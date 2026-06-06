from flask import Flask, jsonify


app = Flask(__name__)
application = app


@app.route("/", defaults={"_path": ""}, methods=["GET"])
@app.route("/<path:_path>", methods=["GET"])
def api_root(_path):
    return jsonify({"ok": True, "service": "kitchen-match api"})
