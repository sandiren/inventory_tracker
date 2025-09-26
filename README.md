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

3. Run the application:

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

## Environment Variables

- `SECRET_KEY`: Override the default Flask secret key for production deployments.
- `DATABASE_URL`: If set, the app will use this connection string instead of the local SQLite database.
