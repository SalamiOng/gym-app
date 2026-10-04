from flask import Flask

from .icons import icon
from .navigation import NAV_ITEMS


def create_app() -> Flask:
    app = Flask(__name__)

    app.jinja_env.globals["icon"] = icon
    app.jinja_env.globals["nav_items"] = NAV_ITEMS

    from .views import bp

    app.register_blueprint(bp)

    @app.errorhandler(404)
    def not_found(_error):
        from flask import render_template

        return render_template("pages/not_found.html"), 404

    return app
