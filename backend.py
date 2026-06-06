import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib import error, parse, request
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request as flask_request, send_from_directory
try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError:  # pragma: no cover - local test environments may not have db deps installed
    psycopg = None
    dict_row = None


ROOT = os.path.dirname(os.path.abspath(__file__))
SESSION_COOKIE = "kitchen_session"
BUCKET_NAME = os.environ.get("SUPABASE_STORAGE_BUCKET", "post-images")
LOCAL_TIMEZONE = ZoneInfo(os.environ.get("KITCHEN_TIMEZONE", "America/Toronto"))
TODAY_TIMEZONE = ZoneInfo("America/Vancouver")


app = Flask(__name__, static_folder=None)


def now_utc():
    return datetime.now(timezone.utc)


def now_local():
    return now_utc().astimezone(LOCAL_TIMEZONE)


def now_today_local():
    return now_utc().astimezone(TODAY_TIMEZONE)


def now_iso():
    return now_utc().isoformat()


def normalize_text(value):
    return "".join((value or "").strip().lower().split())


def coerce_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    raise TypeError(f"Unsupported datetime value: {type(value)!r}")


def local_day_label(value):
    created_at = coerce_datetime(value)
    if not created_at:
        return "今天"
    today = now_local().date()
    days = (today - created_at.astimezone(LOCAL_TIMEZONE).date()).days
    if days <= 0:
        return "今天"
    if days == 1:
        return "昨天"
    if days < 7:
        return f"{days} 天前"
    return created_at.strftime("%m-%d")


def infer_category(dish, note):
    text = f"{dish} {note}".lower()
    if any(keyword in text for keyword in ["汤", "炖", "煲", "排骨", "海带", "鸡汤", "牛腩"]):
        return "汤菜"
    if any(keyword in text for keyword in ["面", "粉", "饺", "馄饨"]):
        return "面食"
    if any(keyword in text for keyword in ["炒", "青菜", "鸡蛋", "豆角", "豆苗"]):
        return "家常炒菜"
    if any(keyword in text for keyword in ["快手", "简单", "赶时间"]):
        return "快手晚饭"
    return "家常晚饭"


def pg_connection():
    if psycopg is None or dict_row is None:
        raise RuntimeError("psycopg is not installed")
    return psycopg.connect(
        os.environ["SUPABASE_DB_URL"],
        row_factory=dict_row,
        prepare_threshold=None,
    )


def ensure_schema():
    ddl = """
    create table if not exists users (
        id bigserial primary key,
        display_name text not null,
        email text not null unique,
        password_hash text not null,
        password_salt text not null,
        created_at timestamptz not null default now()
    );

    create table if not exists app_sessions (
        token text primary key,
        user_id bigint not null references users(id) on delete cascade,
        created_at timestamptz not null default now()
    );

    create table if not exists posts (
        id bigserial primary key,
        user_id bigint not null references users(id) on delete cascade,
        dish text not null,
        note text not null default '',
        photo_path text,
        photo_public_url text,
        category text not null,
        created_at timestamptz not null default now()
    );

    create index if not exists posts_user_id_idx on posts(user_id);
    create index if not exists posts_created_at_idx on posts(created_at desc);
    create index if not exists posts_category_idx on posts(category);
    """

    with pg_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(ddl)
        connection.commit()
        seed_demo_data(connection)


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120000,
    ).hex()


