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
MAX_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}


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


DEFAULT_DISH_DICTIONARY = {
    "南昌炒粉": {
        "culture": "🏮 赣菜",
        "story": "南昌人的日常快乐之一，早中晚都能来一份。",
    },
    "南昌汤粉": {
        "culture": "🏮 赣菜",
        "story": "南昌人的一天，可能就是从一碗热汤粉开始。",
    },
    "藜蒿炒腊肉": {
        "culture": "🏮 赣菜",
        "story": "很多江西人心里的春天味道，藜蒿一上桌，就有很强的家乡感。",
    },
    "瓦罐汤": {
        "culture": "🏮 赣菜",
        "story": "江西很有代表性的汤品，慢慢煨出来的香气很有家的感觉。",
    },
    "余干辣椒炒肉": {
        "culture": "🏮 赣菜",
        "story": "江西人懂的辣，香、辣、下饭都在这一盘里。",
    },
    "江西小炒鱼": {
        "culture": "🏮 赣菜",
        "story": "这种带着鲜辣和锅气的小炒，很容易让江西人一下子想起家里的味道。",
    },
    "番茄炒蛋": {
        "culture": "🍅 家常经典",
        "story": "几乎每个中国家庭都做过的一道菜。",
    },
    "红烧肉": {
        "culture": "🍅 家常经典",
        "story": "很多人家的招牌菜里，总少不了这样一盘浓油赤酱的熟悉味道。",
    },
    "可乐鸡翅": {
        "culture": "🍅 家常经典",
        "story": "甜咸刚好的可乐鸡翅，常常是很多人记忆里特别有亲切感的一道菜。",
    },
    "清炒莴苣": {
        "culture": "🥬 时令蔬菜",
        "story": "这种清清爽爽的时令蔬菜，最能看出家里餐桌跟着季节在走。",
    },
    "炒青菜": {
        "culture": "🥬 时令蔬菜",
        "story": "一盘简单青菜，往往就是一顿家常饭最安稳的底色。",
    },
    "生菜": {
        "culture": "🥬 时令蔬菜",
        "story": "这种看起来简单的蔬菜，常常最能把家常饭的节奏接住。",
    },
    "菠菜": {
        "culture": "🥬 时令蔬菜",
        "story": "菠菜这种家里常见的绿叶菜，往往一上桌就有一种很日常的安心感。",
    },
    "奶黄包": {
        "culture": "🥟 中式点心",
        "story": "热乎乎的奶黄包一上桌，总有一种茶楼和家里早饭同时靠近的感觉。",
    },
    "豆沙包": {
        "culture": "🥟 中式点心",
        "story": "豆沙包这种甜口点心，常常让人一下子想到小时候的早餐桌。",
    },
    "小笼包": {
        "culture": "🥟 中式点心",
        "story": "小笼包最迷人的地方，往往就是那口热汤和刚蒸好的香气。",
    },
    "烧麦": {
        "culture": "🥟 中式点心",
        "story": "烧麦很适合出现在早饭和点心时间里，轻轻巧巧却很有满足感。",
    },
    "帝王蟹": {
        "culture": "🌊 海鲜时令",
        "story": "这种一上桌就很有存在感的海鲜，常常让整顿饭都亮起来。",
    },
    "帝皇蟹": {
        "culture": "🌊 海鲜时令",
        "story": "帝皇蟹这种大块头海鲜，一端上桌就很有节气和聚餐的感觉。",
    },
    "斑点虾": {
        "culture": "🌊 海鲜时令",
        "story": "很多人在等的就是这一口当季鲜味，越简单做越能吃出好时候。",
    },
    "螃蟹": {
        "culture": "🌊 海鲜时令",
        "story": "螃蟹这种带着季节感的海鲜，很容易让一顿饭变得更像一次小聚。",
    },
}


