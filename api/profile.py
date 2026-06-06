from flask import Flask

from backend import profile as profile_handler


app = Flask(__name__)
application = app


@app.get("/")
@app.get("/api/profile")
def profile():
    return profile_handler()
