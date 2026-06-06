from flask import Flask

from backend import logout as logout_handler


app = Flask(__name__)
application = app


@app.post("/")
@app.post("/api/logout")
def logout():
    return logout_handler()