FOOD_CULTURE_RULES = [
    {
        "cuisine": "赣菜",
        "label": "🏮 赣菜",
        "story": "江西菜里常有一种鲜辣和烟火气并行的感觉，端上桌就很有家乡味。",
        "keywords": ["藜蒿炒腊肉", "瓦罐汤", "南昌炒粉", "余干辣椒炒肉", "三杯鸡", "鄱阳湖鱼", "粉蒸肉", "米粉蒸肉", "井冈山烟笋", "江西小炒鱼", "萍乡小炒肉"],
    },
    {
        "cuisine": "川菜",
        "label": "🏮 川菜",
        "story": "川菜常把麻、辣、鲜和锅气放在一起，很容易一口就把人叫醒。",
        "keywords": ["宫保鸡丁", "麻婆豆腐", "回锅肉", "水煮鱼", "夫妻肺片", "鱼香肉丝", "口水鸡"],
    },
    {
        "cuisine": "湘菜",
        "label": "🌶️ 湘菜",
        "story": "湘菜的辣往往很直接，香、辣、下饭常常一下子就都到位了。",
        "keywords": ["辣椒炒肉", "剁椒鱼头", "小炒肉", "农家小炒", "腊味合蒸"],
    },
    {
        "cuisine": "粤菜",
        "label": "🥢 粤菜",
        "story": "粤菜常把讲究藏在细处里，很多时候越看着简单，越吃得出功夫。",
        "keywords": ["白切鸡", "叉烧", "肠粉", "煲仔饭", "烧鹅", "云吞面"],
    },
    {
        "cuisine": "东北菜",
        "label": "❄️ 东北菜",
        "story": "东北菜很多时候香得很直接、分量也实在，吃起来就是一种痛快。",
        "keywords": ["锅包肉", "地三鲜", "酸菜白肉", "溜肉段", "杀猪菜"],
    },
    {
        "cuisine": "江浙菜",
        "label": "🪷 江浙菜",
        "story": "江浙菜常有一种细致的鲜甜感，很多人一吃就会想到江南餐桌。",
        "keywords": ["红烧肉", "小笼包", "西湖醋鱼", "东坡肉", "醉鸡"],
    },
    {
        "cuisine": "闽菜",
        "label": "🦪 闽菜",
        "story": "闽菜常把海味和汤味一起端出来，味道里很有沿海城市的节奏。",
        "keywords": ["佛跳墙", "荔枝肉", "沙茶面", "海蛎煎"],
    },
    {
        "cuisine": "徽菜",
        "label": "⛰️ 徽菜",
        "story": "徽菜里常见山味和火候感，很多菜一吃就有种慢慢煨出来的厚实。",
        "keywords": ["臭鳜鱼", "毛豆腐", "刀板香"],
    },
    {
        "cuisine": "云南风味",
        "label": "🌿 云南风味",
        "story": "云南风味常带一点山野感，香气清亮，很容易让人想到当季食材。",
        "keywords": ["过桥米线", "汽锅鸡", "菌子", "鲜花饼", "饵块"],
    },
    {
        "cuisine": "贵州风味",
        "label": "🥣 贵州风味",
        "story": "贵州风味里很常见酸、辣和发酵香，味道一出来就很有辨识度。",
        "keywords": ["酸汤鱼", "丝娃娃", "折耳根", "贵州辣子鸡"],
    },
    {
        "cuisine": "新疆风味",
        "label": "🐑 新疆风味",
        "story": "新疆风味常把肉香、孜然和面食放在一起，热烈得很有画面感。",
        "keywords": ["大盘鸡", "烤羊肉串", "抓饭", "馕", "拉条子"],
    },
    {
        "cuisine": "客家风味",
        "label": "🧄 客家风味",
        "story": "客家风味常给人一种朴实又扎实的感觉，很多菜都很耐吃、很像家里味道。",
        "keywords": ["梅菜扣肉", "酿豆腐", "盐焗鸡"],
    },
    {
        "cuisine": "潮汕风味",
        "label": "🫖 潮汕风味",
        "story": "潮汕风味常把鲜味放在最前面，看起来轻，吃起来却很有记忆点。",
        "keywords": ["牛肉火锅", "潮汕牛肉丸", "卤鹅", "蚝烙"],
    },
    {
        "cuisine": "北方家常",
        "label": "🥟 北方家常",
        "story": "这类面点和家常主食常常不只是吃什么，也和热气腾腾的家里感觉连在一起。",
        "keywords": ["饺子", "包子", "馒头", "烙饼", "馄饨"],
    },
    {
        "cuisine": "海鲜时令",
        "label": "🌊 海鲜时令",
        "story": "这种菜最迷人的地方，往往就是当季食材本身带出来的鲜味。",
        "keywords": ["斑点虾", "螃蟹", "生蚝", "扇贝", "鄱阳湖鱼", "鱼", "虾"],
    },
    {
        "cuisine": "主食面饭",
        "label": "🍜 主食面饭",
        "story": "主食常常是最安静的一部分，却最能把一顿饭真正接住。",
        "keywords": ["米饭", "炒饭", "面条", "米线", "河粉", "米粉", "粉", "馒头", "包子", "饺子"],
    },
    {
        "cuisine": "汤粥",
        "label": "🥣 汤粥",
        "story": "汤粥类的菜常常不靠热闹取胜，更多是一种慢慢炖出来的安稳感。",
        "keywords": ["粥", "汤", "鸡汤", "排骨汤", "牛腩汤", "海带汤", "玉米汤", "瓦罐汤"],
    },
    {
        "cuisine": "火锅锅物",
        "label": "🍲 火锅锅物",
        "story": "锅物很多时候不只是吃什么，更像是一群人围着热气慢慢聊起来。",
        "keywords": ["火锅", "麻辣烫", "砂锅", "锅物", "串串"],
    },
    {
        "cuisine": "凉菜小菜",
        "label": "🥒 凉菜小菜",
        "story": "凉菜小菜看起来低调，往往最能把一顿饭的节奏提起来。",
        "keywords": ["凉拌", "拍黄瓜", "凉菜", "泡菜"],
    },
    {
        "cuisine": "甜品饮品",
        "label": "🍰 甜品饮品",
        "story": "甜品饮品更像是一顿饭后的小句号，也很容易留下当天的情绪记忆。",
        "keywords": ["奶茶", "甜品", "蛋糕", "布丁", "糖水", "咖啡"],
    },
    {
        "cuisine": "其他家常",
        "label": "🍚 其他家常",
        "story": "这是一道很适合记录在日常餐桌里的菜。",
        "keywords": ["番茄炒蛋", "炒青菜", "豆角", "青椒肉丝", "家常"],
    },
]


