from flask import Flask

from backend import admin_users as admin_users_handler


app = Flask(__name__)
application = app


@app.route("/", defaults={"_path": ""}, methods=["GET"])
@app.route("/<path:_path>", methods=["GET"])
def users(_path):
    return admin_users_handler()
