# Inventory Tracker — UX & Product Plan

Conversation notes capturing the project audit, branding direction, database guidance, and differentiation strategy for a Datravia-branded inventory product aimed at building contractors, M&E, and anyone tracking yard/site assets.

---

## 1. Current product snapshot

Flask + Jinja + Bootstrap 5 app for construction inventory.

### Existing capabilities

| Area | What it does today |
|------|--------------------|
| **Dashboard** | Total items, checked-out count, maintenance-due list + full inventory table |
| **Items** | Create / edit / delete |
| **Categories & locations** | Manage via modals on the form (API-backed) |
| **Check in / out** | Status flip + optional checkout location |
| **Maintenance** | Due date + notes |
| **GPS** | Lat/lng on item; map picker on form; Leaflet map view |
| **QR** | Per-item QR linking to detail page |
| **API** | `GET /api/items` JSON list |

### Current gaps

- No search / filter on dashboard
- No assignee / custody (“who has it”)
- No activity / audit history
- No bulk actions (QR sheets, CSV)
- Generic Bootstrap look — not Datravia-branded
- Weak field/mobile workflow (detail page is form-heavy)
- Map is markers-only (no status color / legend / filters)

---

## 2. Database (from conversation)

### What is used now?

- **ORM:** Flask-SQLAlchemy
- **Config:** `DATABASE_URL` from environment only (local SQLite fallback is commented out in `app.py`)
- **Driver already in deps:** `psycopg2-binary` → Postgres-ready
- **README** still mentions SQLite (`inventory.db`) as the default, which no longer matches the live config path

### Is Supabase better?

**Yes for production on Vercel** — as hosted Postgres, not as a rewrite of the app.

| Option | Fit |
|--------|-----|
| **SQLite** | Fine for local demos only; not durable on Vercel serverless |
| **Supabase** | Good fit: Postgres + connection string; keep SQLAlchemy models |
| **Neon / Railway / Vercel Postgres** | Same idea (hosted Postgres) |

**Recommended use of Supabase**

- Point `DATABASE_URL` at Supabase (prefer **pooler / transaction mode** for serverless)
- Keep business logic in Flask
- Auth / Realtime / Storage optional later — not required for v1

---

## 3. Datravia brand system (from www.datravia.com)

| Token | Approx. value | Use in app |
|-------|---------------|------------|
| Accent | Dusty rose / mauve `#C57798` | Highlights, overdue, active states |
| Primary CTA | Deep charcoal `#1A2A33` | Buttons, headers |
| Surface | Soft off-white / light gray | Page background |
| Cards | White, soft radius, light elevation | Content blocks |
| Logo | Icon + “Datravia” + `DATA · ANALYTICS · AUTOMATION` | Header + footer |

**Mood:** light, spacious, typography-led, rounded CTAs — professional B2B, warm accent (not purple SaaS, not cream/serif, not dark neon).

**Must include**