def create_user(connection, display_name, email, password):
    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into users (display_name, email, password_hash, password_salt)
            values (%s, %s, %s, %s)
            returning id
            """,
            (display_name, email.lower(), password_hash, salt),
        )
        user_id = cursor.fetchone()["id"]
    connection.commit()
    return user_id


def seed_demo_data(connection):
    with connection.cursor() as cursor:
        cursor.execute("select count(*) as count from users")
        count = cursor.fetchone()["count"]
        if count:
            return

    demo_users = [
        ("周叔", "zhou@example.com"),
        ("Maggie 阿姨", "maggie@example.com"),
        ("陈叔", "chen@example.com"),
        ("Wendy", "wendy@example.com"),
    ]
    user_ids = {}
    for name, email in demo_users:
        user_ids[name] = create_user(connection, name, email, "demo1234")

    demo_posts = [
        ("周叔", "萝卜排骨汤", "今天萝卜炖得更透了，汤也更甜。", None, now_utc() - timedelta(hours=2)),
        ("Maggie 阿姨", "萝卜排骨汤", "她今天也炖了萝卜排骨汤，还说一降温就特别想喝热汤。", None, now_utc() - timedelta(hours=1, minutes=20)),
        ("陈叔", "海带排骨汤", "不是同一道菜，但也是慢炖的汤菜。", None, now_utc() - timedelta(hours=1)),
        ("Wendy", "番茄鸡蛋面", "今天也是快手热乎的一顿。", None, now_utc() - timedelta(minutes=40)),
        ("周叔", "土豆烧鸡", "这是最近回应最多的一道，已经有两个人说下周要试。", None, now_utc() - timedelta(days=3)),
        ("周叔", "白菜炖粉条", "很普通的一顿，但正因为普通，反而让人觉得特别像家里。", None, now_utc() - timedelta(days=7)),
        ("Maggie 阿姨", "海带排骨汤", "这周又撞上了一次汤菜。", None, now_utc() - timedelta(days=2)),
    ]

    with connection.cursor() as cursor:
        for author, dish, note, photo_url, created_at in demo_posts:
            cursor.execute(
                """
                insert into posts (user_id, dish, note, photo_public_url, category, created_at)
                values (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user_ids[author],
                    dish,
                    note,
                    photo_url,
                    infer_category(dish, note),
                    created_at.isoformat(),
                ),
            )
    connection.commit()


def create_session(connection, user_id):
    token = secrets.token_urlsafe(32)
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into app_sessions (token, user_id) values (%s, %s)",
            (token, user_id),
        )
    connection.commit()
    return token


def current_user(connection):
    token = flask_request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select users.id, users.display_name, users.email
            from app_sessions
            join users on users.id = app_sessions.user_id
            where app_sessions.token = %s
            """,
            (token,),
        )
        return cursor.fetchone()


def delete_session(connection, token):
    with connection.cursor() as cursor:
        cursor.execute("delete from app_sessions where token = %s", (token,))
    connection.commit()


def parse_data_url(data_url):
    match = re.match(r"^data:(?P<mime>[\w/+.-]+);base64,(?P<data>.+)$", data_url or "")
    if not match:
        raise ValueError("图片格式不对")
    mime = match.group("mime")
    raw = base64.b64decode(match.group("data"))
    extension = mime.split("/")[-1].replace("jpeg", "jpg")
    return mime, raw, extension


def upload_to_storage(user_id, photo_data_url):
    mime, raw, extension = parse_data_url(photo_data_url)
    object_path = f"user-{user_id}/{int(now_utc().timestamp())}-{secrets.token_hex(6)}.{extension}"
    upload_url = f"{os.environ['SUPABASE_URL'].rstrip('/')}/storage/v1/object/{BUCKET_NAME}/{object_path}"

    upload_request = request.Request(
        upload_url,
        data=raw,
        method="POST",
        headers={
            "Authorization": f"Bearer {os.environ['SUPABASE_SERVICE_ROLE_KEY']}",
            "apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
            "Content-Type": mime,
            "x-upsert": "false",
        },
    )
    try:
        with request.urlopen(upload_request) as response:
            response.read()
    except error.HTTPError as exc:
        raise RuntimeError(f"图片上传失败: {exc.read().decode('utf-8', errors='ignore')}") from exc

    public_url = f"{os.environ['SUPABASE_URL'].rstrip('/')}/storage/v1/object/public/{BUCKET_NAME}/{object_path}"
    return object_path, public_url


def serialize_match(row, audience, current_post):
    comments = []
    if normalize_text(row["dish"]) == normalize_text(current_post["dish"]):
        comments = ["你今天也做这个？", "这一顿一看就能聊起来。"]
    else:
        comments = ["虽然不是同一道菜，但感觉是一类晚饭。"]
    return {
        "author": row["display_name"],
        "dish": row["dish"],
        "note": row["note"] or "今天也做了这一顿。",
        "audience": audience,
        "comments": comments,
        "photo_data_url": row["photo_public_url"],
    }


def fetch_posts(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select posts.*, users.display_name
            from posts
            join users on users.id = posts.user_id
            order by posts.created_at desc
            """
        )
        return cursor.fetchall()


