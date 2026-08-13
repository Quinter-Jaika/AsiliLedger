from flask import Flask
from config import Config
from models import db
from auth import init_auth
from routes import init_routes

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    init_auth(app)
    init_routes(app)
    with app.app_context():
        db.create_all()  # create tables on first run
    return app

if __name__ == "__main__":
    create_app().run(debug=True)