- Datravia logo somewhere in the shell
- Footer / credit: **Developed by Datravia** → [datravia.com](https://www.datravia.com)

**Working product names discussed**

- Keep **Inventory Tracker**, or rebrand UI to **YardOps** / **SiteStock** (Datravia product identity)

---

## 4. Competitor UX patterns worth borrowing

From ToolWatch, Fleetio, Samsara-class tools:

1. **Scan-first field flow** — QR opens straight to check-out / check-in
2. **Custody trail** — who has it, where, since when
3. **Status clarity** — available / out / in maintenance / overdue at a glance
4. **Fast find** — search + filters (site, category, status)
5. **Map + list** — status-colored pins
6. **Maintenance alerts** — due soon vs overdue
7. **Mobile-first actions** — large tap targets for yard/site use

These make the app *usable*. Alone, they do not make it *uncopyable*.

---

## 5. Original “make it nicer” plan (baseline UX)

### Shell & brand

- Design tokens + Datravia colors/fonts
- Sticky nav with search
- Footer: Developed by Datravia

### Dashboard

- Clickable KPI tiles (Total / Available / Out / Maintenance)
- Live search + status / category / location chips
- Status pills, overdue accent, empty states
- Row quick actions (View / QR / Check out–in)

### Item detail (field-first)

- Status hero + one primary Check Out / Check In CTA
- Checkout: location + **assigned to**
- Prominent QR panel
- Mini-map when GPS exists
- Activity timeline

### Forms & map

- Grouped form sections; keep category/location modals
- Map: colored markers, legend, filters

### Extra options (useful but common)

- Activity log model
- Status: In maintenance
- Bulk QR print page
- CSV export
- Optional low-stock threshold
- Mobile bottom nav

### Suggested original build order

1. Brand + shell + footer  
2. Dashboard search / filter / KPIs  
3. Detail field workflow + assignee  
4. Activity log + maintenance status  
5. Map upgrades + CSV / bulk QR  
6. Mobile polish  

### Success criteria (baseline)

- Feels like a Datravia product
- Find + check out in under ~10 seconds
- Maintenance and custody obvious
- Fast on phone; no heavy SPA rewrite (stay Flask + Jinja + CSS/JS)

---

## 6. Differentiation: what makes it hard to copy

### Problem with the baseline alone

Baseline changes make the app **faster and more professional**.  
A table + check-in/out + pretty theme is still easy to clone.

### Product point of view

> This isn’t an inventory list — it’s a **site-readiness and custody brain** for contractors, with Datravia **decision cards** telling the yard what to do next.

Align with Datravia’s own framing: **data → clarity → decision → action**.

### Differentiator set

| Capability | What users can do | Why it stands out |
|------------|-------------------|-------------------|
| **Site readiness score** | Per jobsite: “Can we start tomorrow?” from availability, overdue maintenance, missing critical gear | Product logic, not CRUD |
| **Crew kits / loadouts** | Define kits (“M&E install van”, “HVAC bag”); one-tap kit checkout | Workflow depth |
| **Conflict / shortage radar** | Warn when two jobs need the same scarce asset | Ops intelligence |
| **Decision cards** | Dashboard actions: overdue tools, long checkouts, missing critical items | Datravia-style insights |
| **Scan → story** | QR shows last moves, owner, next action — not just a form | Field narrative UX |
| **Loss / idle signals** | Flag long checkouts or assets idle 30+ days | Soft rules / analytics |
| **Yard board + mobile thumb UI** | Crib view + phone view | Dual-mode ops product |

### Must-ship for uniqueness

1. Decision cards dashboard  
2. Assigned-to + activity timeline  
3. Crew kits / bulk check-out  
4. Overdue / idle / conflict warnings  
5. Datravia brand shell + field-first detail page  

### Defer (Phase 2)

- Auth / roles  
- Photos  
- RFID / BLE  
- Offline PWA  
- True ML predictions  
- ERP / purchasing sync  

---

## 7. What the app would *do* after the full distinctive build

A contractor / M&E team could:

1. See **what to do next** on the dashboard (decision cards), not only counts  
2. Score **jobsite readiness** before a crew leaves the yard  
3. Check out a **whole kit** in one action  
4. Know **who holds** an asset and for how long  
5. Get warned about **conflicts, idle gear, and overdue maintenance**  
6. Scan QR and immediately see **custody story + next action**  
7. Find and move assets fast via **search, filters, and status map**  
8. Export / print QR for yard tagging  
9. Clearly see the product as **Developed by Datravia**

---

## 8. Open choices (from conversation)

- [ ] Product name: **Inventory Tracker** vs **YardOps** vs **SiteStock**
- [ ] Hosted DB: **Supabase** (recommended) vs Neon / other Postgres
- [ ] Priority differentiator to build first: **kits** vs **readiness score** vs **decision cards**

---

## 9. Recommended next step

1. Confirm product name + which differentiator ships first  
2. Provision Supabase and set `DATABASE_URL` (pooled)  
3. Implement brand shell + decision-card dashboard first (visible Datravia identity + unique value in one slice)  
4. Layer custody, kits, readiness, then map / export polish  

---

*Developed by Datravia — data · analytics · automation — [www.datravia.com](https://www.datravia.com)*
