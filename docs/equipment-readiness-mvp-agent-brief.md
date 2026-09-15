# Equipment Readiness by Datravia

Full implementation brief prepared 15 September 2026.

The canonical brief for this implementation is the Datravia Equipment Readiness MVP agent brief supplied by the owner. Implement the narrow protected pilot around this workflow:

`create job → add requirement → reserve asset → verify → issue → return → readiness/action updates`

## Core implementation decisions

- Reuse the existing Flask + Jinja application.
- PostgreSQL for integration tests and pilot data.
- Single customer per deployment/database for the pilot.
- Manager and Operator roles with protected access.
- Individually identified assets only for pilot operations.
- Append-only equipment event history.
- Job requirements and reusable requirement templates.
- Database-backed reservation conflict protection.
- Job-specific asset verification.
- Deterministic readiness states: Ready, Blocked, Unverified.
- Server-side readiness evaluator shared across views.
- Atomic issue and return transactions with idempotency protection.
- Datravia design system for visual implementation.
- Synthetic data until a live pilot is separately approved.

## Readiness precedence

```text
if any known blocking condition exists:
    Blocked
else if any required information or verification is missing/expired:
    Unverified
else:
    Ready
```

The UI must show the underlying reasons and corrective actions. Do not present readiness as a safety certification or guarantee that a job can proceed.

## Required implementation sequence

1. Inspect repository and record baseline.
2. Add migrations, authentication, permissions and reliable audited custody transactions.
3. Add jobs, requirements, reservations and schedule conflict rules.
4. Add deterministic readiness and follow-up actions.
5. Implement Today, Equipment and Jobs UX plus mobile scan/manual lookup.
6. Run automated, PostgreSQL, concurrency, browser and security checks.
7. Fix observed critical/major defects and provide an evidence-backed handover.

## Scope exclusions

Do not build billing, subscriptions, multi-tenant administration, consumables, purchasing, ERP integrations, predictive AI, RFID/BLE, live GPS tracking, native apps, full offline sync or advanced dashboards.

Do not integrate with Datravia Signals.

## Evidence standard

For significant requirements report **passed**, **failed**, **blocked**, or **not run**. Do not equate generated code or screenshots with a verified workflow. Do not claim production readiness, customer validation, realised savings or commercial success from synthetic tests.

## Commercial decision

**VALIDATE** through a narrow paid pilot. A future pilot should test adoption, preparation time, equipment-related disruptions, resolution follow-through, support effort and concrete willingness to continue paying.

## Agent start instruction

> Inspect the current code and relevant historical plan before editing. Implement the narrow equipment-readiness pilot on a new branch while preserving the Flask/Jinja application. Start with access control and one audited issue/return transaction, then add job requirements, reservations and deterministic readiness. Use isolated PostgreSQL and synthetic data, run the acceptance tests, review the actual browser experience, fix observed defects, and return the evidence-backed handover. Do not change live infrastructure, migrate real data, publish externally or broaden scope without explicit approval.
