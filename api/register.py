from flask import Flask

from backend import register as register_handler


app = Flask(__name__)
application = app


@app.post("/")
@app.post("/api/register")
def register():
    return register_handler()
