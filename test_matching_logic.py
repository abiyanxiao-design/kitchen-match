from datetime import datetime, timezone

from backend import build_dashboard


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, query):
        self.query = query

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self):
        return FakeCursor(self.rows)


def run_test():
    now = datetime.now(timezone.utc)
    rows = [
        {
            "id": 2,
            "user_id": 2,
            "display_name": "B",
            "dish": "番茄炒蛋",
            "note": "B 今天也做了",
            "photo_public_url": None,
            "category": "家常炒菜",
            "created_at": now,
        },
        {
            "id": 1,
            "user_id": 1,
            "display_name": "A",
            "dish": "番茄炒蛋",
            "note": "A 今天做了",
            "photo_public_url": None,
            "category": "家常炒菜",
            "created_at": now,
        },
    ]

    dashboard_a = build_dashboard(FakeConnection(rows), {"id": 1, "display_name": "A"})
    dashboard_b = build_dashboard(FakeConnection(rows), {"id": 2, "display_name": "B"})

    assert dashboard_a["matched_dishes"] == ["番茄炒蛋"]
    assert dashboard_b["matched_dishes"] == ["番茄炒蛋"]
    assert dashboard_a["matched_users"][0]["display_name"] == "B"
    assert dashboard_b["matched_users"][0]["display_name"] == "A"
    assert dashboard_a["same_dish_matches"], "A 应该看到撞菜"
    assert dashboard_b["same_dish_matches"], "B 应该看到撞菜"
    print("matching test passed")


if __name__ == "__main__":
    run_test()
