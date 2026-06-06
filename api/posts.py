from flask import Flask

from backend import create_post as create_post_handler


app = Flask(__name__)
application = app


@app.post("/")
@app.post("/api/posts")
def posts():
    return create_post_handler()