def culture_label_to_name(label):
    text = (label or "").strip()
    if not text:
        return "其他家常"
    match = re.search(r"[\u4e00-\u9fffA-Za-z].*", text)
    return (match.group(0).strip() if match else text) or "其他家常"


def dish_dictionary_entry(dish, culture, story):
    label = (culture or "🍚 其他家常").strip() or "🍚 其他家常"
    return {
        "dish": dish,
        "label": label,
        "culture": label,
        "cuisine": culture_label_to_name(label),
        "story": (story or "这是一道很适合记录在日常餐桌里的菜。").strip(),
    }


def load_dish_dictionary(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select dish_key, dish, culture, story
            from dish_dictionary
            order by updated_at desc, created_at desc
            """
        )
        rows = cursor.fetchall()

    dictionary = {}
    for row in rows:
        dictionary[row["dish_key"]] = dish_dictionary_entry(
            row["dish"],
            row["culture"],
            row["story"],
        )
    return dictionary


def seed_dish_dictionary(connection):
    with connection.cursor() as cursor:
        for dish, payload in DEFAULT_DISH_DICTIONARY.items():
            cursor.execute(
                """
                insert into dish_dictionary (dish_key, dish, culture, story)
                values (%s, %s, %s, %s)
                on conflict (dish_key) do nothing
                """,
                (
                    normalize_text(dish),
                    dish,
                    payload["culture"],
                    payload["story"],
                ),
            )


def find_dish_dictionary_match(dish, dish_dictionary):
    normalized = normalize_text(dish)
    if not normalized or not dish_dictionary:
        return None

    exact = dish_dictionary.get(normalized)
    if exact:
        return exact

    partial_matches = [
        entry
        for dish_key, entry in dish_dictionary.items()
        if dish_key and dish_key in normalized
    ]
    if not partial_matches:
        return None
    partial_matches.sort(key=lambda entry: len(normalize_text(entry["dish"])), reverse=True)
    return partial_matches[0]


def build_food_culture_info(dish, dish_dictionary=None):
    dictionary_match = find_dish_dictionary_match(dish, dish_dictionary or {})
    if dictionary_match:
        return {
            "cuisine": dictionary_match["cuisine"],
            "label": dictionary_match["label"],
            "story": dictionary_match["story"],
        }

    normalized = normalize_text(dish)

    # 江西语境下的辣椒炒肉优先识别为赣菜
    if "辣椒炒肉" in dish and any(keyword in dish for keyword in ["江西", "余干", "萍乡", "南昌"]):
        return {
            "cuisine": "赣菜",
            "label": "🏮 赣菜",
            "story": "江西人懂的辣，香、辣、下饭都在这一盘里。",
        }

    for rule in FOOD_CULTURE_RULES:
        if any(normalize_text(keyword) in normalized for keyword in rule["keywords"]):
            story = rule["story"]
            if "藜蒿炒腊肉" in dish:
                story = "很多江西人心里的春天味道，藜蒿一上桌，就有很强的家乡感。"
            elif "南昌炒粉" in dish:
                story = "南昌人的日常快乐之一，早中晚都能来一份。"
            elif "瓦罐汤" in dish:
                story = "江西很有代表性的汤品，慢慢煨出来的香气很有家的感觉。"
            elif "余干辣椒炒肉" in dish:
                story = "江西人懂的辣，香、辣、下饭都在这一盘里。"
            return {
                "cuisine": rule["cuisine"],
                "label": rule["label"],
                "story": story,
            }
    return {
        "cuisine": "其他家常",
        "label": "🍚 其他家常",
        "story": "这是一道很适合记录在日常餐桌里的菜。",
    }


def infer_category(dish, note, dish_dictionary=None):
    return build_food_culture_info(f"{dish} {note}", dish_dictionary)["cuisine"]


def split_dishes(value):
    raw_parts = re.split(r"[\n,，]+", (value or "").strip())
    dishes = [part.strip() for part in raw_parts if part.strip()]
    seen = set()
    ordered = []
    for dish in dishes:
        key = normalize_text(dish)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(dish)
    return ordered

def build_cuisine_info(dish, dish_dictionary=None):
    return build_food_culture_info(dish, dish_dictionary)


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
        is_admin boolean not null default false,
        created_at timestamptz not null default now()
    );
    alter table users add column if not exists is_admin boolean not null default false;

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

    create table if not exists dish_dictionary (
        dish_key text primary key,
        dish text not null,
        culture text not null,
        story text not null,
        created_at timestamptz not null default now(),
        updated_at timestamptz not null default now()
    );
    """

    with pg_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(ddl)
        seed_dish_dictionary(connection)
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

    dish_dictionary = load_dish_dictionary(connection)

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
                    infer_category(dish, note, dish_dictionary),
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
            select users.id, users.display_name, users.email, users.is_admin
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


def get_post_like_state(connection, post_id, viewer_user_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select
                count(*)::bigint as like_count,
                bool_or(user_id = %s) as liked_by_me
            from likes
            where post_id = %s
            """,
            (viewer_user_id, post_id),
        )
        row = cursor.fetchone() or {}
    return {
        "like_count": int(row.get("like_count") or 0),
        "liked_by_me": bool(row.get("liked_by_me")),
    }


def toggle_post_like(connection, post_id, viewer_user_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select id, user_id
            from posts
            where id = %s
            """,
            (post_id,),
        )
        post = cursor.fetchone()
        if not post:
            return None, "这道菜好像已经不见了。"
        if post["user_id"] == viewer_user_id:
            return None, "这是你自己的菜，先留给别人来赞你吧。"

        cursor.execute(
            """
            select id
            from likes
            where post_id = %s and user_id = %s
            """,
            (post_id, viewer_user_id),
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                "delete from likes where post_id = %s and user_id = %s",
                (post_id, viewer_user_id),
            )
        else:
            cursor.execute(
                """
                insert into likes (post_id, user_id)
                values (%s, %s)
                on conflict (post_id, user_id) do nothing
                """,
                (post_id, viewer_user_id),
            )
    connection.commit()
    return get_post_like_state(connection, post_id, viewer_user_id), None


def parse_data_url(data_url):
    match = re.match(r"^data:(?P<mime>[\w/+.-]+);base64,(?P<data>.+)$", data_url or "")
    if not match:
        raise ValueError("图片格式不支持，请换一张常见照片格式")
    mime = match.group("mime")
    if mime not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValueError("图片格式不支持，请换一张常见照片格式")
    try:
        raw = base64.b64decode(match.group("data"))
    except Exception as exc:
        raise ValueError("图片格式不支持，请换一张常见照片格式") from exc
    if len(raw) > MAX_PHOTO_BYTES:
        raise ValueError("图片太大，请换一张小一点的照片")
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
        body = exc.read().decode("utf-8", errors="ignore").lower()
        if exc.code == 413 or "too large" in body or "payload" in body:
            raise RuntimeError("图片太大，请换一张小一点的照片") from exc
        if exc.code in (401, 403):
            raise RuntimeError("图片上传失败，请稍后再试") from exc
        if exc.code == 415:
            raise RuntimeError("图片格式不支持，请换一张常见照片格式") from exc
        raise RuntimeError("图片上传失败，请稍后再试") from exc
    except error.URLError as exc:
        raise RuntimeError("图片上传失败，请稍后再试") from exc

    public_url = f"{os.environ['SUPABASE_URL'].rstrip('/')}/storage/v1/object/public/{BUCKET_NAME}/{object_path}"
    return object_path, public_url


def to_post_upload_warning(message):
    if "图片太大" in message:
        return "图片太大，请换一张小一点的照片；这顿饭已经先帮你记下了。"
    if "格式不支持" in message:
        return "图片格式不支持；这顿饭已经先帮你记下了。"
    return "图片没传上，但菜已经记录了。"


def serialize_match(row, audience, current_post, dish_dictionary=None):
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
        "cuisine_info": build_cuisine_info(row["dish"], dish_dictionary),
    }


