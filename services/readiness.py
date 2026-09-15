"""Deterministic readiness evaluation + follow-up action sync."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional

from extensions import db
from models import Asset, AssetVerification, FollowUpAction, Job

READY = "Ready"
BLOCKED = "Blocked"
UNVERIFIED = "Unverified"


@dataclass
class ReadinessReason:
    code: str
    severity: str
    message: str
    corrective_action: str
    requirement_id: Optional[int] = None
    asset_id: Optional[int] = None
    reservation_id: Optional[int] = None


@dataclass
class ReadinessResult:
    status: str
    reasons: list[ReadinessReason] = field(default_factory=list)
    evaluated_at: str = ""
    job_id: Optional[int] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "evaluated_at": self.evaluated_at,
            "job_id": self.job_id,
            "reasons": [asdict(r) for r in self.reasons],
        }


def _latest_verification(asset_id: int, job_id: int) -> Optional[AssetVerification]:
    return (
        AssetVerification.query.filter_by(asset_id=asset_id, job_id=job_id)
        .order_by(AssetVerification.verified_at.desc())
        .first()
    )


def evaluate_job_readiness(job: Job, *, now: datetime | None = None) -> ReadinessResult:
    now = now or datetime.utcnow()
    blockers: list[ReadinessReason] = []
    unverified: list[ReadinessReason] = []

    requirements = list(job.requirements or [])
    if not requirements:
        blockers.append(
            ReadinessReason(
                code="no_requirements",
                severity="blocker",
                message="Job has no equipment requirements defined.",
                corrective_action="Add at least one requirement.",
            )
        )

    for req in requirements:
        active = [r for r in (req.reservations or []) if r.status in {"held", "issued"}]
        if not active:
            reason = ReadinessReason(
                code="missing_reservation",
                severity="blocker" if req.is_critical else "major",
                message=f"No asset reserved for '{req.label}'.",
                corrective_action="Reserve a matching available asset.",
                requirement_id=req.id,
            )
            (blockers if req.is_critical else unverified).append(reason)
            continue

        reservation = active[0]
        asset = reservation.asset or db.session.get(Asset, reservation.asset_id)
        if asset is None:
            blockers.append(
                ReadinessReason(
                    code="missing_asset",
                    severity="blocker",
                    message=f"Reserved asset missing for '{req.label}'.",
                    corrective_action="Cancel and reserve a valid asset.",
                    requirement_id=req.id,
                    reservation_id=reservation.id,
                )
            )
            continue

        if asset.status == "maintenance":
            blockers.append(
                ReadinessReason(
                    code="asset_maintenance",
                    severity="blocker",
                    message=f"{asset.tag} is in maintenance.",
                    corrective_action="Choose a different asset or clear maintenance.",
                    requirement_id=req.id,
                    asset_id=asset.id,
                    reservation_id=reservation.id,
                )
            )
        elif asset.status == "unavailable":
            blockers.append(
                ReadinessReason(
                    code="asset_unavailable",
                    severity="blocker",
                    message=f"{asset.tag} is unavailable.",
                    corrective_action="Restore availability or reserve another asset.",
                    requirement_id=req.id,
                    asset_id=asset.id,
                    reservation_id=reservation.id,
                )
            )

        if asset.maintenance_due and asset.maintenance_due <= now.date() and req.is_critical:
            blockers.append(
                ReadinessReason(
                    code="maintenance_overdue",
                    severity="blocker",
                    message=f"{asset.tag} has overdue maintenance ({asset.maintenance_due}).",
                    corrective_action="Complete maintenance or reserve an alternate.",
                    requirement_id=req.id,
                    asset_id=asset.id,
                    reservation_id=reservation.id,
                )
            )

        if asset.status == "issued" and asset.current_job_id and asset.current_job_id != job.id:
            blockers.append(
                ReadinessReason(
                    code="issued_elsewhere",
                    severity="blocker",
                    message=f"{asset.tag} is issued to another job.",
                    corrective_action="Return the asset or reserve a substitute.",
                    requirement_id=req.id,
                    asset_id=asset.id,
                    reservation_id=reservation.id,
                )
            )

        if req.verification_required:
            verification = _latest_verification(asset.id, job.id)
            if verification is None:
                unverified.append(
                    ReadinessReason(
                        code="verification_missing",
                        severity="major",
                        message=f"{asset.tag} has not been verified for this job.",
                        corrective_action="Run job-specific verification before issue.",
                        requirement_id=req.id,
                        asset_id=asset.id,
                        reservation_id=reservation.id,
                    )
                )
            elif verification.result == "fail":
                blockers.append(
                    ReadinessReason(
                        code="verification_failed",
                        severity="blocker",
                        message=f"{asset.tag} failed verification for this job.",
                        corrective_action="Resolve fail notes or reserve another asset.",
                        requirement_id=req.id,
                        asset_id=asset.id,
                        reservation_id=reservation.id,
                    )
                )
            elif verification.expires_at <= now:
                unverified.append(
                    ReadinessReason(
                        code="verification_expired",
                        severity="major",
                        message=f"Verification for {asset.tag} expired.",
                        corrective_action="Re-verify the asset for this job.",
                        requirement_id=req.id,
                        asset_id=asset.id,
                        reservation_id=reservation.id,
                    )
                )

    if blockers:
        status, reasons = BLOCKED, blockers + unverified
    elif unverified:
        status, reasons = UNVERIFIED, unverified
    else:
        status = READY
        reasons = [
            ReadinessReason(
                code="ready",
                severity="info",
                message="All critical requirements are reserved and verified.",
                corrective_action="Proceed to issue when the crew is ready.",
            )
        ]

    return ReadinessResult(
        status=status,
        reasons=reasons,
        evaluated_at=now.isoformat() + "Z",
        job_id=job.id,
    )


def sync_follow_up_actions(job: Job, result: ReadinessResult) -> list[FollowUpAction]:
    FollowUpAction.query.filter_by(job_id=job.id, status="open").filter(
        FollowUpAction.action_type.like("readiness:%")
    ).delete(synchronize_session=False)

    created: list[FollowUpAction] = []
    for reason in result.reasons:
        if reason.code == "ready":
            continue
        action = FollowUpAction(
            job_id=job.id,
            asset_id=reason.asset_id,
            action_type=f"readiness:{reason.code}",
            reason=reason.message,
            corrective_action=reason.corrective_action,
            status="open",
            severity=reason.severity,
        )
        db.session.add(action)
        created.append(action)
    db.session.commit()
    return created
