from flask import Flask

from backend import register as register_handler


app = Flask(__name__)
application = app


@app.route("/", defaults={"_path": ""}, methods=["POST"])
@app.route("/<path:_path>", methods=["POST"])
def register(_path):
    return register_handler()