def is_same_local_day(value, target_day=None):
    created_at = coerce_datetime(value)
    if not created_at:
        return False
    day = target_day or now_today_local().date()
    return created_at.astimezone(TODAY_TIMEZONE).date() == day


def recent_local_day_range(days=7):
    return now_local() - timedelta(days=days)


def serialize_current_post(row):
    return {
        "id": row["id"],
        "dish": row["dish"],
        "note": row["note"] or "",
        "category": row["category"],
        "day": local_day_label(row.get("created_at")),
        "photo_data_url": row.get("photo_public_url"),
    }


def serialize_matched_post(row, audience, current_post=None):
    payload = serialize_match(row, audience, current_post or row)
    payload["id"] = row["id"]
    payload["user_id"] = row["user_id"]
    payload["category"] = row["category"]
    payload["created_day"] = local_day_label(row.get("created_at"))
    return payload


def serialize_public_post(row):
    created_at = coerce_datetime(row.get("created_at"))
    return {
        "display_name": row["display_name"],
        "dish": row["dish"],
        "note": row["note"] or "",
        "photo_public_url": row.get("photo_public_url"),
        "created_at": created_at.isoformat() if created_at else None,
        "category": row["category"],
    }


def build_today_hot_dishes(posts):
    today = now_today_local().date()
    today_posts = [row for row in posts if is_same_local_day(row.get("created_at"), today)]
    grouped = defaultdict(list)
    for row in today_posts:
        grouped[normalize_text(row["dish"])].append(row)

    hot_dishes = []
    for _, group_rows in grouped.items():
        sorted_rows = sorted(group_rows, key=lambda row: coerce_datetime(row.get("created_at")) or now_utc(), reverse=True)
        display_names = [row["display_name"] for row in sorted_rows]
        unique_names = []
        for name in display_names:
            if name not in unique_names:
                unique_names.append(name)

        thumbnail = next((row.get("photo_public_url") for row in sorted_rows if row.get("photo_public_url")), None)
        hot_dishes.append({
            "dish": sorted_rows[0]["dish"],
            "category": sorted_rows[0]["category"],
            "count": len(sorted_rows),
            "user_names": unique_names[:3],
            "remaining_user_count": max(0, len(unique_names) - 3),
            "thumbnail": thumbnail,
        })

    hot_dishes.sort(key=lambda item: (-item["count"], item["dish"]))
    return hot_dishes[:5]


def build_today_new_dishes(posts):
    today = now_today_local().date()
    today_posts = [row for row in posts if is_same_local_day(row.get("created_at"), today)]
    if not today_posts:
        return []

    seven_days_ago = now_today_local() - timedelta(days=7)
    recent_history = {}
    for row in posts:
        created_at = coerce_datetime(row.get("created_at"))
        if not created_at:
            continue
        created_local = created_at.astimezone(TODAY_TIMEZONE)
        dish_key = normalize_text(row["dish"])
        if created_local.date() == today:
            continue
        if created_local < seven_days_ago:
            continue
        recent_history[dish_key] = True

    grouped_today = defaultdict(list)
    for row in today_posts:
        grouped_today[normalize_text(row["dish"])].append(row)

    new_dishes = []
    for dish_key, group_rows in grouped_today.items():
        if recent_history.get(dish_key):
            continue
        sorted_rows = sorted(group_rows, key=lambda row: coerce_datetime(row.get("created_at")) or now_utc(), reverse=True)
        chosen = sorted_rows[0]
        created_at = coerce_datetime(chosen.get("created_at"))
        new_dishes.append({
            "dish": chosen["dish"],
            "category": chosen["category"],
            "display_name": chosen["display_name"],
            "photo_public_url": chosen.get("photo_public_url"),
            "created_at": created_at.isoformat() if created_at else None,
            "note": chosen.get("note") or "",
        })

    new_dishes.sort(key=lambda item: item["created_at"] or "", reverse=True)
    return new_dishes[:5]


