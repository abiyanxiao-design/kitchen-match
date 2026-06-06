from flask import Flask

from backend import logout as logout_handler


app = Flask(__name__)
application = app


@app.route("/", defaults={"_path": ""}, methods=["POST"])
@app.route("/<path:_path>", methods=["POST"])
def logout(_path):
    return logout_handler()
