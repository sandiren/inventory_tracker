# Equipment Readiness (Datravia)

Flask + Jinja operations app for contractor / M&E teams. The Equipment Readiness pilot adds protected custody, job requirements, reservations, deterministic readiness, and a field scan loop — while preserving the legacy inventory screens.

> Readiness is an **operational aid**, not a safety certification.

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
