# Equipment Readiness (Datravia)

## What it is (plain English)

**Equipment Readiness** helps contractors and M&E teams keep track of tools and plant.

Use it to:

1. **See what kit you have** and where it is  
2. **Book gear to a job** so two crews do not claim the same asset  
3. **Check items out and back in** with a clear trail of who had them  
4. **Spot blockers early** — missing kit, overdue checks, or unverified equipment — before the crew leaves the yard  

In short: *know what you have, who has it, and whether a job can start.*

> Readiness is an **operational aid**, not a safety certification.

---

Flask + Jinja operations app. The pilot adds protected custody, job requirements, reservations, deterministic readiness, and a field scan loop — while preserving the legacy inventory screens.

## Pilot features

- Manager / operator login (protected routes)
- Individually tagged assets with append-only custody events
- Idempotent issue & return
- Jobs → requirements (templates) → reservations with conflict checks
- Job-specific verification
- Deterministic readiness: **Ready / Blocked / Unverified**
- Today board, Jobs, Equipment, Scan UI (Datravia branding)
- Legacy inventory + map retained under `/inventory…`

## Local setup (isolated Postgres)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL=postgresql://USER:PASS@127.0.0.1:5432/equipment_readiness_pilot
export SECRET_KEY=change-me

flask --app app:app init-db
flask --app app:app seed-demo
flask --app app:app run --host 127.0.0.1 --port 5000
```

### Seed users

| Email | Password | Role |
|-------|----------|------|
| manager@datravia.local | Manager123! | manager |
| operator@datravia.local | Operator123! | operator |

## Tests

```bash
pytest -q tests/test_acceptance.py
```

## Docs

- Brief: `docs/equipment-readiness-mvp-agent-brief.md`
- Handover: `docs/equipment-readiness-mvp-handover.md`

## Environment

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLAlchemy URL (use Postgres for the pilot) |
| `SECRET_KEY` | Flask session secret |

Do not point this pilot at production data without an explicit migration plan.
