from flask import Flask

from backend import me as me_handler


app = Flask(__name__)
application = app


@app.get("/")
@app.get("/api/me")
def me():
    return me_handler()
