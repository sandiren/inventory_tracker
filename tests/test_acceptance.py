"""Acceptance tests for Equipment Readiness pilot."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta

import pytest

# Isolated DB — never touch production
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://er_pilot:er_pilot_dev@127.0.0.1:5432/equipment_readiness_pilot",
)
os.environ["SECRET_KEY"] = "test-secret"


from app import create_app
from extensions import db
from models import Asset, Job, JobRequirement, Reservation, User
from seed import seed_demo_data
from services.custody import CustodyError, issue_asset, return_asset
from services.readiness import evaluate_job_readiness
from services.reservations import ReservationError, create_reservation


@pytest.fixture()
def app():
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": os.environ["DATABASE_URL"],
            "WTF_CSRF_ENABLED": False,
        }
    )
    with application.app_context():
        db.drop_all()
        db.create_all()
        seed_demo_data()
        yield application
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email="manager@datravia.local", password="Manager123!"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def test_unauthenticated_requests_redirect(client):
    for path in ("/", "/jobs/", "/equipment/", "/equipment/scan"):
        resp = client.get(path)
        assert resp.status_code in {302, 401}
        assert "/login" in (resp.headers.get("Location") or "")


def test_login_and_today_board(client):
    resp = login(client)
    assert resp.status_code == 200
    assert b"Today" in resp.data or b"Operations" in resp.data or b"JOB-1001" in resp.data


def test_operator_cannot_create_job(client, app):
    login(client, "operator@datravia.local", "Operator123!")
    resp = client.post(
        "/jobs/new",
        data={
            "code": "JOB-9999",
            "title": "Should fail",
            "site_name": "X",
            "starts_at": (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (datetime.utcnow() + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M"),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        assert Job.query.filter_by(code="JOB-9999").first() is None


def test_reservation_conflict(app):
    with app.app_context():
        manager = User.query.filter_by(email="manager@datravia.local").first()
        job1 = Job.query.filter_by(code="JOB-1001").first()
        job2 = Job.query.filter_by(code="JOB-1002").first()
        req1 = JobRequirement.query.filter_by(job_id=job1.id).first()
        req2 = JobRequirement.query.filter_by(job_id=job2.id, category=req1.category).first()
        asset = Asset.query.filter_by(category=req1.category, status="available").first()
        assert asset is not None
        create_reservation(
            job_id=job1.id,
            requirement_id=req1.id,
            asset_id=asset.id,
            actor=manager,
        )
        with pytest.raises(ReservationError) as exc:
            create_reservation(
                job_id=job2.id,
                requirement_id=req2.id,
                asset_id=asset.id,
                actor=manager,
            )
        assert exc.value.code == "schedule_conflict"


def test_issue_return_idempotent_and_audited(app):
    with app.app_context():
        manager = User.query.filter_by(email="manager@datravia.local").first()
        job = Job.query.filter_by(code="JOB-1001").first()
        req = next(r for r in job.requirements if r.category == "MEWP")
        asset = Asset.query.filter_by(tag="MEWP-001").first()
        create_reservation(
            job_id=job.id,
            requirement_id=req.id,
            asset_id=asset.id,
            actor=manager,
        )
        # verification
        from datetime import timedelta as td

        from models import AssetVerification, EquipmentEvent

        now = datetime.utcnow()
        db.session.add(
            AssetVerification(
                asset_id=asset.id,
                job_id=job.id,
                verified_by_id=manager.id,
                verified_at=now,
                expires_at=now + td(hours=24),
                result="pass",
            )
        )
        asset.last_verified_at = now
        asset.verification_expires_at = now + td(hours=24)
        db.session.commit()

        key = f"issue-{uuid.uuid4()}"
        first = issue_asset(
            asset_id=asset.id,
            job_id=job.id,
            actor=manager,
            idempotency_key=key,
            notes="gate issue",
        )
        second = issue_asset(
            asset_id=asset.id,
            job_id=job.id,
            actor=manager,
            idempotency_key=key,
            notes="gate issue",
        )
        assert first["ok"] is True
        assert second["replayed"] is True
        assert first["event_id"] == second["event_id"]
        assert EquipmentEvent.query.filter_by(event_type="issue", asset_id=asset.id).count() == 1

        ret_key = f"return-{uuid.uuid4()}"
        returned = return_asset(
            asset_id=asset.id,
            actor=manager,
            idempotency_key=ret_key,
            notes="back to yard",
            condition_ok=True,
        )
        assert returned["asset_status"] == "available"
        assert EquipmentEvent.query.filter_by(event_type="return", asset_id=asset.id).count() == 1


def test_readiness_blocked_without_reservation(app):
    with app.app_context():
        job = Job.query.filter_by(code="JOB-1002").first()
        result = evaluate_job_readiness(job)
        assert result.status == "Blocked"
        assert any(r.code == "missing_reservation" for r in result.reasons)


def test_full_ready_path(app):
    with app.app_context():
        manager = User.query.filter_by(email="manager@datravia.local").first()
        job = Job.query.filter_by(code="JOB-1001").first()
        now = datetime.utcnow()
        from models import AssetVerification

        for req in job.requirements:
            asset = Asset.query.filter_by(category=req.category, status="available").first()
            create_reservation(
                job_id=job.id,
                requirement_id=req.id,
                asset_id=asset.id,
                actor=manager,
            )
            if req.verification_required:
                db.session.add(
                    AssetVerification(
                        asset_id=asset.id,
                        job_id=job.id,
                        verified_by_id=manager.id,
                        verified_at=now,
                        expires_at=now + timedelta(hours=24),
                        result="pass",
                    )
                )
                asset.last_verified_at = now
                asset.verification_expires_at = now + timedelta(hours=24)
        db.session.commit()
        result = evaluate_job_readiness(job)
        assert result.status == "Ready"
