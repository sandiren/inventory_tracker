"""Synthetic pilot data for isolated PostgreSQL."""

from __future__ import annotations

from datetime import datetime, timedelta

from extensions import db
from models import (
    Asset,
    Category,
    InventoryItem,
    Job,
    JobRequirement,
    Location,
    RequirementTemplate,
    User,
)


def seed_demo_data(*, reset: bool = False) -> None:
    if reset:
        db.drop_all()
        db.create_all()

    if User.query.filter_by(email="manager@datravia.local").first():
        return

    manager = User(email="manager@datravia.local", name="Maya Manager", role="manager")
    manager.set_password("Manager123!")
    operator = User(email="operator@datravia.local", name="Omar Operator", role="operator")
    operator.set_password("Operator123!")
    db.session.add_all([manager, operator])
    db.session.flush()

    for name in ("Yard A", "Bay 2", "Service Van 1"):
        db.session.add(Location(name=name))
    for name in ("Tools", "PPE", "Consumables"):
        db.session.add(Category(name=name))

    db.session.add(
        InventoryItem(
            name="Spare Cable Drum",
            category="Consumables",
            quantity=4,
            location="Yard A",
            status="available",
        )
    )

    templates = [
        RequirementTemplate(
            name="MEWP / Scissor Lift",
            description="Mobile elevating work platform",
            category="MEWP",
            is_critical=True,
            verification_required=True,
        ),
        RequirementTemplate(
            name="Torque Wrench Set",
            description="Calibrated torque tools",
            category="Torque Tool",
            is_critical=True,
            verification_required=True,
        ),
        RequirementTemplate(
            name="Gas Detector",
            description="Personal gas monitor",
            category="Safety",
            is_critical=True,
            verification_required=True,
        ),
        RequirementTemplate(
            name="Cable Puller",
            description="Optional assist tool",
            category="Cable Tool",
            is_critical=False,
            verification_required=False,
        ),
    ]
    db.session.add_all(templates)
    db.session.flush()

    now = datetime.utcnow()
    assets = [
        Asset(tag="MEWP-001", name="Genie GS-1930", category="MEWP", location="Yard A", serial_number="GS1930-1001", status="available"),
        Asset(tag="MEWP-002", name="JLG 1930ES", category="MEWP", location="Yard A", serial_number="JLG1930-44", status="available", maintenance_due=(now - timedelta(days=2)).date()),
        Asset(tag="TQ-101", name="Norbar 100Nm Kit", category="Torque Tool", location="Bay 2", serial_number="NB-100-9", status="available"),
        Asset(tag="TQ-102", name="Snap-On Torque Kit", category="Torque Tool", location="Bay 2", serial_number="SO-77", status="available"),
        Asset(tag="GAS-01", name="BW GasAlert Micro", category="Safety", location="Service Van 1", serial_number="BW-501", status="available"),
        Asset(tag="GAS-02", name="MSA Altair 4XR", category="Safety", location="Bay 2", serial_number="MSA-22", status="maintenance", condition_notes="Sensor fault"),
        Asset(tag="CBL-01", name="Hydraulic Cable Puller", category="Cable Tool", location="Yard A", serial_number="CP-9", status="available"),
    ]
    db.session.add_all(assets)
    db.session.flush()

    job_ready = Job(
        code="JOB-1001",
        title="Plant room M&E install",
        site_name="Riverside Block B",
        starts_at=now + timedelta(hours=4),
        ends_at=now + timedelta(hours=28),
        status="planned",
        notes="Critical path — morning access window",
        created_by_id=manager.id,
    )
    job_blocked = Job(
        code="JOB-1002",
        title="Roof plant replacement",
        site_name="Harbour Tower",
        starts_at=now + timedelta(hours=6),
        ends_at=now + timedelta(hours=36),
        status="planned",
        notes="Needs MEWP + gas detector",
        created_by_id=manager.id,
    )
    db.session.add_all([job_ready, job_blocked])
    db.session.flush()

    db.session.add_all(
        [
            JobRequirement(job_id=job_ready.id, template_id=templates[0].id, label=templates[0].name, category=templates[0].category, is_critical=True, verification_required=True),
            JobRequirement(job_id=job_ready.id, template_id=templates[1].id, label=templates[1].name, category=templates[1].category, is_critical=True, verification_required=True),
            JobRequirement(job_id=job_blocked.id, template_id=templates[0].id, label=templates[0].name, category=templates[0].category, is_critical=True, verification_required=True),
            JobRequirement(job_id=job_blocked.id, template_id=templates[2].id, label=templates[2].name, category=templates[2].category, is_critical=True, verification_required=True),
        ]
    )
    db.session.commit()