def fetch_posts(connection, viewer_user_id=None):
    viewer_id = int(viewer_user_id or 0)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select
                posts.*,
                users.display_name,
                coalesce(like_counts.like_count, 0) as like_count,
                case
                    when %s > 0 and viewer_likes.user_id is not null then true
                    else false
                end as liked_by_me
            from posts
            join users on users.id = posts.user_id
            left join (
                select post_id, count(*)::bigint as like_count
                from likes
                group by post_id
            ) as like_counts on like_counts.post_id = posts.id
            left join likes as viewer_likes
                on viewer_likes.post_id = posts.id
                and viewer_likes.user_id = %s
            order by posts.created_at desc
            """,
            (viewer_id, viewer_id),
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


def serialize_like_state(row):
    return {
        "like_count": int(row.get("like_count") or 0),
        "liked_by_me": bool(row.get("liked_by_me")),
    }


def serialize_current_post(row, dish_dictionary=None):
    payload = {
        "id": row["id"],
        "user_id": row["user_id"],
        "dish": row["dish"],
        "note": row["note"] or "",
        "category": row["category"],
        "day": local_day_label(row.get("created_at")),
        "photo_data_url": row.get("photo_public_url"),
        "cuisine_info": build_cuisine_info(row["dish"], dish_dictionary),
    }
    payload.update(serialize_like_state(row))
    return payload


def serialize_matched_post(row, audience, current_post=None, dish_dictionary=None):
    payload = serialize_match(row, audience, current_post or row, dish_dictionary)
    payload["id"] = row["id"]
    payload["user_id"] = row["user_id"]
    payload["category"] = row["category"]
    payload["created_day"] = local_day_label(row.get("created_at"))
    payload.update(serialize_like_state(row))
    return payload


def serialize_public_post(row, dish_dictionary=None):
    created_at = coerce_datetime(row.get("created_at"))
    payload = {
        "id": row["id"],
        "user_id": row["user_id"],
        "display_name": row["display_name"],
        "dish": row["dish"],
        "note": row["note"] or "",
        "photo_public_url": row.get("photo_public_url"),
        "created_at": created_at.isoformat() if created_at else None,
        "category": row["category"],
        "cuisine_info": build_cuisine_info(row["dish"], dish_dictionary),
    }
    payload.update(serialize_like_state(row))
    return payload


def build_today_hot_dishes(posts, dish_dictionary=None):
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
        chosen = sorted_rows[0]
        hot_dishes.append({
            "post_id": chosen["id"],
            "user_id": chosen["user_id"],
            "dish": chosen["dish"],
            "category": chosen["category"],
            "count": len(sorted_rows),
            "user_names": unique_names[:3],
            "remaining_user_count": max(0, len(unique_names) - 3),
            "thumbnail": thumbnail,
            "cuisine_info": build_cuisine_info(chosen["dish"], dish_dictionary),
            "like_count": int(chosen.get("like_count") or 0),
            "liked_by_me": bool(chosen.get("liked_by_me")),
        })

    hot_dishes.sort(key=lambda item: (-item["count"], item["dish"]))
    return hot_dishes[:5]


def build_today_new_dishes(posts, dish_dictionary=None):
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
            "post_id": chosen["id"],
            "user_id": chosen["user_id"],
            "dish": chosen["dish"],
            "category": chosen["category"],
            "display_name": chosen["display_name"],
            "photo_public_url": chosen.get("photo_public_url"),
            "created_at": created_at.isoformat() if created_at else None,
            "note": chosen.get("note") or "",
            "cuisine_info": build_cuisine_info(chosen["dish"], dish_dictionary),
            "like_count": int(chosen.get("like_count") or 0),
            "liked_by_me": bool(chosen.get("liked_by_me")),
        })

    new_dishes.sort(key=lambda item: item["created_at"] or "", reverse=True)
    return new_dishes[:5]


def build_top_unknown_dishes(posts, dish_dictionary=None, days=30, limit=20):
    cutoff = now_today_local() - timedelta(days=days)
    grouped = {}

    for row in posts:
        created_at = coerce_datetime(row.get("created_at"))
        if not created_at:
            continue
        if created_at.astimezone(TODAY_TIMEZONE) < cutoff:
            continue

        cuisine_info = build_cuisine_info(row["dish"], dish_dictionary)
        if cuisine_info["cuisine"] != "其他家常":
            continue

        dish_key = normalize_text(row["dish"])
        if dish_key not in grouped:
            grouped[dish_key] = {"dish": row["dish"], "count": 0}
        grouped[dish_key]["count"] += 1

    return sorted(grouped.values(), key=lambda item: (-item["count"], item["dish"]))[:limit]


def build_unknown_dishes_payload(connection):
    posts = fetch_posts(connection)
    dish_dictionary = load_dish_dictionary(connection)
    return {
        "items": build_top_unknown_dishes(posts, dish_dictionary, days=30, limit=30),
    }


def build_learning_culture_options():
    options = []
    seen = set()

    for payload in DEFAULT_DISH_DICTIONARY.values():
        label = payload["culture"]
        if label not in seen:
            seen.add(label)
            options.append(label)

    for rule in FOOD_CULTURE_RULES:
        label = rule["label"]
        if label not in seen:
            seen.add(label)
            options.append(label)

    fallback = "🍚 其他家常"
    if fallback not in seen:
        options.append(fallback)
    return options


def build_grouped_matches(rows, audience, key_field, label_field, current_lookup=None, dish_dictionary=None):
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
                serialize_matched_post(row, audience, current_post or row, dish_dictionary)
                for row in sorted_rows
            ],
        })

    groups.sort(key=lambda group: group["count"], reverse=True)
    return groups


def build_public_feed(connection, user=None):
    posts = fetch_posts(connection, user["id"] if user else None)
    dish_dictionary = load_dish_dictionary(connection)
    today = now_today_local().date()
    today_posts = [row for row in posts if is_same_local_day(row.get("created_at"), today)]
    recent_posts = posts[:30]
    today_user_count = len({row["display_name"] for row in today_posts if row.get("display_name")})

    starters = [
        {
            "name": row["display_name"],
            "meta": f"刚发了 {row['dish']} · {(row['note'] or '今天更新了晚饭')[:18]}",
        }
        for row in recent_posts[:4]
    ]

    return {
        "updates_count": len(recent_posts),
        "today_posts_count": len(today_posts),
        "today_users_count": today_user_count,
        "today_posts": [serialize_public_post(row, dish_dictionary) for row in today_posts[:8]],
        "recent_posts": [serialize_public_post(row, dish_dictionary) for row in recent_posts],
        "today_hot_dishes": build_today_hot_dishes(posts, dish_dictionary),
        "today_new_dishes": build_today_new_dishes(posts, dish_dictionary),
        "starters": starters,
        "hero_points": ["先看看大家做了什么", "想发一顿时再登录", "撞菜和记录会在登录后开始"],
    }


def build_dashboard(connection, user):
    posts = fetch_posts(connection, user["id"])
    dish_dictionary = load_dish_dictionary(connection)
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
            serialize_matched_post(row, "同一道菜", current_post_by_dish.get(normalize_text(row["dish"])), dish_dictionary)
            for row in same_dish_rows
        ]
        same_style_matches = [
            serialize_matched_post(
                row,
                "同一类菜",
                next((post for post in current_user_posts if post["category"] == row["category"]), current_user_posts[0]),
                dish_dictionary,
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
                dish_dictionary=dish_dictionary,
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
                dish_dictionary=dish_dictionary,
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
        "today_hot_dishes": build_today_hot_dishes(posts, dish_dictionary),
        "today_new_dishes": build_today_new_dishes(posts, dish_dictionary),
        "weekly_matches": weekly_matches,
        "monthly_profiles": monthly_profiles,
        "hero_points": ["先写菜名", "再看今天撞上谁", "慢慢留下自己的记录"],
        "current_user_posts": [serialize_current_post(row, dish_dictionary) for row in current_user_posts],
        "matched_posts": matched_posts,
        "matched_users": [
            {"user_id": user_id, "display_name": display_name}
            for user_id, display_name in matched_users_map.items()
        ],
        "matched_dishes": list(matched_dishes_map.values()),
        "grouped_matches": grouped_matches,
    }


def build_profile(connection, user):
    posts = fetch_posts(connection, user["id"])
    dish_dictionary = load_dish_dictionary(connection)
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
            "id": row["id"],
            "user_id": row["user_id"],
            "day": local_day_label(row["created_at"]),
            "dish": row["dish"],
            "note": row["note"] or "今天记下了这顿饭。",
            "raw_note": row["note"] or "",
            "photo_public_url": row.get("photo_public_url"),
            "cuisine_info": build_cuisine_info(row["dish"], dish_dictionary),
        }
        for row in user_posts[:12]
    ]

    related_counts = {}
    for row in weekly_other:
        if row["category"] != top_category:
            continue
        uid = row["user_id"]
        if uid not in related_counts:
            related_counts[uid] = {"name": row["display_name"], "count": 0}
        related_counts[uid]["count"] += 1

    relationships = [
        {"user_id": uid, "name": data["name"], "meta": f"这周已经和你撞了 {data['count']} 次 {top_category}。"}
        for uid, data in sorted(related_counts.items(), key=lambda item: item[1]["count"], reverse=True)[:3]
    ]

    next_up = []
    seen = set()
    for row in monthly_other:
        if row["user_id"] in seen:
            continue
        seen.add(row["user_id"])
        next_up.append({
            "user_id": row["user_id"],
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


def build_learning_payload(connection):
    posts = fetch_posts(connection)
    dish_dictionary = load_dish_dictionary(connection)
    known_entries = sorted(
        dish_dictionary.values(),
        key=lambda item: (culture_label_to_name(item["label"]), item["dish"]),
    )
    return {
        "top_unknown_dishes": build_top_unknown_dishes(posts, dish_dictionary),
        "dish_dictionary": known_entries,
        "culture_options": build_learning_culture_options(),
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


@app.get("/learning")
def learning_page():
    return send_from_directory(ROOT, "learning.html")


@app.get("/learning.html")
def learning_html():
    return send_from_directory(ROOT, "learning.html")


@app.get("/admin/unknown-dishes")
def unknown_dishes_page():
    return send_from_directory(ROOT, "unknown-dishes.html")


@app.get("/admin/unknown-dishes.html")
def unknown_dishes_html():
    return send_from_directory(ROOT, "unknown-dishes.html")


@app.get("/styles.css")
def styles():
    return send_from_directory(ROOT, "styles.css")


@app.get("/app.js")
def app_js():
    return send_from_directory(ROOT, "app.js")


@app.get("/learning.js")
def learning_js():
    return send_from_directory(ROOT, "learning.js")


@app.get("/unknown-dishes.js")
def unknown_dishes_js():
    return send_from_directory(ROOT, "unknown-dishes.js")


@app.get("/manifest.json")
def manifest():
    return send_from_directory(ROOT, "manifest.json")


@app.get("/sw.js")
def service_worker():
    return send_from_directory(ROOT, "sw.js")


@app.get("/icons/<path:filename>")
def icons(filename):
    return send_from_directory(os.path.join(ROOT, "icons"), filename)


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
@app.get("/public_feed")
@app.get("/api/public-feed")
@app.get("/api/public_feed")
def public_feed():
    with pg_connection() as connection:
        user = current_user(connection)
        return jsonify(build_public_feed(connection, user))


@app.get("/api/admin/unknown-dishes")
def admin_unknown_dishes():
    with pg_connection() as connection:
        return jsonify(build_unknown_dishes_payload(connection))


@app.get("/api/admin/users")
def admin_users():
    with pg_connection() as connection:
        user = current_user(connection)
        if not user or not user.get("is_admin"):
            return jsonify({"error": "无权限"}), 403
        with connection.cursor() as cursor:
            cursor.execute("""
                select u.id, u.display_name, u.email, u.is_admin, u.created_at,
                       count(p.id)::bigint as post_count
                from users u
                left join posts p on p.user_id = u.id
                group by u.id, u.display_name, u.email, u.is_admin, u.created_at
                order by u.created_at desc
            """)
            users = [dict(row) for row in cursor.fetchall()]
        for u in users:
            if u.get("created_at"):
                u["created_at"] = u["created_at"].isoformat()
        return jsonify({"users": users})


@app.route("/api/learning", methods=["GET", "POST"])
def learning():
    with pg_connection() as connection:
        if flask_request.method == "GET":
            return jsonify(build_learning_payload(connection))

        user = current_user(connection)
        if not user:
            return jsonify({"error": "请先登录，再保存菜品知识"}), 401

        payload = flask_request.get_json(force=True, silent=True) or {}
        dish = (payload.get("dish") or "").strip()
        culture = (payload.get("culture") or "").strip()
        story = (payload.get("story") or "").strip()

        if not dish:
            return jsonify({"error": "请先填写菜名"}), 400
        if not culture:
            return jsonify({"error": "请先选择一个标签"}), 400
        if not story:
            return jsonify({"error": "请写一句小故事"}), 400

        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into dish_dictionary (dish_key, dish, culture, story, updated_at)
                values (%s, %s, %s, %s, now())
                on conflict (dish_key) do update
                set dish = excluded.dish,
                    culture = excluded.culture,
                    story = excluded.story,
                    updated_at = now()
                """,
                (normalize_text(dish), dish, culture, story),
            )
        connection.commit()

        return jsonify({
            "ok": True,
            "entry": dish_dictionary_entry(dish, culture, story),
            **build_learning_payload(connection),
        })


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

    response = jsonify({"user": {"id": user["id"], "display_name": user["display_name"], "email": user["email"], "is_admin": bool(user.get("is_admin", False))}})
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
    raw_posts = payload.get("posts")
    post_items = []

    if isinstance(raw_posts, list) and raw_posts:
        for item in raw_posts:
            if not isinstance(item, dict):
                continue
            dish = (item.get("dish") or "").strip()
            note = (item.get("note") or "").strip()
            photo_data_url = item.get("photo_data_url")
            if not dish:
                return jsonify({"error": "每张照片都要先写好菜名"}), 400
            post_items.append({
                "dish": dish,
                "note": note,
                "photo_data_url": photo_data_url,
            })
    else:
        dish_input = (payload.get("dish") or "").strip()
        note = (payload.get("note") or "").strip()
        photo_data_url = payload.get("photo_data_url")
        dishes = split_dishes(dish_input)

        if not dishes:
            return jsonify({"error": "请先写下今天做了什么"}), 400

        post_items = [
            {
                "dish": dish,
                "note": note,
                "photo_data_url": photo_data_url,
            }
            for dish in dishes
        ]

    with pg_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify({"error": "登录状态过期，请重新登录"}), 401
        dish_dictionary = load_dish_dictionary(connection)

        warnings = []
        created_posts = []

        try:
            with connection.cursor() as cursor:
                for item in post_items:
                    dish = item["dish"]
                    note = item["note"]
                    photo_data_url = item.get("photo_data_url")
                    photo_path = None
                    photo_public_url = None
                    created_at = now_utc()

                    if photo_data_url:
                        try:
                            photo_path, photo_public_url = upload_to_storage(user["id"], photo_data_url)
                        except Exception as exc:
                            warnings.append(f"{dish}：{to_post_upload_warning(str(exc))}")

                    cursor.execute(
                        """
                        insert into posts (user_id, dish, note, photo_path, photo_public_url, category, created_at)
                        values (%s, %s, %s, %s, %s, %s, %s)
                        returning id
                        """,
                        (
                            user["id"],
                            dish,
                            note,
                            photo_path,
                            photo_public_url,
                            infer_category(dish, note, dish_dictionary),
                            created_at,
                        ),
                    )
                    created_row = cursor.fetchone()
                    created_posts.append({
                        "id": created_row["id"] if created_row else None,
                        "dish": dish,
                        "note": note,
                        "photo_public_url": photo_public_url,
                        "cuisine_info": build_cuisine_info(dish, dish_dictionary),
                    })
            connection.commit()
        except Exception:
            return jsonify({"error": "服务器暂时开小差了，请稍后再试"}), 500

    return jsonify({
        "ok": True,
        "warning": "；".join(warnings) if warnings else None,
        "created_count": len(post_items),
        "created_posts": created_posts,
        "created_cuisine_info": [
            {"dish": item["dish"], "cuisine_info": build_cuisine_info(item["dish"], dish_dictionary)}
            for item in post_items[:2]
        ],
    })


