# Connecting Inventory Tracker to Supabase

This guide walks through configuring the Flask application to use [Supabase](https://supabase.com/) as the backing PostgreSQL database instead of the default local SQLite file.

## 1. Prepare your Supabase project

1. Sign in to the [Supabase dashboard](https://app.supabase.com/) and create a new project (or reuse an existing one).
2. Take note of the database password you set during project creation. You will need it for the connection string.
3. From the dashboard, open **Project Settings → Database** and locate the **Connection string** section. Copy the "URI" string that looks similar to:
   ```
   postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
   ```
   Supabase requires TLS, so the URI normally already includes `?sslmode=require`. If it does not, append it manually.

## 2. Install the PostgreSQL driver

The app already uses SQLAlchemy, so switching databases only requires a PostgreSQL driver. Install the packages listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

> **Note**: `psycopg2-binary` is included to provide the PostgreSQL driver that SQLAlchemy uses under the hood.

## 3. Configure environment variables

1. Copy the sample environment file and fill it in with your project details:
   ```bash
   cp .env.example .env
   ```
   Open `.env` in your editor and update the placeholders with your Supabase project URL, anon key, and database password. The app automatically loads variables defined in `.env` via [python-dotenv](https://pypi.org/project/python-dotenv/), so there is no need to export them manually.
2. If you prefer to manage variables outside of `.env`, you can still export them directly. Supply either the full Supabase connection string as `DATABASE_URL` _or_ let the app assemble it from the standard Supabase environment variables:
   ```bash
   # Option A: provide the connection string directly
   export DATABASE_URL="postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require"

   # Option B: supply Supabase metadata and let the app build the string
   export SUPABASE_URL="https://titxasiceazfdyfqjukf.supabase.co"
   export SUPABASE_DB_PASSWORD="<your-database-password>"
   # You can also use Supabase's alternate names
   # export SUPABASE_DB_URL="postgresql://..."
   # export SUPABASE_DIRECT_URL="postgresql://..."
   # export SUPABASE_POSTGRES_PASSWORD="<your-database-password>"
   # Optional overrides if you changed defaults in Supabase
   # export SUPABASE_DB_USER="postgres"
   # export SUPABASE_DB_NAME="postgres"
   # export SUPABASE_DB_HOST="db.<project-ref>.supabase.co"
   # export SUPABASE_DB_PORT="5432"
   # export SUPABASE_PROJECT_REF="<project-ref>"
   # export SUPABASE_PROJECT_URL="https://<project-ref>.supabase.co"

   export SECRET_KEY="replace-with-a-strong-secret"
   export SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRpdHhhc2ljZWF6ZmR5ZnFqdWtmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTg5NzQ1MjksImV4cCI6MjA3NDU1MDUyOX0.7KTnmlUFq6xAw8OpeHDgkABfD-YSrFzdGgw8W5HLvIw"
   ```
   `SUPABASE_URL` and the anon key come from **Project Settings → API**. The database password is the one set when the project was created (you can reset it under **Project Settings → Database** if needed). Any special characters in the password are automatically URL-encoded by the app, so copy it exactly as shown.
3. The Flask app now logs whether it is using PostgreSQL or falling back to SQLite. If you see a fallback message in the console, double-check that one of the password variables listed above is available along with either `DATABASE_URL`, `SUPABASE_DB_URL`, or the combination of `SUPABASE_URL` + password.

## 4. Apply the database schema

Instead of relying on SQLAlchemy's auto-generated schema, run the provided SQL script so Supabase exactly matches the Flask models:

```bash
psql "$DATABASE_URL" -f docs/supabase_schema.sql
```

Alternatively, open the Supabase SQL editor, paste the contents of `docs/supabase_schema.sql`, and execute the script. It creates the `inventory_items`, `categories`, and `locations` tables and adds helpful triggers and indexes.

## 5. Verify the connection

1. Visit `http://127.0.0.1:5000/` and add a test inventory item.
2. Open the Supabase SQL editor or Table editor to confirm the data appears in the corresponding tables.

## 6. Deploying

When deploying (for example to Render, Railway, Fly.io, etc.):

- Set the `DATABASE_URL` environment variable in the hosting provider's dashboard using the same Supabase connection string.
- Ensure outbound connections to `db.<project-ref>.supabase.co` on port `5432` are allowed by the host.
- Rotate the Supabase password periodically and update the environment variable accordingly.

Once these steps are complete the Inventory Tracker app will read and write data directly to Supabase, so all users will share the centralized database.
