from flask import Flask

from backend import public_feed as public_feed_handler


app = Flask(__name__)
application = app


@app.route("/", defaults={"_path": ""}, methods=["GET"])
@app.route("/<path:_path>", methods=["GET"])
def public_feed(_path):
    return public_feed_handler()
