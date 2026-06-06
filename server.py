import os

from backend import app


if __name__ == "__main__":
    host = os.environ.get("KITCHEN_HOST", "127.0.0.1")
    port = int(os.environ.get("KITCHEN_PORT", "8787"))
    app.run(host=host, port=port, debug=False)
