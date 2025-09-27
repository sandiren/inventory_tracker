# Inventory Tracker

A Flask-based web application to manage construction inventory with QR code generation, GPS tracking, and maintenance scheduling.

## Features

- Dashboard overview with status counts and maintenance alerts
- Add, edit, and delete inventory items
- Generate QR codes for quick access to item detail pages
- Check items in and out while tracking last activity
- Schedule maintenance and record notes
- Store GPS coordinates and visualize assets on an interactive map

## Getting Started

1. Create and activate a virtual environment (optional):

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy the sample environment file and fill in your credentials (Supabase users should supply the project URL, anon key, and database password):

   ```bash
   cp .env.example .env
   # then edit .env with your preferred editor
   ```

   The app automatically loads variables defined in `.env`.

4. Run the application:

   ```bash
   flask --app main run
   ```

   The development server runs on `http://127.0.0.1:5000/`.

## Usage Tips

- Use the **Add Item** button to register new equipment or materials.
- Print the QR code for each item and affix it to the asset to quickly open the item detail page.
- Update GPS coordinates manually from the item detail page or via the API endpoint `/api/items` if integrating with external trackers.
- Visit the **Map View** to see all assets with GPS coordinates plotted on a map.

## Database

The application uses SQLite (`inventory.db`) by default. Tables are created automatically on the first request.

To connect the app to a hosted PostgreSQL database such as Supabase, either set the `DATABASE_URL` environment variable directly or provide the Supabase metadata variables. The app understands Supabase's `SUPABASE_DB_URL`/`SUPABASE_DIRECT_URL` connection strings as well as the metadata form (`SUPABASE_URL`, `SUPABASE_DB_PASSWORD`, optional `SUPABASE_DB_USER`, `SUPABASE_DB_NAME`, `SUPABASE_DB_HOST`, `SUPABASE_DB_PORT`). It logs when it falls back to SQLite so you immediately know if any of the required credentials are missing. A detailed walkthrough is available in [`docs/SUPABASE_SETUP.md`](docs/SUPABASE_SETUP.md).

## Environment Variables

- `SECRET_KEY`: Override the default Flask secret key for production deployments.
- `DATABASE_URL`: If set, the app will use this connection string instead of the local SQLite database (e.g. a Supabase URI).
- `SUPABASE_DB_URL` / `SUPABASE_DIRECT_URL`: Full PostgreSQL connection strings supplied by Supabase. The app automatically appends `sslmode=require` if it is missing.
- `SUPABASE_URL` / `SUPABASE_PROJECT_URL` / `SUPABASE_HOST`: Supabase project URL or host (used to derive the PostgreSQL host when `DATABASE_URL`/`SUPABASE_DB_URL` is not set).
- `SUPABASE_DB_PASSWORD` / `SUPABASE_POSTGRES_PASSWORD`: Password for the primary Supabase database user.
- `SUPABASE_DB_USER`, `SUPABASE_DB_NAME`, `SUPABASE_DB_HOST`, `SUPABASE_DB_PORT`: Optional overrides when deriving the Supabase connection string.
- `SUPABASE_PROJECT_REF` / `SUPABASE_PROJECT_REFERENCE`: Optional project reference used when the host cannot be parsed from `SUPABASE_URL`.
