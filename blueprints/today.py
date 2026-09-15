"""Today board."""

from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, render_template
from flask_login import login_required

from models import FollowUpAction, Job
from services.readiness import evaluate_job_readiness, sync_follow_up_actions

today_bp = Blueprint("today", __name__)


@today_bp.route("/")
@login_required
def dashboard():
    now = datetime.utcnow()
    jobs = (
        Job.query.filter(
            Job.status.in_(("planned", "active")),
            Job.starts_at <= now + timedelta(days=2),
            Job.ends_at >= now - timedelta(hours=12),
        )
        .order_by(Job.starts_at)
        .all()
    )
    cards = []
    for job in jobs:
        result = evaluate_job_readiness(job, now=now)
        sync_follow_up_actions(job, result)
        cards.append({"job": job, "readiness": result})
    actions = (
        FollowUpAction.query.filter_by(status="open")
        .order_by(FollowUpAction.created_at.desc())
        .limit(25)
        .all()
    )
    return render_template("today/dashboard.html", cards=cards, actions=actions, now=now)
