from flask import Flask, jsonify


app = Flask(__name__)
application = app


@app.get("/")
@app.get("/api")
def api_root():
    return jsonify({"ok": True, "service": "kitchen-match api"})
