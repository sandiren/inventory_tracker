"""Jobs, requirements, reservations."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from blueprints.auth import role_required
from extensions import db
from models import Job, JobRequirement, RequirementTemplate, Reservation
from services.readiness import evaluate_job_readiness, sync_follow_up_actions
from services.reservations import (
    ReservationError,
    cancel_reservation,
    candidate_assets_for_requirement,
    create_reservation,
)

jobs_bp = Blueprint("jobs", __name__, url_prefix="/jobs")


def _parse_dt(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@jobs_bp.route("/")
@login_required
def index():
    now = datetime.utcnow()
    cards = [
        {"job": job, "readiness": evaluate_job_readiness(job, now=now)}
        for job in Job.query.order_by(Job.starts_at.desc()).all()
    ]
    return render_template("jobs/index.html", cards=cards)


@jobs_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("manager")
def create():
    if request.method == "POST":
        code = (request.form.get("code") or "").strip().upper()
        title = (request.form.get("title") or "").strip()
        site_name = (request.form.get("site_name") or "").strip()
        starts_at = _parse_dt(request.form.get("starts_at") or "")
        ends_at = _parse_dt(request.form.get("ends_at") or "")
        notes = (request.form.get("notes") or "").strip() or None
        if not all([code, title, site_name, starts_at, ends_at]):
            flash("Code, title, site, start and end are required.", "error")
        elif ends_at <= starts_at:
            flash("End must be after start.", "error")
        elif Job.query.filter_by(code=code).first():
            flash("Job code already exists.", "error")
        else:
            job = Job(
                code=code,
                title=title,
                site_name=site_name,
                starts_at=starts_at,
                ends_at=ends_at,
                status="planned",
                notes=notes,
                created_by_id=current_user.id,
            )
            db.session.add(job)
            db.session.commit()
            flash(f"Job {job.code} created.", "success")
            return redirect(url_for("jobs.detail", job_id=job.id))
    return render_template("jobs/form.html")


@jobs_bp.route("/<int:job_id>")
@login_required
def detail(job_id: int):
    job = Job.query.get_or_404(job_id)
    readiness = evaluate_job_readiness(job)
    sync_follow_up_actions(job, readiness)
    templates = RequirementTemplate.query.order_by(RequirementTemplate.name).all()
    candidates = {
        req.id: candidate_assets_for_requirement(req) for req in job.requirements
    }
    return render_template(
        "jobs/detail.html",
        job=job,
        readiness=readiness,
        templates=templates,
        candidates=candidates,
    )


@jobs_bp.route("/<int:job_id>/requirements", methods=["POST"])
@login_required
@role_required("manager")
def add_requirement(job_id: int):
    job = Job.query.get_or_404(job_id)
    template_id = request.form.get("template_id")
    if template_id:
        template = RequirementTemplate.query.get_or_404(int(template_id))
        req = JobRequirement(
            job_id=job.id,
            template_id=template.id,
            label=template.name,
            category=template.category,
            is_critical=template.is_critical,
            verification_required=template.verification_required,
        )
    else:
        label = (request.form.get("label") or "").strip()
        category = (request.form.get("category") or "").strip()
        if not label or not category:
            flash("Label and category required for custom requirement.", "error")
            return redirect(url_for("jobs.detail", job_id=job.id))
        req = JobRequirement(
            job_id=job.id,
            label=label,
            category=category,
            is_critical=request.form.get("is_critical") == "on",
            verification_required=request.form.get("verification_required") == "on",
        )
    db.session.add(req)
    db.session.commit()
    flash("Requirement added.", "success")
    return redirect(url_for("jobs.detail", job_id=job.id))


@jobs_bp.route("/<int:job_id>/reserve", methods=["POST"])
@login_required
@role_required("manager", "operator")
def reserve(job_id: int):
    try:
        reservation = create_reservation(
            job_id=job_id,
            requirement_id=int(request.form.get("requirement_id") or 0),
            asset_id=int(request.form.get("asset_id") or 0),
            actor=current_user,
        )
        flash(f"Reservation #{reservation.id} created.", "success")
    except ReservationError as exc:
        flash(exc.message, "error")
    return redirect(url_for("jobs.detail", job_id=job_id))


@jobs_bp.route("/reservations/<int:reservation_id>/cancel", methods=["POST"])
@login_required
@role_required("manager")
def cancel(reservation_id: int):
    reservation = Reservation.query.get_or_404(reservation_id)
    job_id = reservation.job_id
    try:
        cancel_reservation(reservation_id=reservation_id, actor=current_user)
        flash("Reservation cancelled.", "success")
    except ReservationError as exc:
        flash(exc.message, "error")
    return redirect(url_for("jobs.detail", job_id=job_id))
