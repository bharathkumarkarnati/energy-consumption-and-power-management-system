from flask import Flask
from config import Config
from .extensions import db


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    from . import models
    from .routes import bp
    app.register_blueprint(bp)
    with app.app_context():
        db.create_all()
        from .seed import seed_data
        seed_data()
    return app
