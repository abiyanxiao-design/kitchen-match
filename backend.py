import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib import error, parse, request

import psycopg
from flask import Flask, jsonify, request as flask_request, send_from_directory
from psycopg.rows import dict_row


ROOT = os.path.dirname(os.path.abspath(__file__))
SESSION_COOKIE = "kitchen_session"
BUCKET_NAME = os.environ.get("SUPABASE_STORAGE_BUCKET", "post-images")


app = Flask(__name__, static_folder=None)


def now_utc():
    return datetime.now(timezone.utc)


def now_iso():
    return now_utc().isoformat()


def normalize_text(value):
    return "".join((value or "").strip().lower().split())


def local_day_label(iso_string):
    created_at = datetime.fromisoformat(iso_string)
    today = now_utc().date()
    days = (today - created_at.date()).days
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


def build_dashboard(connection, user):
    posts = fetch_posts(connection)
    user_posts = [row for row in posts if row["user_id"] == user["id"]]
    current_post = user_posts[0] if user_posts else None

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

    if current_post:
        normalized_dish = normalize_text(current_post["dish"])
        same_dish_rows = [
            row
            for row in posts
            if row["user_id"] != user["id"] and normalize_text(row["dish"]) == normalized_dish
        ]
        same_style_rows = [
            row
            for row in posts
            if row["user_id"] != user["id"]
            and row["category"] == current_post["category"]
            and normalize_text(row["dish"]) != normalized_dish
        ]

        same_dish_matches = [serialize_match(row, "同一道菜", current_post) for row in same_dish_rows[:3]]
        same_style_matches = [serialize_match(row, "同一类菜", current_post) for row in same_style_rows[:4]]

        week_ago = now_utc() - timedelta(days=7)
        weekly_counts = {}
        for row in posts:
            created_at = datetime.fromisoformat(row["created_at"])
            if row["user_id"] == user["id"] or created_at < week_ago:
                continue
            if row["category"] != current_post["category"]:
                continue
            weekly_counts.setdefault(row["display_name"], 0)
            weekly_counts[row["display_name"]] += 1

        weekly_matches = [
            {
                "name": name,
                "meta": f"这周已经和你撞了 {count} 次 {current_post['category']}。",
            }
            for name, count in sorted(weekly_counts.items(), key=lambda item: item[1], reverse=True)[:3]
        ]

        monthly_profiles = [
            f"这个月你最常撞上的是 {current_post['category']}。",
            "最容易和你撞上的人，通常也在晚饭前后做饭。",
            f"最近只要你发 {current_post['category']}，就更容易有人回你。",
        ]

    return {
        "updates_count": len(posts),
        "starters": starters,
        "same_dish_matches": same_dish_matches,
        "same_style_matches": same_style_matches,
        "weekly_matches": weekly_matches,
        "monthly_profiles": monthly_profiles,
        "hero_points": ["先写菜名", "再看今天撞上谁", "慢慢留下自己的记录"],
    }


def build_profile(connection, user):
    posts = fetch_posts(connection)
    user_posts = [row for row in posts if row["user_id"] == user["id"]]

    categories = {}
    for row in user_posts:
        categories[row["category"]] = categories.get(row["category"], 0) + 1
    top_category = max(categories.items(), key=lambda item: item[1])[0] if categories else "家常晚饭"

    week_ago = now_utc() - timedelta(days=7)
    month_ago = now_utc() - timedelta(days=30)
    weekly_other = []
    monthly_other = []
    for row in posts:
        created_at = datetime.fromisoformat(row["created_at"])
        if row["user_id"] == user["id"]:
            continue
        if created_at >= week_ago:
            weekly_other.append(row)
        if created_at >= month_ago:
            monthly_other.append(row)

    stats = [
        {"label": "本周发了", "value": f"{sum(1 for row in user_posts if datetime.fromisoformat(row['created_at']) >= week_ago)} 顿"},
        {"label": "最常做", "value": top_category},
        {"label": "本月记录", "value": f"{sum(1 for row in user_posts if datetime.fromisoformat(row['created_at']) >= month_ago)} 顿"},
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

    return {
        "stats": stats,
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


@app.get("/api/me")
def me():
    with pg_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify({"error": "未登录"}), 401
        return jsonify({"user": dict(user)})


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


@app.post("/api/logout")
def logout():
    token = flask_request.cookies.get(SESSION_COOKIE)
    if token:
        with pg_connection() as connection:
            delete_session(connection, token)
    response = jsonify({"ok": True})
    response.set_cookie(SESSION_COOKIE, "", max_age=0)
    return response


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


@app.get("/api/dashboard")
def dashboard():
    with pg_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify({"error": "请先登录"}), 401
        return jsonify(build_dashboard(connection, user))


@app.get("/api/profile")
def profile():
    with pg_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify({"error": "请先登录"}), 401
        return jsonify(build_profile(connection, user))


ensure_schema()
