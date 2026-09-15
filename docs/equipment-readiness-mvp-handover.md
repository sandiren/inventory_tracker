# Equipment Readiness MVP — Evidence-backed handover

**Branch:** `cursor/equipment-readiness-mvp-fd92`  
**Date:** 15 September 2026  
**Environment:** Isolated local PostgreSQL `equipment_readiness_pilot` (synthetic data only)  
**Brief:** `docs/equipment-readiness-mvp-agent-brief.md`

---

## Verdict

The narrow Equipment Readiness pilot is **implemented and locally verified** against isolated Postgres + synthetic data. It is **not** production-ready, not customer-validated, and was **not** deployed.

**Commercial posture (from brief):** VALIDATE via a future narrow paid pilot — do not claim savings or market success from this synthetic run.

---

## What was preserved

- Existing Flask + Jinja application structure
- Legacy inventory routes (login-gated under `/inventory…`)
- No live / paid infrastructure changes
- No merge to `main`, no public deploy

---

## Implemented features

| Area | Status | Notes |
|------|--------|-------|
| Protected access (manager / operator) | **Implemented + verified** | Flask-Login; unauthenticated requests redirect to `/login` |
| Role gates | **Implemented + verified** | Operator cannot create jobs (acceptance test) |
| Append-only equipment events | **Implemented + verified** | Issue/return write `EquipmentEvent` rows |
| Idempotent issue / return | **Implemented + verified** | Same idempotency key replays; single audit event |
| Jobs + requirements + templates | **Implemented + verified** | UI + seed templates |
| Reservations + schedule conflict | **Implemented + verified** | Overlapping hold rejected (`schedule_conflict`) |
| Job-specific verification | **Implemented + verified** | Pass/fail with expiry; feeds readiness |
| Deterministic readiness | **Implemented + verified** | Ready / Blocked / Unverified precedence |
| Follow-up actions sync | **Implemented** | Open readiness actions refreshed from evaluator |
| Today / Jobs / Equipment / Scan UI | **Implemented + browser-verified** | Datravia-branded shell; mobile nav checked at ~390px |
| Synthetic seed data | **Implemented + verified** | `manager@datravia.local` / `operator@datravia.local` |
| Isolated PostgreSQL | **Implemented + verified** | Local DB only; not Supabase/prod |

---

## Verified evidence

### Automated acceptance (`pytest`)

```text
7 passed in ~2.5s
```

Covered:

1. Unauthenticated redirect  
2. Login + Today board  
3. Operator cannot create job  
4. Reservation schedule conflict  
5. Issue/return idempotency + audit  
6. Readiness blocked without reservation  
7. Full path → Ready after reserve + verify  

### Browser review (local `http://127.0.0.1:5000`)

| Flow | Result |
|------|--------|
| Login | Passed |
| Today board | Passed |
| Jobs list + detail | Passed |
| Reserve asset on job | Passed |
| Equipment list + asset detail | Passed |
| Scan page | Passed with workaround (see defects) |
| Mobile Today + Scan (~390px) | Passed — usable compact nav |

Screenshots in `/opt/cursor/artifacts/`:

- `01_login.webp`
- `02_today_desktop.webp`
- `03_jobs_list.webp`
- `04_job_detail.webp`
- `05_equipment_list.webp`
- `06_scan.webp`
- `07_asset_detail.webp`
- `08_today_mobile.webp`
- `09_scan_mobile.webp`

---

## Defects observed & disposition

| Severity | Defect | Disposition |
|----------|--------|-------------|
| Medium | Scan form sometimes failed HTML5 validation when browser automation prefilled the tag | Mitigated: `GET /equipment/scan?tag=…` deep link + clearer form hint. Re-test manually in a real phone browser before pilot. |
| Low | `datetime.utcnow()` deprecation warnings under Python 3.12 | Not blocking; track for timezone-aware UTC cleanup |
| Info | Legacy inventory UI still Bootstrap-era; not restyled to full Datravia system | Out of MVP critical path; preserved on purpose |

---

## Explicitly blocked / out of scope (not claimed)

- Live customer data migration  
- Paid infra / Supabase production provisioning  
- Merge / deploy / public URL  
- Billing, multi-tenant admin, consumables, ERP, predictive AI, RFID/BLE, live GPS, native apps, offline sync  
- Datravia Signals integration  
- Safety certification claims (UI states readiness is an **operational aid only**)

---

## How to run the pilot locally

```bash
# Postgres (example local)
# DB: equipment_readiness_pilot  USER: er_pilot

export DATABASE_URL=postgresql://er_pilot:er_pilot_dev@127.0.0.1:5432/equipment_readiness_pilot
export SECRET_KEY=pilot-dev-secret

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

flask --app app:app init-db
flask --app app:app seed-demo
flask --app app:app run --host 127.0.0.1 --port 5000

pytest -q tests/test_acceptance.py
```

**Seed users**

| Email | Password | Role |
|-------|----------|------|
| `manager@datravia.local` | `Manager123!` | manager |
| `operator@datravia.local` | `Operator123!` | operator |

---

## Suggested next steps (needs explicit approval)

1. Manager + operator walkthrough on synthetic data  
2. Decide production Postgres host (e.g. Supabase) — do **not** auto-provision  
3. Replace seed users with real IdP / passwords  
4. Hardening: CSRF on state-changing forms, UTC cleanup, scan UX on physical devices  
5. Paid pilot design: adoption, prep time, disruption, follow-through, support load, willingness to pay  

---

## Honesty labels (required by brief)

| Claim | Label |
|-------|-------|
| Code + UI for protected custody + readiness loop | **Passed** (local) |
| Automated acceptance on isolated Postgres | **Passed** |
| Browser + mobile smoke | **Passed** (one scan UX caveat) |
| Production readiness | **Not claimed** |
| Customer validation / savings | **Not claimed** |
| Live deploy | **Blocked** (no approval) |
