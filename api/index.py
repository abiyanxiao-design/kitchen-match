from backend import app as flask_app


# Vercel's Flask runtime looks for a top-level `app`.
app = flask_app
application = app
