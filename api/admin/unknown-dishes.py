from flask import Flask

from backend import admin_unknown_dishes as admin_unknown_dishes_handler


app = Flask(__name__)
application = app


@app.route("/", defaults={"_path": ""}, methods=["GET"])
@app.route("/<path:_path>", methods=["GET"])
def unknown_dishes(_path):
    return admin_unknown_dishes_handler()
