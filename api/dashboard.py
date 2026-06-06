from flask import Flask

from backend import dashboard as dashboard_handler


app = Flask(__name__)
application = app


@app.route("/", defaults={"_path": ""}, methods=["GET"])
@app.route("/<path:_path>", methods=["GET"])
def dashboard(_path):
    return dashboard_handler()
