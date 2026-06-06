from flask import Flask

from backend import create_post as create_post_handler


app = Flask(__name__)
application = app


@app.route("/", defaults={"_path": ""}, methods=["POST"])
@app.route("/<path:_path>", methods=["POST"])
def posts(_path):
    return create_post_handler()