def delete_post():
    payload = flask_request.get_json(force=True, silent=True) or {}
    try:
        post_id = int(payload.get("post_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "找不到这道菜"}), 400

    with pg_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify({"error": "请先登录"}), 401
        with connection.cursor() as cursor:
            cursor.execute("select id, user_id from posts where id = %s", (post_id,))
            post = cursor.fetchone()
        if not post:
            return jsonify({"error": "这道菜已经不在了"}), 404
        if post["user_id"] != user["id"]:
            return jsonify({"error": "只能删除自己的记录"}), 403
        with connection.cursor() as cursor:
            cursor.execute("delete from posts where id = %s", (post_id,))
        connection.commit()
    return jsonify({"ok": True, "post_id": post_id})


def update_post():
    payload = flask_request.get_json(force=True, silent=True) or {}
    try:
        post_id = int(payload.get("post_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "找不到这道菜"}), 400

    dish = (payload.get("dish") or "").strip()
    note = (payload.get("note") or "").strip()

    if not dish:
        return jsonify({"error": "请先填写菜名"}), 400

    with pg_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify({"error": "请先登录"}), 401
        with connection.cursor() as cursor:
            cursor.execute("select id, user_id from posts where id = %s", (post_id,))
            post = cursor.fetchone()
        if not post:
            return jsonify({"error": "这道菜已经不在了"}), 404
        if post["user_id"] != user["id"]:
            return jsonify({"error": "只能编辑自己的记录"}), 403
        dish_dictionary = load_dish_dictionary(connection)
        new_category = infer_category(dish, note, dish_dictionary)
        with connection.cursor() as cursor:
            cursor.execute(
                "update posts set dish = %s, note = %s, category = %s where id = %s",
                (dish, note, new_category, post_id),
            )
        connection.commit()
    return jsonify({"ok": True, "post_id": post_id})


@app.post("/like_post")
@app.post("/api/like_post")
def like_post():
    payload = flask_request.get_json(force=True, silent=True) or {}
    try:
        post_id = int(payload.get("post_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "请先选中一道菜再点赞"}), 400

    with pg_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify({"error": "请先登录，再给别人点赞"}), 401

        like_state, error_message = toggle_post_like(connection, post_id, user["id"])
        if error_message:
            status = 404 if "不见了" in error_message else 400
            return jsonify({"error": error_message}), status

    return jsonify({
        "ok": True,
        "post_id": post_id,
        "like_count": like_state["like_count"],
        "liked_by_me": like_state["liked_by_me"],
    })


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


@app.delete("/posts")
@app.delete("/api/posts")
def delete_post_route():
    return delete_post()


@app.patch("/posts")
@app.patch("/api/posts")
def update_post_route():
    return update_post()


if os.environ.get("SUPABASE_DB_URL"):
    ensure_schema()
