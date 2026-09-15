"""Equipment Readiness application factory."""

from __future__ import annotations

import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask
from flask_login import current_user

from extensions import db, login_manager


def create_app(config: dict | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__)

    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://er_pilot:er_pilot_dev@127.0.0.1:5432/equipment_readiness_pilot",
    )
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key-change-me"),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        REMEMBER_COOKIE_DURATION=timedelta(days=7),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "error"

    from blueprints.auth import auth_bp
    from blueprints.equipment import equipment_bp
    from blueprints.jobs import jobs_bp
    from blueprints.legacy import legacy_bp
    from blueprints.today import today_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(today_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(legacy_bp)

    @app.context_processor
    def inject_globals():
        return {"current_user": current_user, "app_name": "Equipment Readiness"}

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; "
            "style-src 'self' https://cdn.jsdelivr.net https://unpkg.com https://fonts.googleapis.com 'unsafe-inline'; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' https://*.tile.openstreetmap.org data:; "
            "connect-src 'self';"
        )
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.cli.command("init-db")
    def init_db_command():
        import models  # noqa: F401

        db.create_all()
        print("tables created")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        from seed import seed_demo_data

        seed_demo_data()
        print("demo data loaded")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