def build_grouped_matches(rows, audience, key_field, label_field, current_lookup=None):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[key_field]].append(row)

    groups = []
    for group_key, group_rows in grouped.items():
        sorted_rows = sorted(group_rows, key=lambda row: coerce_datetime(row.get("created_at")) or now_utc(), reverse=True)
        display_names = [row["display_name"] for row in sorted_rows]
        thumbnails = [row.get("photo_public_url") for row in sorted_rows if row.get("photo_public_url")][:3]
        preview_names = display_names[:5]
        current_post = None
        if current_lookup:
            current_post = current_lookup(group_rows[0])

        groups.append({
            "group_key": group_key,
            "group_type": audience,
            "label": group_rows[0][label_field],
            "count": len(sorted_rows),
            "summary": f"你和 {len(sorted_rows)} 个人撞上了",
            "user_names": preview_names,
            "remaining_user_count": max(0, len(display_names) - len(preview_names)),
            "thumbnails": thumbnails,
            "posts": [
                serialize_matched_post(row, audience, current_post or row)
                for row in sorted_rows
            ],
        })

    groups.sort(key=lambda group: group["count"], reverse=True)
    return groups


def build_public_feed(connection):
    posts = fetch_posts(connection)
    today = now_today_local().date()
    today_posts = [row for row in posts if is_same_local_day(row.get("created_at"), today)]
    recent_posts = posts[:12]

    starters = [
        {
            "name": row["display_name"],
            "meta": f"刚发了 {row['dish']} · {(row['note'] or '今天更新了晚饭')[:18]}",
        }
        for row in recent_posts[:4]
    ]

    return {
        "updates_count": len(recent_posts),
        "today_posts": [serialize_public_post(row) for row in today_posts[:8]],
        "recent_posts": [serialize_public_post(row) for row in recent_posts],
        "today_hot_dishes": build_today_hot_dishes(posts),
        "today_new_dishes": build_today_new_dishes(posts),
        "starters": starters,
        "hero_points": ["先看看大家做了什么", "想发一顿时再登录", "撞菜和记录会在登录后开始"],
    }


