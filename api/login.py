from flask import Flask

from backend import login as login_handler


app = Flask(__name__)
application = app


@app.post("/")
@app.post("/api/login")
def login():
    return login_handler()
