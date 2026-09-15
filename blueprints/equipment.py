"""Equipment list, scan, verify, issue, return."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from blueprints.auth import role_required
from extensions import db
from models import Asset, AssetVerification, EquipmentEvent, Job, Reservation
from services.custody import CustodyError, issue_asset, return_asset

equipment_bp = Blueprint("equipment", __name__, url_prefix="/equipment")


@equipment_bp.route("/")
@login_required
def index():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    query = Asset.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Asset.tag.ilike(like),
                Asset.name.ilike(like),
                Asset.category.ilike(like),
                Asset.serial_number.ilike(like),
            )
        )
    if status:
        query = query.filter_by(status=status)
    return render_template(
        "equipment/index.html",
        assets=query.order_by(Asset.tag).all(),
        q=q,
        status=status,
    )


@equipment_bp.route("/scan", methods=["GET", "POST"])
@login_required
def scan():
    # Support GET ?tag= for QR deep links and POST from the field form.
    tag = (request.values.get("tag") or "").strip().upper()
    if request.method == "POST" or (request.method == "GET" and tag):
        if not tag:
            flash("Enter or scan an asset tag.", "error")
            return render_template("equipment/scan.html")
        asset = Asset.query.filter(db.func.upper(Asset.tag) == tag).first()
        if not asset:
            flash(f"No asset found for tag {tag}.", "error")
            return render_template("equipment/scan.html", tag=tag)
        return redirect(url_for("equipment.detail", asset_id=asset.id))
    return render_template("equipment/scan.html")


@equipment_bp.route("/<int:asset_id>")
@login_required
def detail(asset_id: int):
    asset = Asset.query.get_or_404(asset_id)
    events = (
        EquipmentEvent.query.filter_by(asset_id=asset.id)
        .order_by(EquipmentEvent.created_at.desc())
        .limit(30)
        .all()
    )
    reservations = (
        Reservation.query.filter_by(asset_id=asset.id)
        .filter(Reservation.status.in_(("held", "issued")))
        .order_by(Reservation.starts_at)
        .all()
    )
    jobs = Job.query.filter(Job.status.in_(("planned", "active"))).order_by(Job.starts_at).all()
    return render_template(
        "equipment/detail.html",
        asset=asset,
        events=events,
        reservations=reservations,
        jobs=jobs,
        idem_key=str(uuid.uuid4()),
    )


@equipment_bp.route("/<int:asset_id>/verify", methods=["POST"])
@login_required
@role_required("manager", "operator")
def verify(asset_id: int):
    asset = Asset.query.get_or_404(asset_id)
    job = Job.query.get_or_404(int(request.form.get("job_id") or 0))
    result = (request.form.get("result") or "pass").strip().lower()
    notes = (request.form.get("notes") or "").strip()
    hours = int(request.form.get("valid_hours") or 24)
    reservation = (
        Reservation.query.filter_by(asset_id=asset.id, job_id=job.id)
        .filter(Reservation.status.in_(("held", "issued")))
        .first()
    )
    if reservation is None:
        flash("Asset must be reserved to this job before verification.", "error")
        return redirect(url_for("equipment.detail", asset_id=asset.id))
    if result not in {"pass", "fail"}:
        flash("Result must be pass or fail.", "error")
        return redirect(url_for("equipment.detail", asset_id=asset.id))

    now = datetime.utcnow()
    verification = AssetVerification(
        asset_id=asset.id,
        job_id=job.id,
        reservation_id=reservation.id,
        verified_by_id=current_user.id,
        verified_at=now,
        expires_at=now + timedelta(hours=hours),
        result=result,
        notes=notes or None,
    )
    asset.last_verified_at = now
    asset.verification_expires_at = verification.expires_at
    db.session.add(verification)
    db.session.add(
        EquipmentEvent(
            asset_id=asset.id,
            event_type="verified",
            actor_user_id=current_user.id,
            job_id=job.id,
            reservation_id=reservation.id,
            payload_json={
                "result": result,
                "notes": notes,
                "expires_at": verification.expires_at.isoformat(),
            },
        )
    )
    db.session.commit()
    flash(f"Verification recorded for {asset.tag}: {result}.", "success")
    return redirect(url_for("equipment.detail", asset_id=asset.id))


@equipment_bp.route("/<int:asset_id>/issue", methods=["POST"])
@login_required
@role_required("manager", "operator")
def issue(asset_id: int):
    try:
        result = issue_asset(
            asset_id=asset_id,
            job_id=int(request.form.get("job_id") or 0),
            actor=current_user,
            idempotency_key=(request.form.get("idempotency_key") or "").strip()
            or str(uuid.uuid4()),
            notes=(request.form.get("notes") or "").strip(),
        )
        msg = f"Issued {result['asset_tag']}."
        if result.get("replayed"):
            msg += " (idempotent replay)"
        flash(msg, "success")
    except CustodyError as exc:
        flash(exc.message, "error")
    return redirect(url_for("equipment.detail", asset_id=asset_id))


@equipment_bp.route("/<int:asset_id>/return", methods=["POST"])
@login_required
@role_required("manager", "operator")
def return_(asset_id: int):
    try:
        result = return_asset(
            asset_id=asset_id,
            actor=current_user,
            idempotency_key=(request.form.get("idempotency_key") or "").strip()
            or str(uuid.uuid4()),
            notes=(request.form.get("notes") or "").strip(),
            condition_ok=request.form.get("condition_ok") != "no",
        )
        msg = f"Returned {result['asset_tag']} → {result['asset_status']}."
        if result.get("replayed"):
            msg += " (idempotent replay)"
        flash(msg, "success")
    except CustodyError as exc:
        flash(exc.message, "error")
    return redirect(url_for("equipment.detail", asset_id=asset_id))
