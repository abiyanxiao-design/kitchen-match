from flask import Flask

from backend import health as health_handler


app = Flask(__name__)
application = app


@app.get("/")
@app.get("/api/health")
def health():
    return health_handler()
