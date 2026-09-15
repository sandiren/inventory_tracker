"""SQLAlchemy models — Equipment Readiness pilot + legacy inventory."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="operator")  # manager|operator
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self) -> bool:
        return bool(self.active)

    @property
    def is_manager(self) -> bool:
        return self.role == "manager"


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    def as_dict(self):
        return {"id": self.id, "name": self.name}


class Location(db.Model):
    __tablename__ = "locations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    def as_dict(self):
        return {"id": self.id, "name": self.name}


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(80), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    location = db.Column(db.String(120), nullable=True)
    gps_lat = db.Column(db.Float, nullable=True)
    gps_lng = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="available")
    last_checked_in = db.Column(db.DateTime, nullable=True)
    last_checked_out = db.Column(db.DateTime, nullable=True)
    maintenance_due = db.Column(db.Date, nullable=True)
    maintenance_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "quantity": self.quantity,
            "location": self.location,
            "gps_lat": self.gps_lat,
            "gps_lng": self.gps_lng,
            "status": self.status,
            "last_checked_in": self.last_checked_in.isoformat() if self.last_checked_in else None,
            "last_checked_out": self.last_checked_out.isoformat() if self.last_checked_out else None,
            "maintenance_due": self.maintenance_due.isoformat() if self.maintenance_due else None,
            "maintenance_notes": self.maintenance_notes,
        }


class Asset(db.Model):
    __tablename__ = "assets"

    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80), nullable=True, index=True)
    location = db.Column(db.String(120), nullable=True)
    serial_number = db.Column(db.String(120), nullable=True)
    # available | reserved | issued | maintenance | unavailable
    status = db.Column(db.String(20), nullable=False, default="available", index=True)
    condition_notes = db.Column(db.Text, nullable=True)
    maintenance_due = db.Column(db.Date, nullable=True)
    last_verified_at = db.Column(db.DateTime, nullable=True)
    verification_expires_at = db.Column(db.DateTime, nullable=True)
    current_job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=True)
    current_holder_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    current_holder = db.relationship("User", foreign_keys=[current_holder_id])
    events = db.relationship(
        "EquipmentEvent",
        back_populates="asset",
        order_by="desc(EquipmentEvent.created_at)",
    )


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    site_name = db.Column(db.String(160), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    ends_at = db.Column(db.DateTime, nullable=False, index=True)
    # planned | active | completed | cancelled
    status = db.Column(db.String(20), nullable=False, default="planned")
    notes = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    requirements = db.relationship(
        "JobRequirement",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobRequirement.id",
    )
    reservations = db.relationship("Reservation", back_populates="job")
    actions = db.relationship("FollowUpAction", back_populates="job")


class RequirementTemplate(db.Model):
    __tablename__ = "requirement_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(80), nullable=False)
    is_critical = db.Column(db.Boolean, nullable=False, default=True)
    verification_required = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class JobRequirement(db.Model):
    __tablename__ = "job_requirements"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey("requirement_templates.id"), nullable=True)
    label = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    is_critical = db.Column(db.Boolean, nullable=False, default=True)
    verification_required = db.Column(db.Boolean, nullable=False, default=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    job = db.relationship("Job", back_populates="requirements")
    template = db.relationship("RequirementTemplate")
    reservations = db.relationship("Reservation", back_populates="requirement")


class Reservation(db.Model):
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)
    requirement_id = db.Column(
        db.Integer, db.ForeignKey("job_requirements.id"), nullable=False, index=True
    )
    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True)
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    # held | issued | released | cancelled
    status = db.Column(db.String(20), nullable=False, default="held", index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    job = db.relationship("Job", back_populates="reservations")
    requirement = db.relationship("JobRequirement", back_populates="reservations")
    asset = db.relationship("Asset")
    created_by = db.relationship("User")


class AssetVerification(db.Model):
    __tablename__ = "asset_verifications"

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservations.id"), nullable=True)
    verified_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    verified_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    result = db.Column(db.String(20), nullable=False)  # pass | fail
    notes = db.Column(db.Text, nullable=True)

    asset = db.relationship("Asset")
    job = db.relationship("Job")
    verified_by = db.relationship("User")


class EquipmentEvent(db.Model):
    __tablename__ = "equipment_events"

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True)
    event_type = db.Column(db.String(40), nullable=False, index=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=True, index=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservations.id"), nullable=True)
    payload_json = db.Column(db.JSON, nullable=True)
    idempotency_key = db.Column(db.String(120), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    asset = db.relationship("Asset", back_populates="events")
    actor = db.relationship("User", foreign_keys=[actor_user_id])
    job = db.relationship("Job")


class IdempotencyKey(db.Model):
    __tablename__ = "idempotency_keys"

    key = db.Column(db.String(120), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(40), nullable=False)
    resource_type = db.Column(db.String(40), nullable=False)
    resource_id = db.Column(db.Integer, nullable=True)
    response_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class FollowUpAction(db.Model):
    __tablename__ = "follow_up_actions"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=True, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=True, index=True)
    action_type = db.Column(db.String(60), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    corrective_action = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open")  # open|done|dismissed
    severity = db.Column(db.String(20), nullable=False, default="major")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    job = db.relationship("Job", back_populates="actions")
    asset = db.relationship("Asset")
