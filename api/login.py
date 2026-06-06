from flask import Flask

from backend import login as login_handler


app = Flask(__name__)
application = app


@app.route("/", defaults={"_path": ""}, methods=["POST"])
@app.route("/<path:_path>", methods=["POST"])
def login(_path):
    return login_handler()
