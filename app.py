"""Equipment Readiness application factory."""

from __future__ import annotations

import logging
import os
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_login import current_user
from sqlalchemy.pool import NullPool

from extensions import db, login_manager

logger = logging.getLogger(__name__)


def _normalize_database_url(url: str) -> str:
    """Normalize hosted Postgres URLs for SQLAlchemy + serverless."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))

    # Hosted providers require TLS; local Docker/Postgres usually does not.
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if host and host not in local_hosts and "sslmode" not in query:
        query["sslmode"] = "require"

    return urlunparse(parsed._replace(query=urlencode(query)))


def create_app(config: dict | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__)

    raw_database_url = (os.environ.get("DATABASE_URL") or "").strip()
    on_vercel = bool(os.environ.get("VERCEL"))

    if not raw_database_url:
        # Never silently fall back to localhost on Vercel — that always 500s.
        if on_vercel:
            logger.error("DATABASE_URL is not set on Vercel")
        raw_database_url = (
            "postgresql://er_pilot:er_pilot_dev@127.0.0.1:5432/equipment_readiness_pilot"
        )

    database_url = _normalize_database_url(raw_database_url)

    engine_options: dict = {"pool_pre_ping": True}
    # Serverless functions should not keep persistent connection pools.
    if on_vercel or os.environ.get("SQLALCHEMY_NULL_POOL") == "1":
        engine_options["poolclass"] = NullPool

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key-change-me"),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS=engine_options,
        REMEMBER_COOKIE_DURATION=timedelta(days=7),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=on_vercel,
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

    @app.get("/health")
    def health():
        """Lightweight probe for Vercel / ops — no secrets returned."""
        db_ok = False
        db_error = None
        user_count = None
        try:
            from sqlalchemy import text

            db.session.execute(text("SELECT 1"))
            db_ok = True
            from models import User

            user_count = User.query.count()
        except Exception as exc:  # noqa: BLE001 - surface safe summary only
            db_error = type(exc).__name__
            logger.exception("health check database failure")

        status = 200 if db_ok else 503
        return (
            jsonify(
                {
                    "ok": db_ok,
                    "database": "up" if db_ok else "down",
                    "error": db_error,
                    "users": user_count,
                    "vercel": on_vercel,
                }
            ),
            status,
        )

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

    # Optional one-shot bootstrap for empty hosted DBs (pilot only).
    if os.environ.get("INIT_DB_ON_BOOT") == "1":
        with app.app_context():
            try:
                import models  # noqa: F401
                from seed import seed_demo_data

                db.create_all()
                seed_demo_data()
                logger.info("INIT_DB_ON_BOOT completed")
            except Exception:
                logger.exception("INIT_DB_ON_BOOT failed")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
