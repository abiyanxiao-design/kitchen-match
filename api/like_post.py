from flask import Flask

from backend import like_post as like_post_handler


app = Flask(__name__)
application = app


@app.route("/", defaults={"_path": ""}, methods=["POST"])
@app.route("/<path:_path>", methods=["POST"])
def like_post(_path):
    return like_post_handler()
