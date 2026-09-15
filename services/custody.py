"""Atomic issue/return with idempotency + append-only audit events."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Asset, EquipmentEvent, IdempotencyKey, Job, Reservation, User


class CustodyError(Exception):
    def __init__(self, message: str, code: str = "custody_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def _replay(key: str) -> Optional[dict[str, Any]]:
    row = IdempotencyKey.query.filter_by(key=key).first()
    return row.response_json if row else None


def _store(key: str, user: User, action: str, resource_type: str, resource_id: int, response: dict):
    db.session.add(
        IdempotencyKey(
            key=key,
            user_id=user.id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            response_json=response,
        )
    )


def issue_asset(
    *,
    asset_id: int,
    job_id: int,
    actor: User,
    idempotency_key: str,
    notes: str = "",
) -> dict[str, Any]:
    if not idempotency_key.strip():
        raise CustodyError("Idempotency key is required.", "missing_idempotency_key")
    replay = _replay(idempotency_key)
    if replay is not None:
        return {**replay, "replayed": True}

    asset = Asset.query.filter_by(id=asset_id).with_for_update().first()
    if asset is None:
        raise CustodyError("Asset not found.", "asset_not_found")
    job = Job.query.filter_by(id=job_id).with_for_update().first()
    if job is None:
        raise CustodyError("Job not found.", "job_not_found")
    if job.status in {"cancelled", "completed"}:
        raise CustodyError("Job is not open for issue.", "job_closed")

    reservation = (
        Reservation.query.filter_by(job_id=job_id, asset_id=asset_id, status="held")
        .with_for_update()
        .first()
    )
    if reservation is None:
        raise CustodyError("No held reservation links this asset to the job.", "reservation_missing")

    now = datetime.utcnow()
    if now > reservation.ends_at:
        raise CustodyError("Reservation window has ended.", "reservation_expired")
    if now < reservation.starts_at - timedelta(hours=12):
        raise CustodyError("Reservation window has not opened yet.", "reservation_not_open")
    if asset.status == "issued":
        raise CustodyError("Asset is already issued.", "already_issued")
    if asset.status == "maintenance":
        raise CustodyError("Asset is in maintenance.", "in_maintenance")
    if asset.status == "unavailable":
        raise CustodyError("Asset is unavailable.", "unavailable")

    prior = asset.status
    asset.status = "issued"
    asset.current_job_id = job.id
    asset.current_holder_id = actor.id
    asset.updated_at = now
    reservation.status = "issued"
    reservation.updated_at = now
    if job.status == "planned":
        job.status = "active"
        job.updated_at = now

    event = EquipmentEvent(
        asset_id=asset.id,
        event_type="issue",
        actor_user_id=actor.id,
        job_id=job.id,
        reservation_id=reservation.id,
        payload_json={
            "notes": notes,
            "from_status": prior,
            "to_status": "issued",
            "job_code": job.code,
        },
        idempotency_key=f"event:{idempotency_key}",
    )
    db.session.add(event)
    response = {
        "ok": True,
        "action": "issue",
        "asset_id": asset.id,
        "asset_tag": asset.tag,
        "job_id": job.id,
        "reservation_id": reservation.id,
        "event_id": None,
        "replayed": False,
    }
    _store(idempotency_key, actor, "issue", "asset", asset.id, response)
    try:
        db.session.flush()
        response["event_id"] = event.id
        stored = IdempotencyKey.query.filter_by(key=idempotency_key).first()
        if stored:
            stored.response_json = dict(response)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        replay = _replay(idempotency_key)
        if replay is not None:
            return {**replay, "replayed": True}
        raise CustodyError("Issue conflict. Retry with a new key.", "conflict") from exc
    return response


def return_asset(
    *,
    asset_id: int,
    actor: User,
    idempotency_key: str,
    notes: str = "",
    condition_ok: bool = True,
) -> dict[str, Any]:
    if not idempotency_key.strip():
        raise CustodyError("Idempotency key is required.", "missing_idempotency_key")
    replay = _replay(idempotency_key)
    if replay is not None:
        return {**replay, "replayed": True}

    asset = Asset.query.filter_by(id=asset_id).with_for_update().first()
    if asset is None:
        raise CustodyError("Asset not found.", "asset_not_found")
    if asset.status != "issued":
        raise CustodyError("Asset is not currently issued.", "not_issued")

    reservation = (
        Reservation.query.filter_by(asset_id=asset_id, status="issued")
        .order_by(Reservation.updated_at.desc())
        .with_for_update()
        .first()
    )
    job_id = asset.current_job_id
    reservation_id = reservation.id if reservation else None
    previous_holder = asset.current_holder_id
    now = datetime.utcnow()

    asset.status = "available" if condition_ok else "maintenance"
    asset.current_job_id = None
    asset.current_holder_id = None
    asset.updated_at = now
    if not condition_ok:
        asset.condition_notes = notes or "Returned with condition issue."
    if reservation:
        reservation.status = "released"
        reservation.updated_at = now

    event = EquipmentEvent(
        asset_id=asset.id,
        event_type="return",
        actor_user_id=actor.id,
        job_id=job_id,
        reservation_id=reservation_id,
        payload_json={
            "notes": notes,
            "condition_ok": condition_ok,
            "previous_holder_id": previous_holder,
            "to_status": asset.status,
        },
        idempotency_key=f"event:{idempotency_key}",
    )
    db.session.add(event)
    response = {
        "ok": True,
        "action": "return",
        "asset_id": asset.id,
        "asset_tag": asset.tag,
        "job_id": job_id,
        "reservation_id": reservation_id,
        "event_id": None,
        "asset_status": asset.status,
        "replayed": False,
    }
    _store(idempotency_key, actor, "return", "asset", asset.id, response)
    try:
        db.session.flush()
        response["event_id"] = event.id
        stored = IdempotencyKey.query.filter_by(key=idempotency_key).first()
        if stored:
            stored.response_json = dict(response)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        replay = _replay(idempotency_key)
        if replay is not None:
            return {**replay, "replayed": True}
        raise CustodyError("Return conflict. Retry with a new key.", "conflict") from exc
    return response