def build_dashboard(connection, user):
    posts = fetch_posts(connection)
    user_posts = [row for row in posts if row["user_id"] == user["id"]]
    today = now_today_local().date()
    current_user_posts = [row for row in user_posts if is_same_local_day(row.get("created_at"), today)]
    if not current_user_posts and user_posts:
        current_user_posts = user_posts[:1]

    starters = [
        {
            "name": row["display_name"],
            "meta": f"刚发了 {row['dish']} · {(row['note'] or '今天更新了晚饭')[:18]}",
        }
        for row in posts[:4]
    ]

    same_dish_matches = []
    same_style_matches = []
    weekly_matches = []
    monthly_profiles = [
        "这个月你最常撞上的是家常晚饭。",
        "最容易和你撞上的人，通常也在晚饭前后做饭。",
        "你这月最常引发回应的，是带一点小经验的家常菜。",
    ]

    matched_posts = []
    matched_users_map = {}
    matched_dishes_map = {}
    grouped_matches = {"same_dish": [], "same_style": []}

    if current_user_posts:
        current_dish_keys = {normalize_text(row["dish"]) for row in current_user_posts}
        current_categories = {row["category"] for row in current_user_posts}

        same_dish_rows = [
            row
            for row in posts
            if row["user_id"] != user["id"]
            and is_same_local_day(row.get("created_at"), today)
            and normalize_text(row["dish"]) in current_dish_keys
        ]
        same_style_rows = [
            row
            for row in posts
            if row["user_id"] != user["id"]
            and is_same_local_day(row.get("created_at"), today)
            and row["category"] in current_categories
            and normalize_text(row["dish"]) not in current_dish_keys
        ]

        current_post_by_dish = {normalize_text(row["dish"]): row for row in current_user_posts}
        same_dish_matches = [
            serialize_matched_post(row, "同一道菜", current_post_by_dish.get(normalize_text(row["dish"])))
            for row in same_dish_rows
        ]
        same_style_matches = [
            serialize_matched_post(
                row,
                "同一类菜",
                next((post for post in current_user_posts if post["category"] == row["category"]), current_user_posts[0]),
            )
            for row in same_style_rows
        ]

        grouped_matches = {
            "same_dish": build_grouped_matches(
                same_dish_rows,
                "同一道菜",
                "dish",
                "dish",
                current_lookup=lambda row: current_post_by_dish.get(normalize_text(row["dish"])),
            ),
            "same_style": build_grouped_matches(
                same_style_rows,
                "同一类菜",
                "category",
                "category",
                current_lookup=lambda row: next(
                    (post for post in current_user_posts if post["category"] == row["category"]),
                    current_user_posts[0],
                ),
            ),
        }

        all_matched_rows = same_dish_rows + same_style_rows
        matched_posts = same_dish_matches + same_style_matches

        for row in all_matched_rows:
            matched_users_map[row["user_id"]] = row["display_name"]
            matched_dishes_map[normalize_text(row["dish"])] = row["dish"]

        week_ago_local = recent_local_day_range(7)
        weekly_counts = defaultdict(lambda: {"count": 0, "categories": set()})
        for row in posts:
            created_at = coerce_datetime(row.get("created_at"))
            if not created_at:
                continue
            created_local = created_at.astimezone(LOCAL_TIMEZONE)
            if row["user_id"] == user["id"] or created_local < week_ago_local:
                continue
            if row["category"] not in current_categories:
                continue
            weekly_counts[row["display_name"]]["count"] += 1
            weekly_counts[row["display_name"]]["categories"].add(row["category"])

        weekly_matches = [
            {
                "name": name,
                "meta": f"这周已经和你撞了 {data['count']} 次 {'、'.join(sorted(data['categories'])) or '家常晚饭'}。",
            }
            for name, data in sorted(weekly_counts.items(), key=lambda item: item[1]["count"], reverse=True)[:3]
        ]

        lead_category = current_user_posts[0]["category"]
        monthly_profiles = [
            f"这个月你最常撞上的是 {lead_category}。",
            "今天发过同类菜的人，双方都应该看到彼此。",
            f"你今天发的 {len(current_user_posts)} 道菜，都会参与撞菜匹配。",
        ]

    return {
        "updates_count": len(posts),
        "starters": starters,
        "same_dish_matches": same_dish_matches,
        "same_style_matches": same_style_matches,
        "today_hot_dishes": build_today_hot_dishes(posts),
        "today_new_dishes": build_today_new_dishes(posts),
        "weekly_matches": weekly_matches,
        "monthly_profiles": monthly_profiles,
        "hero_points": ["先写菜名", "再看今天撞上谁", "慢慢留下自己的记录"],
        "current_user_posts": [serialize_current_post(row) for row in current_user_posts],
        "matched_posts": matched_posts,
        "matched_users": [
            {"user_id": user_id, "display_name": display_name}
            for user_id, display_name in matched_users_map.items()
        ],
        "matched_dishes": list(matched_dishes_map.values()),
        "grouped_matches": grouped_matches,
    }


