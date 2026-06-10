from flask import Flask

from backend import create_post as create_post_handler
from backend import delete_post as delete_post_handler
from backend import update_post as update_post_handler


app = Flask(__name__)
application = app


@app.route("/", defaults={"_path": ""}, methods=["POST"])
@app.route("/<path:_path>", methods=["POST"])
def posts_create(_path):
    return create_post_handler()


@app.route("/", defaults={"_path": ""}, methods=["DELETE"])
@app.route("/<path:_path>", methods=["DELETE"])
def posts_delete(_path):
    return delete_post_handler()


@app.route("/", defaults={"_path": ""}, methods=["PATCH"])
@app.route("/<path:_path>", methods=["PATCH"])
def posts_update(_path):
    return update_post_handler()
