"""Authentication routes and role decorator."""

from __future__ import annotations

import logging
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError

from extensions import db, login_manager
from models import User

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError, SQLAlchemyError):
        logger.exception("user_loader failed for id=%s", user_id)
        return None


def role_required(*roles: str):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                flash("You do not have permission for that action.", "error")
                return redirect(url_for("today.dashboard"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("today.dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        try:
            user = User.query.filter(db.func.lower(User.email) == email).first()
        except (OperationalError, ProgrammingError) as exc:
            # Typical on Vercel when DATABASE_URL is missing, wrong, or schema not seeded.
            logger.exception("login database error")
            flash(
                "Cannot reach the database. On Vercel, set DATABASE_URL (Postgres with "
                "sslmode=require) and SECRET_KEY, then run init-db + seed-demo — or set "
                "INIT_DB_ON_BOOT=1 once. Details: /health",
                "error",
            )
            return render_template("auth/login.html"), 503
        except SQLAlchemyError:
            logger.exception("login unexpected sqlalchemy error")
            flash("Sign-in failed due to a server database error. Check /health.", "error")
            return render_template("auth/login.html"), 503

        if not user or not user.check_password(password) or not user.is_active:
            flash("Invalid email or password.", "error")
        else:
            login_user(user, remember=True)
            return redirect(request.args.get("next") or url_for("today.dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    flash("Signed out.", "success")
    return redirect(url_for("auth.login"))