def build_profile(connection, user):
    posts = fetch_posts(connection)
    user_posts = [row for row in posts if row["user_id"] == user["id"]]

    categories = {}
    dishes = {}
    for row in user_posts:
        categories[row["category"]] = categories.get(row["category"], 0) + 1
        dishes[row["dish"]] = dishes.get(row["dish"], 0) + 1
    top_category = max(categories.items(), key=lambda item: item[1])[0] if categories else "家常晚饭"

    week_ago = recent_local_day_range(7)
    month_ago = recent_local_day_range(30)
    weekly_other = []
    monthly_other = []
    for row in posts:
        created_at = coerce_datetime(row.get("created_at"))
        if not created_at:
            continue
        created_local = created_at.astimezone(LOCAL_TIMEZONE)
        if row["user_id"] == user["id"]:
            continue
        if created_local >= week_ago:
            weekly_other.append(row)
        if created_local >= month_ago:
            monthly_other.append(row)

    weekly_posts_count = sum(
        1
        for row in user_posts
        if (
            (coerce_datetime(row.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc))
            .astimezone(LOCAL_TIMEZONE)
            >= week_ago
        )
    )
    monthly_posts_count = sum(
        1
        for row in user_posts
        if (
            (coerce_datetime(row.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc))
            .astimezone(LOCAL_TIMEZONE)
            >= month_ago
        )
    )

    stats = [
        {"label": "本周发了", "value": f"{weekly_posts_count} 顿"},
        {"label": "最常做", "value": top_category},
        {"label": "本月记录", "value": f"{monthly_posts_count} 顿"},
        {"label": "本月撞菜", "value": f"{len(monthly_other)} 次"},
    ]

    timeline = [
        {
            "day": local_day_label(row["created_at"]),
            "dish": row["dish"],
            "note": row["note"] or "今天记下了这顿饭。",
        }
        for row in user_posts[:12]
    ]

    related_counts = {}
    for row in weekly_other:
        if row["category"] != top_category:
            continue
        related_counts.setdefault(row["display_name"], 0)
        related_counts[row["display_name"]] += 1

    relationships = [
        {"name": name, "meta": f"这周已经和你撞了 {count} 次 {top_category}。"}
        for name, count in sorted(related_counts.items(), key=lambda item: item[1], reverse=True)[:3]
    ]

    next_up = []
    seen = set()
    for row in monthly_other:
        if row["display_name"] in seen:
            continue
        seen.add(row["display_name"])
        next_up.append({
            "name": row["display_name"],
            "meta": f"最近做了 {row['dish']}，晚饭节奏和你挺像。",
        })
        if len(next_up) >= 3:
            break

    affinities = [
        {
            "name": "同城晚饭时间",
            "match": "会更常遇见",
            "text": "晚饭前后总发内容的人，更容易反复出现在彼此首页。",
            "tags": ["生活节奏接近", "反复曝光"],
        },
        {
            "name": top_category,
            "match": "更容易聊起来",
            "text": f"你最近最常发的是 {top_category}，所以更容易撞上相似口味的人。",
            "tags": ["家常菜", "同口味"],
        },
        {
            "name": "连续撞上几次",
            "match": "会慢慢变熟",
            "text": "先从撞菜开始，撞多了以后就会慢慢记住彼此。",
            "tags": ["熟人生成", "轻连接"],
        },
    ]

    top_dishes = [
        {"dish": dish, "count": count}
        for dish, count in sorted(dishes.items(), key=lambda item: (-item[1], item[0]))[:3]
    ]
    top_categories = [
        {"category": category, "count": count}
        for category, count in sorted(categories.items(), key=lambda item: (-item[1], item[0]))[:3]
    ]
    profile_stats = {
        "total_posts": len(user_posts),
        "week_posts": weekly_posts_count,
        "month_posts": monthly_posts_count,
        "top_dishes": top_dishes,
        "top_categories": top_categories,
    }

    return {
        "stats": stats,
        "profile_stats": profile_stats,
        "timeline": timeline,
        "relationships": relationships,
        "next_up": next_up,
        "affinities": affinities,
    }


