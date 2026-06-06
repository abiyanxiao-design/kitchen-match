from flask import Flask

from backend import dashboard as dashboard_handler


app = Flask(__name__)
application = app


@app.get("/")
@app.get("/api/dashboard")
def dashboard():
    return dashboard_handler()
