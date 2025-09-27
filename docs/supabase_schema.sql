-- Schema for running Inventory Tracker on Supabase
-- Run this in the Supabase SQL editor or via psql against your project database.

-- Categories table keeps a unique list of item categories.
CREATE TABLE IF NOT EXISTS public.categories (
    id serial PRIMARY KEY,
    name varchar(80) UNIQUE NOT NULL
);

-- Locations table stores distinct storage locations.
CREATE TABLE IF NOT EXISTS public.locations (
    id serial PRIMARY KEY,
    name varchar(120) UNIQUE NOT NULL
);

-- Inventory items table matches the SQLAlchemy model in main.py.
CREATE TABLE IF NOT EXISTS public.inventory_items (
    id serial PRIMARY KEY,
    name varchar(120) NOT NULL,
    description text,
    category varchar(80),
    quantity integer NOT NULL DEFAULT 1,
    location varchar(120),
    gps_lat double precision,
    gps_lng double precision,
    status varchar(20) NOT NULL DEFAULT 'available',
    last_checked_in timestamp with time zone,
    last_checked_out timestamp with time zone,
    maintenance_due date,
    maintenance_notes text,
    created_at timestamp with time zone NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamp with time zone NOT NULL DEFAULT timezone('utc', now())
);

-- Keep updated_at in sync when rows change.
CREATE OR REPLACE FUNCTION public.touch_inventory_items_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at := timezone('utc', now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS inventory_items_set_updated_at ON public.inventory_items;
CREATE TRIGGER inventory_items_set_updated_at
BEFORE UPDATE ON public.inventory_items
FOR EACH ROW
EXECUTE FUNCTION public.touch_inventory_items_updated_at();

-- Helpful indexes for frequent lookups.
CREATE INDEX IF NOT EXISTS idx_inventory_items_name ON public.inventory_items (name);
CREATE INDEX IF NOT EXISTS idx_inventory_items_status ON public.inventory_items (status);
CREATE INDEX IF NOT EXISTS idx_inventory_items_maintenance_due ON public.inventory_items (maintenance_due);
