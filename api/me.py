from flask import Flask

from backend import me as me_handler


app = Flask(__name__)
application = app


@app.route("/", defaults={"_path": ""}, methods=["GET"])
@app.route("/<path:_path>", methods=["GET"])
def me(_path):
    return me_handler()
