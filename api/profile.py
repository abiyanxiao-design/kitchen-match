from flask import Flask

from backend import profile as profile_handler


app = Flask(__name__)
application = app


@app.route("/", defaults={"_path": ""}, methods=["GET"])
@app.route("/<path:_path>", methods=["GET"])
def profile(_path):
    return profile_handler()
