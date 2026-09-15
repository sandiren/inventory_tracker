"""Reservations with schedule conflict protection."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Asset, EquipmentEvent, Job, JobRequirement, Reservation, User


class ReservationError(Exception):
    def __init__(self, message: str, code: str = "reservation_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def overlapping_reservations(
    asset_id: int, starts_at: datetime, ends_at: datetime, exclude_id: int | None = None
) -> list[Reservation]:
    q = Reservation.query.filter(
        Reservation.asset_id == asset_id,
        Reservation.status.in_(("held", "issued")),
        Reservation.starts_at < ends_at,
        Reservation.ends_at > starts_at,
    )
    if exclude_id is not None:
        q = q.filter(Reservation.id != exclude_id)
    return q.order_by(Reservation.starts_at).all()


def create_reservation(
    *,
    job_id: int,
    requirement_id: int,
    asset_id: int,
    actor: User,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
) -> Reservation:
    job = Job.query.filter_by(id=job_id).with_for_update().first()
    if job is None:
        raise ReservationError("Job not found.", "job_not_found")
    if job.status in {"cancelled", "completed"}:
        raise ReservationError("Cannot reserve for a closed job.", "job_closed")

    requirement = JobRequirement.query.filter_by(id=requirement_id, job_id=job_id).first()
    if requirement is None:
        raise ReservationError("Requirement not found on this job.", "requirement_missing")

    asset = Asset.query.filter_by(id=asset_id).with_for_update().first()
    if asset is None:
        raise ReservationError("Asset not found.", "asset_not_found")
    if asset.status in {"maintenance", "unavailable"}:
        raise ReservationError(f"Asset is {asset.status}.", "asset_unavailable")
    if asset.status == "issued" and asset.current_job_id != job.id:
        raise ReservationError("Asset is issued to another job.", "asset_issued_elsewhere")

    window_start = starts_at or job.starts_at
    window_end = ends_at or job.ends_at
    if window_end <= window_start:
        raise ReservationError("End must be after start.", "invalid_window")

    if requirement.category and asset.category:
        if requirement.category.lower() != asset.category.lower():
            raise ReservationError(
                f"Category mismatch: asset '{asset.category}' vs requirement '{requirement.category}'.",
                "category_mismatch",
            )

    conflicts = overlapping_reservations(asset.id, window_start, window_end)
    if conflicts:
        other = conflicts[0]
        other_code = other.job.code if other.job else str(other.job_id)
        raise ReservationError(
            f"Asset {asset.tag} already reserved for {other_code} "
            f"({other.starts_at.isoformat()} – {other.ends_at.isoformat()}).",
            "schedule_conflict",
        )

    if (
        Reservation.query.filter_by(requirement_id=requirement.id)
        .filter(Reservation.status.in_(("held", "issued")))
        .first()
    ):
        raise ReservationError(
            "This requirement already has an active reservation.",
            "requirement_already_reserved",
        )

    reservation = Reservation(
        job_id=job.id,
        requirement_id=requirement.id,
        asset_id=asset.id,
        starts_at=window_start,
        ends_at=window_end,
        status="held",
        created_by_id=actor.id,
    )
    db.session.add(reservation)
    db.session.flush()

    if asset.status == "available":
        asset.status = "reserved"
        asset.updated_at = datetime.utcnow()

    db.session.add(
        EquipmentEvent(
            asset_id=asset.id,
            event_type="reserved",
            actor_user_id=actor.id,
            job_id=job.id,
            reservation_id=reservation.id,
            payload_json={
                "requirement_id": requirement.id,
                "starts_at": window_start.isoformat(),
                "ends_at": window_end.isoformat(),
            },
        )
    )
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ReservationError("DB conflict while reserving.", "db_conflict") from exc
    return reservation


def cancel_reservation(*, reservation_id: int, actor: User) -> Reservation:
    reservation = Reservation.query.filter_by(id=reservation_id).with_for_update().first()
    if reservation is None:
        raise ReservationError("Reservation not found.", "not_found")
    if reservation.status == "issued":
        raise ReservationError("Cannot cancel an issued reservation.", "already_issued")
    if reservation.status in {"cancelled", "released"}:
        return reservation

    reservation.status = "cancelled"
    reservation.updated_at = datetime.utcnow()

    asset = Asset.query.filter_by(id=reservation.asset_id).with_for_update().first()
    if asset and asset.status == "reserved":
        others = (
            Reservation.query.filter(
                Reservation.asset_id == asset.id,
                Reservation.id != reservation.id,
                Reservation.status.in_(("held", "issued")),
            ).count()
        )
        if others == 0:
            asset.status = "available"
            asset.updated_at = datetime.utcnow()

    db.session.add(
        EquipmentEvent(
            asset_id=reservation.asset_id,
            event_type="reservation_cancelled",
            actor_user_id=actor.id,
            job_id=reservation.job_id,
            reservation_id=reservation.id,
            payload_json={},
        )
    )
    db.session.commit()
    return reservation


def candidate_assets_for_requirement(requirement: JobRequirement) -> list[Asset]:
    q = Asset.query.filter(Asset.status.in_(("available", "reserved")))
    if requirement.category:
        q = q.filter(db.func.lower(Asset.category) == requirement.category.lower())
    return q.order_by(Asset.tag).all()