@app.after_request
def add_cache_headers(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def index():
    return send_from_directory(ROOT, "index.html")


@app.get("/index.html")
def index_html():
    return send_from_directory(ROOT, "index.html")


@app.get("/styles.css")
def styles():
    return send_from_directory(ROOT, "styles.css")


@app.get("/app.js")
def app_js():
    return send_from_directory(ROOT, "app.js")


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/me")
@app.get("/api/me")
def me():
    with pg_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify({"error": "未登录"}), 401
        return jsonify({"user": dict(user)})


@app.get("/public-feed")
@app.get("/api/public-feed")
def public_feed():
    with pg_connection() as connection:
        return jsonify(build_public_feed(connection))


@app.post("/register")
@app.post("/api/register")
def register():
    payload = flask_request.get_json(force=True, silent=True) or {}
    display_name = (payload.get("display_name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if len(display_name) < 2 or "@" not in email or len(password) < 6:
        return jsonify({"error": "请填写正确的称呼、邮箱和至少 6 位密码"}), 400

    with pg_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select id from users where email = %s", (email,))
            if cursor.fetchone():
                return jsonify({"error": "这个邮箱已经注册过了"}), 400
        user_id = create_user(connection, display_name, email, password)
        token = create_session(connection, user_id)
        with connection.cursor() as cursor:
            cursor.execute("select id, display_name, email from users where id = %s", (user_id,))
            user = cursor.fetchone()

    response = jsonify({"user": dict(user)})
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="Lax", max_age=60 * 60 * 24 * 30)
    return response


@app.post("/login")
@app.post("/api/login")
def login():
    payload = flask_request.get_json(force=True, silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    with pg_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select * from users where email = %s", (email,))
            user = cursor.fetchone()
        if not user:
            return jsonify({"error": "邮箱或密码不对"}), 400

        expected = hash_password(password, user["password_salt"])
        if not hmac.compare_digest(expected, user["password_hash"]):
            return jsonify({"error": "邮箱或密码不对"}), 400

        token = create_session(connection, user["id"])

    response = jsonify({"user": {"id": user["id"], "display_name": user["display_name"], "email": user["email"]}})
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="Lax", max_age=60 * 60 * 24 * 30)
    return response


@app.post("/logout")
@app.post("/api/logout")
def logout():
    token = flask_request.cookies.get(SESSION_COOKIE)
    if token:
        with pg_connection() as connection:
            delete_session(connection, token)
    response = jsonify({"ok": True})
    response.set_cookie(SESSION_COOKIE, "", max_age=0)
    return response


@app.post("/posts")
@app.post("/api/posts")
def create_post():
    payload = flask_request.get_json(force=True, silent=True) or {}
    dish = (payload.get("dish") or "").strip()
    note = (payload.get("note") or "").strip()
    photo_data_url = payload.get("photo_data_url")

    if not dish:
        return jsonify({"error": "请先写下今天做了什么"}), 400

    with pg_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify({"error": "请先登录"}), 401

        photo_path = None
        photo_public_url = None
        if photo_data_url:
            try:
                photo_path, photo_public_url = upload_to_storage(user["id"], photo_data_url)
            except Exception as exc:
                return jsonify({"error": str(exc)}), 400

        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into posts (user_id, dish, note, photo_path, photo_public_url, category)
                values (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user["id"],
                    dish,
                    note,
                    photo_path,
                    photo_public_url,
                    infer_category(dish, note),
                ),
            )
        connection.commit()
    return jsonify({"ok": True})


@app.get("/dashboard")
@app.get("/api/dashboard")
def dashboard():
    with pg_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify({"error": "请先登录"}), 401
        return jsonify(build_dashboard(connection, user))


@app.get("/profile")
@app.get("/api/profile")
def profile():
    with pg_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify({"error": "请先登录"}), 401
        return jsonify(build_profile(connection, user))

if os.environ.get("SUPABASE_DB_URL"):
    ensure_schema()
