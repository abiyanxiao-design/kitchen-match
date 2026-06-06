from flask import Flask

from backend import health as health_handler


app = Flask(__name__)
application = app


@app.route("/", defaults={"_path": ""}, methods=["GET"])
@app.route("/<path:_path>", methods=["GET"])
def health(_path):
    return health_handler()
