import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("KITCHEN_DATA_DIR", ROOT / "data")).resolve()
DB_PATH = DATA_DIR / "kitchen.sqlite3"
SESSION_COOKIE = "kitchen_session"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def local_day_label(iso_string):
    created_at = datetime.fromisoformat(iso_string)
    today = datetime.now(timezone.utc).date()
    days = (today - created_at.date()).days
    if days <= 0:
        return "今天"
    if days == 1:
        return "昨天"
    if days < 7:
        return f"{days} 天前"
    return created_at.strftime("%m-%d")


def normalize_text(value):
    return "".join((value or "").strip().lower().split())


def infer_category(dish, note):
    text = f"{dish} {note}".lower()
    if any(keyword in text for keyword in ["汤", "炖", "煲", "排骨", "海带"]):
        return "汤菜"
    if any(keyword in text for keyword in ["面", "粉", "饺", "馄饨"]):
        return "面食"
    if any(keyword in text for keyword in ["炒", "青菜", "鸡蛋", "豆角", "豆苗"]):
        return "家常炒菜"
    if any(keyword in text for keyword in ["剩", "快手", "简单"]):
        return "快手晚饭"
    return "家常晚饭"


def ensure_database():
    DATA_DIR.mkdir(exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.executescript(
        """
        create table if not exists users (
            id integer primary key autoincrement,
            display_name text not null,
            email text not null unique,
            password_hash text not null,
            password_salt text not null,
            created_at text not null
        );

        create table if not exists sessions (
            token text primary key,
            user_id integer not null references users(id) on delete cascade,
            created_at text not null
        );

        create table if not exists posts (
            id integer primary key autoincrement,
            user_id integer not null references users(id) on delete cascade,
            dish text not null,
            note text not null default '',
            photo_data_url text,
            category text not null,
            created_at text not null
        );
        """
    )
    connection.commit()
    seed_demo_data(connection)
    connection.close()


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
    cursor = connection.execute(
        """
        insert into users (display_name, email, password_hash, password_salt, created_at)
        values (?, ?, ?, ?, ?)
        """,
        (display_name, email.lower(), password_hash, salt, now_iso()),
    )
    connection.commit()
    return cursor.lastrowid


def seed_demo_data(connection):
    connection.row_factory = sqlite3.Row
    existing = connection.execute("select count(*) as count from users").fetchone()["count"]
    if existing:
        return

    demo_users = [
        ("周叔", "zhou@example.com"),
        ("Maggie 阿姨", "maggie@example.com"),
        ("陈叔", "chen@example.com"),
        ("Wendy", "wendy@example.com"),
    ]
    user_ids = {}
    for name, email in demo_users:
        user_id = create_user(connection, name, email, "demo1234")
        user_ids[name] = user_id

    demo_posts = [
        ("周叔", "萝卜排骨汤", "今天萝卜炖得更透了，汤也更甜。", None, datetime.now(timezone.utc) - timedelta(hours=2)),
        ("Maggie 阿姨", "萝卜排骨汤", "她今天也炖了萝卜排骨汤，还说这两天气温一降就特别想喝热汤。", None, datetime.now(timezone.utc) - timedelta(hours=1, minutes=20)),
        ("陈叔", "海带排骨汤", "不是同一道菜，但也是慢炖的汤菜。", None, datetime.now(timezone.utc) - timedelta(hours=1)),
        ("Wendy", "番茄鸡蛋面", "今天也是快手热乎的一顿。", None, datetime.now(timezone.utc) - timedelta(minutes=40)),
        ("周叔", "土豆烧鸡", "这是最近回应最多的一道，已经有两个人说下周要试。", None, datetime.now(timezone.utc) - timedelta(days=3)),
        ("周叔", "白菜炖粉条", "很普通的一顿，但正因为普通，反而让人觉得特别像家里。", None, datetime.now(timezone.utc) - timedelta(days=7)),
        ("Maggie 阿姨", "海带排骨汤", "这周又撞上了一次汤菜。", None, datetime.now(timezone.utc) - timedelta(days=2)),
    ]

    for author, dish, note, photo_data_url, created_at in demo_posts:
        connection.execute(
            """
            insert into posts (user_id, dish, note, photo_data_url, category, created_at)
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                user_ids[author],
                dish,
                note,
                photo_data_url,
                infer_category(dish, note),
                created_at.isoformat(),
            ),
        )
    connection.commit()


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def create_session(connection, user_id):
    token = secrets.token_urlsafe(32)
    connection.execute(
        "insert into sessions (token, user_id, created_at) values (?, ?, ?)",
        (token, user_id, now_iso()),
    )
    connection.commit()
    return token


def delete_session(connection, token):
    connection.execute("delete from sessions where token = ?", (token,))
    connection.commit()


def fetch_user_by_session(connection, token):
    if not token:
        return None
    return connection.execute(
        """
        select users.id, users.display_name, users.email
        from sessions
        join users on users.id = sessions.user_id
        where sessions.token = ?
        """,
        (token,),
    ).fetchone()


def serialize_match(row, audience, current_category):
    comments = []
    if normalize_text(row["dish"]) == normalize_text(current_category["dish"]):
        comments.append("你今天也做这个？")
        comments.append("这一顿一看就能聊起来。")
    else:
        comments.append("虽然不是同一道菜，但感觉是一类晚饭。")
    return {
        "author": row["display_name"],
        "dish": row["dish"],
        "note": row["note"] or "今天也做了这一顿。",
        "audience": audience,
        "comments": comments,
        "photo_data_url": row["photo_data_url"],
    }


def build_dashboard(connection, user):
    posts = connection.execute(
        """
        select posts.*, users.display_name
        from posts
        join users on users.id = posts.user_id
        order by datetime(posts.created_at) desc
        """
    ).fetchall()

    user_posts = [row for row in posts if row["user_id"] == user["id"]]
    current_post = user_posts[0] if user_posts else None
    starters = [
        {
            "name": row["display_name"],
            "meta": f"刚发了 {row['dish']} · {row['note'][:18] or '今天更新了晚饭'}",
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
        current_category = current_post["category"]
        same_dish_rows = [
            row for row in posts
            if row["user_id"] != user["id"] and normalize_text(row["dish"]) == normalized_dish
        ]
        same_style_rows = [
            row for row in posts
            if row["user_id"] != user["id"] and row["category"] == current_category and normalize_text(row["dish"]) != normalized_dish
        ]
        same_dish_matches = [serialize_match(row, "同一道菜", current_post) for row in same_dish_rows[:3]]
        same_style_matches = [serialize_match(row, "同一类菜", current_post) for row in same_style_rows[:4]]

        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        weekly_counts = {}
        for row in posts:
            created_at = datetime.fromisoformat(row["created_at"])
            if row["user_id"] == user["id"] or created_at < week_ago:
                continue
            if row["category"] != current_category:
                continue
            weekly_counts.setdefault(row["display_name"], {"count": 0, "display_name": row["display_name"]})
            weekly_counts[row["display_name"]]["count"] += 1
        weekly_matches = [
            {
                "name": item["display_name"],
                "meta": f"这周已经和你撞了 {item['count']} 次 {current_category}。",
            }
            for item in sorted(weekly_counts.values(), key=lambda item: item["count"], reverse=True)[:3]
        ]

        monthly_profiles = [
            f"这个月你最常撞上的是 {current_category}。",
            "最容易和你撞上的人，通常也在晚饭前后做饭。",
            f"最近只要你发 {current_category}，就更容易有人回你。",
        ]

    return {
        "updates_count": len(posts),
        "starters": starters,
        "same_dish_matches": same_dish_matches,
        "same_style_matches": same_style_matches,
        "weekly_matches": weekly_matches,
        "monthly_profiles": monthly_profiles,
        "hero_points": [
            "先写菜名",
            "再看今天撞上谁",
            "慢慢留下自己的记录",
        ],
    }


def build_profile(connection, user):
    posts = connection.execute(
        """
        select posts.*, users.display_name
        from posts
        join users on users.id = posts.user_id
        order by datetime(posts.created_at) desc
        """
    ).fetchall()
    user_posts = [row for row in posts if row["user_id"] == user["id"]]
    categories = {}
    for row in user_posts:
      categories[row["category"]] = categories.get(row["category"], 0) + 1

    top_category = max(categories.items(), key=lambda item: item[1])[0] if categories else "家常晚饭"
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    month_ago = datetime.now(timezone.utc) - timedelta(days=30)
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

    seen_names = {}
    for row in weekly_other:
        if row["category"] != top_category:
            continue
        seen_names.setdefault(row["display_name"], 0)
        seen_names[row["display_name"]] += 1

    relationships = [
        {"name": name, "meta": f"这周已经和你撞了 {count} 次 {top_category}。"}
        for name, count in sorted(seen_names.items(), key=lambda item: item[1], reverse=True)[:3]
    ]

    next_up_rows = [row for row in monthly_other if row["display_name"] not in seen_names]
    next_up = []
    picked = set()
    for row in next_up_rows:
        if row["display_name"] in picked:
            continue
        picked.add(row["display_name"])
        next_up.append({
            "name": row["display_name"],
            "meta": f"最近做了 {row['dish']}，晚饭节奏和你挺像。",
        })
        if len(next_up) == 3:
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


class KitchenHandler(BaseHTTPRequestHandler):
    server_version = "KitchenServer/0.1"

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        print("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def send_json(self, status_code, payload, set_cookie=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie.OutputString())
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path):
        if not path.exists():
            self.send_error(404)
            return
        content = path.read_bytes()
        suffix = path.suffix
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
        }.get(suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def get_session_token(self):
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None
        jar = cookies.SimpleCookie()
        jar.load(cookie_header)
        morsel = jar.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def current_user(self, connection):
        return fetch_user_by_session(connection, self.get_session_token())

    def require_user(self, connection):
        user = self.current_user(connection)
        if not user:
            self.send_json(401, {"error": "请先登录"})
            return None
        return user

    def session_cookie(self, token):
        jar = cookies.SimpleCookie()
        jar[SESSION_COOKIE] = token
        jar[SESSION_COOKIE]["path"] = "/"
        jar[SESSION_COOKIE]["httponly"] = True
        jar[SESSION_COOKIE]["samesite"] = "Lax"
        jar[SESSION_COOKIE]["max-age"] = 60 * 60 * 24 * 30
        return jar[SESSION_COOKIE]

    def clear_cookie(self):
        jar = cookies.SimpleCookie()
        jar[SESSION_COOKIE] = ""
        jar[SESSION_COOKIE]["path"] = "/"
        jar[SESSION_COOKIE]["max-age"] = 0
        return jar[SESSION_COOKIE]

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/", "/index.html"]:
            return self.send_file(ROOT / "index.html")
        if parsed.path == "/styles.css":
            return self.send_file(ROOT / "styles.css")
        if parsed.path == "/app.js":
            return self.send_file(ROOT / "app.js")
        if parsed.path == "/health":
            return self.send_json(200, {"ok": True})

        connection = get_connection()
        try:
            if parsed.path == "/api/me":
                user = self.current_user(connection)
                if not user:
                    return self.send_json(401, {"error": "未登录"})
                return self.send_json(200, {"user": dict(user)})
            if parsed.path == "/api/dashboard":
                user = self.require_user(connection)
                if not user:
                    return
                return self.send_json(200, build_dashboard(connection, user))
            if parsed.path == "/api/profile":
                user = self.require_user(connection)
                if not user:
                    return
                return self.send_json(200, build_profile(connection, user))
            self.send_error(404)
        finally:
            connection.close()

    def do_POST(self):
        parsed = urlparse(self.path)
        connection = get_connection()
        try:
            if parsed.path == "/api/register":
                payload = self.read_json()
                display_name = (payload.get("display_name") or "").strip()
                email = (payload.get("email") or "").strip().lower()
                password = payload.get("password") or ""
                if len(display_name) < 2 or "@" not in email or len(password) < 6:
                    return self.send_json(400, {"error": "请填写正确的称呼、邮箱和至少 6 位密码"})
                exists = connection.execute("select id from users where email = ?", (email,)).fetchone()
                if exists:
                    return self.send_json(400, {"error": "这个邮箱已经注册过了"})
                user_id = create_user(connection, display_name, email, password)
                token = create_session(connection, user_id)
                user = connection.execute("select id, display_name, email from users where id = ?", (user_id,)).fetchone()
                return self.send_json(200, {"user": dict(user)}, set_cookie=self.session_cookie(token))

            if parsed.path == "/api/login":
                payload = self.read_json()
                email = (payload.get("email") or "").strip().lower()
                password = payload.get("password") or ""
                user = connection.execute("select * from users where email = ?", (email,)).fetchone()
                if not user:
                    return self.send_json(400, {"error": "邮箱或密码不对"})
                expected = hash_password(password, user["password_salt"])
                if not hmac.compare_digest(expected, user["password_hash"]):
                    return self.send_json(400, {"error": "邮箱或密码不对"})
                token = create_session(connection, user["id"])
                safe_user = {"id": user["id"], "display_name": user["display_name"], "email": user["email"]}
                return self.send_json(200, {"user": safe_user}, set_cookie=self.session_cookie(token))

            if parsed.path == "/api/logout":
                token = self.get_session_token()
                if token:
                    delete_session(connection, token)
                return self.send_json(200, {"ok": True}, set_cookie=self.clear_cookie())

            if parsed.path == "/api/posts":
                user = self.require_user(connection)
                if not user:
                    return
                payload = self.read_json()
                dish = (payload.get("dish") or "").strip()
                note = (payload.get("note") or "").strip()
                photo_data_url = payload.get("photo_data_url")
                if not dish:
                    return self.send_json(400, {"error": "请先写下今天做了什么"})
                if photo_data_url and not str(photo_data_url).startswith("data:image/"):
                    return self.send_json(400, {"error": "图片格式不对"})
                connection.execute(
                    """
                    insert into posts (user_id, dish, note, photo_data_url, category, created_at)
                    values (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user["id"],
                        dish,
                        note,
                        photo_data_url,
                        infer_category(dish, note),
                        now_iso(),
                    ),
                )
                connection.commit()
                return self.send_json(200, {"ok": True})

            self.send_error(404)
        finally:
            connection.close()


def main():
    ensure_database()
    host = os.environ.get("KITCHEN_HOST", "0.0.0.0")
    port = int(os.environ.get("KITCHEN_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), KitchenHandler)
    print(f"Kitchen server running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
