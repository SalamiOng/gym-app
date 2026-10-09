import os
from pathlib import Path

from flask import Flask, render_template

from . import db
from .icons import icon
from .navigation import NAV_ITEMS


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        # Needed for flash messages. Set a real SECRET_KEY env var outside local development.
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        DATABASE=str(Path(app.instance_path) / "gym.sqlite3"),
    )
    if test_config:
        app.config.update(test_config)

    app.jinja_env.globals["icon"] = icon
    app.jinja_env.globals["nav_items"] = NAV_ITEMS
    app.jinja_env.filters["weight"] = lambda value: f"{value:g}"
    # Nutrition numbers: at most one decimal place, with thousands separators (1,850 or 32.5).
    app.jinja_env.filters["amount"] = lambda value: f"{round(value, 1):,g}"

    db.init_app(app)

    from .views import bp

    app.register_blueprint(bp)

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("pages/not_found.html"), 404

    return app
