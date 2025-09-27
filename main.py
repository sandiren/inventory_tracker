import os
from typing import Optional
from urllib.parse import urlparse
from datetime import datetime
from io import BytesIO

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
import qrcode
from dotenv import load_dotenv


app = Flask(__name__)

load_dotenv()


def _derive_supabase_database_url() -> Optional[str]:
    """Construct a PostgreSQL connection string from Supabase env vars."""

    # Allow supplying a ready-made PostgreSQL URL via a few common Supabase vars.
    for direct_var in ("SUPABASE_DB_URL", "SUPABASE_DIRECT_URL"):
        direct_url = os.environ.get(direct_var)
        if direct_url:
            if direct_url.startswith("postgresql") and "sslmode=" not in direct_url:
                separator = "&" if "?" in direct_url else "?"
                return f"{direct_url}{separator}sslmode=require"
            return direct_url

    password = (
        os.environ.get("SUPABASE_DB_PASSWORD")
        or os.environ.get("SUPABASE_POSTGRES_PASSWORD")
        or os.environ.get("POSTGRES_PASSWORD")
    )
    if not password:
        return None

    raw_url = (
        os.environ.get("SUPABASE_URL")
        or os.environ.get("SUPABASE_PROJECT_URL")
        or os.environ.get("SUPABASE_HOST")
    )
    project_ref = (
        os.environ.get("SUPABASE_PROJECT_REF")
        or os.environ.get("SUPABASE_PROJECT_REFERENCE")
        or os.environ.get("PROJECT_REF")
    )

    host = os.environ.get("SUPABASE_DB_HOST")

    if raw_url:
        normalized_url = raw_url
        if "//" not in normalized_url:
            normalized_url = f"https://{normalized_url}"
        project_url = urlparse(normalized_url)
        candidate_host = project_url.netloc or project_url.path
        if candidate_host:
            parts = candidate_host.split(".")
            if candidate_host.endswith("supabase.co") and parts:
                # Supabase REST URLs use <project_ref>.supabase.co while database
                # hosts use db.<project_ref>.supabase.co. Normalize both cases so
                # we can build the proper PostgreSQL hostname.
                if parts[0] == "db" and len(parts) >= 2:
                    project_ref = project_ref or parts[1]
                else:
                    project_ref = project_ref or parts[0]
                if not host and project_ref:
                    host = f"db.{project_ref}.supabase.co"
            elif not host:
                host = candidate_host

    if not host and project_ref:
        host = f"db.{project_ref}.supabase.co"

    if not host:
        return None

    user = os.environ.get("SUPABASE_DB_USER", "postgres")
    db_name = os.environ.get("SUPABASE_DB_NAME", "postgres")
    port = os.environ.get("SUPABASE_DB_PORT", "5432")

    from urllib.parse import quote_plus

    safe_user = quote_plus(user)
    safe_password = quote_plus(password)
    safe_db_name = quote_plus(db_name)

    return (
        "postgresql://"
        f"{safe_user}:{safe_password}@{host}:{port}/{safe_db_name}?sslmode=require"
    )


database_url = os.environ.get("DATABASE_URL") or _derive_supabase_database_url()
if not database_url:
    database_url = "sqlite:///inventory.db"
    app.logger.warning(
        "Falling back to local SQLite storage. Set DATABASE_URL or Supabase "
        "environment variables to use PostgreSQL instead."
    )
else:
    if database_url.startswith("postgresql"):
        app.logger.info("Using PostgreSQL database backend")
    else:
        app.logger.info(
            "Using database configuration supplied via DATABASE_URL environment variable"
        )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
if database_url.startswith("postgresql") and "sslmode=" not in database_url:
    app.config.setdefault(
        "SQLALCHEMY_ENGINE_OPTIONS", {"connect_args": {"sslmode": "require"}}
    )

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

db = SQLAlchemy(app)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    def as_dict(self):
        return {"id": self.id, "name": self.name}


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    def as_dict(self):
        return {"id": self.id, "name": self.name}


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(80), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    location = db.Column(db.String(120), nullable=True)
    gps_lat = db.Column(db.Float, nullable=True)
    gps_lng = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="available")
    last_checked_in = db.Column(db.DateTime, nullable=True)
    last_checked_out = db.Column(db.DateTime, nullable=True)
    maintenance_due = db.Column(db.Date, nullable=True)
    maintenance_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "quantity": self.quantity,
            "location": self.location,
            "gps_lat": self.gps_lat,
            "gps_lng": self.gps_lng,
            "status": self.status,
            "last_checked_in": self.last_checked_in.isoformat()
            if self.last_checked_in
            else None,
            "last_checked_out": self.last_checked_out.isoformat()
            if self.last_checked_out
            else None,
            "maintenance_due": self.maintenance_due.isoformat()
            if self.maintenance_due
            else None,
            "maintenance_notes": self.maintenance_notes,
        }


@app.route("/")
def dashboard():
    items = InventoryItem.query.order_by(InventoryItem.name).all()
    total_items = len(items)
    checked_out_count = (
        InventoryItem.query.filter(InventoryItem.status == "checked_out").count()
    )
    maintenance_due_items = InventoryItem.query.filter(
        InventoryItem.maintenance_due != None,
        InventoryItem.maintenance_due <= datetime.utcnow().date(),
    ).all()

    return render_template(
        "dashboard.html",
        items=items,
        total_items=total_items,
        checked_out_count=checked_out_count,
        maintenance_due_items=maintenance_due_items,
    )


@app.route("/inventory/new", methods=["GET", "POST"])
def new_inventory():
    if request.method == "POST":
        item = InventoryItem(
            name=request.form.get("name", "").strip(),
            description=request.form.get("description"),
            category=request.form.get("category"),
            quantity=int(request.form.get("quantity", 0) or 0),
            location=request.form.get("location"),
            gps_lat=_parse_float(request.form.get("gps_lat")),
            gps_lng=_parse_float(request.form.get("gps_lng")),
            maintenance_due=_parse_date(request.form.get("maintenance_due")),
            maintenance_notes=request.form.get("maintenance_notes"),
        )
        if not item.name:
            flash("Name is required", "error")
            return redirect(url_for("new_inventory"))

        db.session.add(item)
        db.session.commit()
        flash("Inventory item created", "success")
        return redirect(url_for("dashboard"))

    categories = Category.query.order_by(Category.name).all()
    locations = Location.query.order_by(Location.name).all()
    return render_template(
        "inventory_form.html",
        item=None,
        action="Create",
        categories=categories,
        locations=locations,
        categories_json=[category.as_dict() for category in categories],
        locations_json=[location.as_dict() for location in locations],
    )


@app.route("/inventory/<int:item_id>/edit", methods=["GET", "POST"])
def edit_inventory(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Name is required", "error")
            return redirect(url_for("edit_inventory", item_id=item_id))

        item.name = name
        item.description = request.form.get("description")
        item.category = request.form.get("category")
        item.quantity = int(request.form.get("quantity", item.quantity) or 0)
        item.location = request.form.get("location")
        item.gps_lat = _parse_float(request.form.get("gps_lat"))
        item.gps_lng = _parse_float(request.form.get("gps_lng"))
        item.maintenance_due = _parse_date(request.form.get("maintenance_due"))
        item.maintenance_notes = request.form.get("maintenance_notes")

        db.session.commit()
        flash("Inventory item updated", "success")
        return redirect(url_for("inventory_detail", item_id=item_id))

    categories = Category.query.order_by(Category.name).all()
    locations = Location.query.order_by(Location.name).all()
    return render_template(
        "inventory_form.html",
        item=item,
        action="Update",
        categories=categories,
        locations=locations,
        categories_json=[category.as_dict() for category in categories],
        locations_json=[location.as_dict() for location in locations],
    )


@app.route("/inventory/<int:item_id>/delete", methods=["POST"])
def delete_inventory(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Inventory item deleted", "success")
    return redirect(url_for("dashboard"))


@app.route("/inventory/<int:item_id>")
def inventory_detail(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    return render_template("inventory_detail.html", item=item)


@app.route("/inventory/<int:item_id>/checkin", methods=["POST"])
def checkin_inventory(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    item.status = "available"
    item.last_checked_in = datetime.utcnow()
    db.session.commit()
    flash(f"{item.name} checked in", "success")
    return redirect(url_for("inventory_detail", item_id=item_id))


@app.route("/inventory/<int:item_id>/checkout", methods=["POST"])
def checkout_inventory(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    item.status = "checked_out"
    item.last_checked_out = datetime.utcnow()
    item.location = request.form.get("checkout_location") or item.location
    db.session.commit()
    flash(f"{item.name} checked out", "success")
    return redirect(url_for("inventory_detail", item_id=item_id))


@app.route("/inventory/<int:item_id>/maintenance", methods=["POST"])
def schedule_maintenance(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    item.maintenance_due = _parse_date(request.form.get("maintenance_due"))
    item.maintenance_notes = request.form.get("maintenance_notes")
    db.session.commit()
    flash("Maintenance schedule updated", "success")
    return redirect(url_for("inventory_detail", item_id=item_id))


@app.route("/inventory/<int:item_id>/gps", methods=["POST"])
def update_gps(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    item.gps_lat = _parse_float(request.form.get("gps_lat"))
    item.gps_lng = _parse_float(request.form.get("gps_lng"))
    db.session.commit()
    flash("GPS coordinates updated", "success")
    return redirect(url_for("inventory_detail", item_id=item_id))


@app.route("/inventory/<int:item_id>/qr")
def inventory_qr(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    qr_url = url_for("inventory_detail", item_id=item.id, _external=True)
    try:
        qr_stream = _generate_qr_png(qr_url)
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("inventory_detail", item_id=item.id))

    return send_file(
        qr_stream,
        mimetype="image/png",
        as_attachment=False,
        download_name=f"inventory-{item.id}.png",
    )


@app.route("/inventory/map")
def inventory_map():
    items = InventoryItem.query.order_by(InventoryItem.name).all()
    items_data = [item.as_dict() for item in items]
    return render_template("map.html", items=items, items_data=items_data)


@app.route("/api/items")
def items_api():
    items = InventoryItem.query.all()
    return jsonify([item.as_dict() for item in items])


@app.route("/categories", methods=["GET", "POST"])
def manage_categories():
    if request.method == "GET":
        categories = Category.query.order_by(Category.name).all()
        return jsonify([category.as_dict() for category in categories])

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Category name is required."}), 400

    if Category.query.filter(db.func.lower(Category.name) == name.lower()).first():
        return jsonify({"error": "Category already exists."}), 409

    category = Category(name=name)
    db.session.add(category)
    db.session.commit()
    return jsonify(category.as_dict()), 201


@app.route("/categories/<int:category_id>", methods=["PUT"])
def update_category(category_id: int):
    category = Category.query.get_or_404(category_id)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()

    if not name:
        return jsonify({"error": "Category name is required."}), 400

    existing = Category.query.filter(
        db.func.lower(Category.name) == name.lower(), Category.id != category.id
    ).first()
    if existing:
        return jsonify({"error": "Category already exists."}), 409

    old_name = category.name
    category.name = name

    for item in InventoryItem.query.filter_by(category=old_name).all():
        item.category = name

    db.session.commit()
    return jsonify(category.as_dict())


@app.route("/categories/<int:category_id>", methods=["DELETE"])
def delete_category(category_id: int):
    category = Category.query.get_or_404(category_id)
    old_name = category.name

    InventoryItem.query.filter_by(category=old_name).update(
        {"category": None}, synchronize_session=False
    )

    db.session.delete(category)
    db.session.commit()
    return jsonify({"status": "deleted"})


@app.route("/locations", methods=["GET", "POST"])
def manage_locations():
    if request.method == "GET":
        locations = Location.query.order_by(Location.name).all()
        return jsonify([location.as_dict() for location in locations])

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Location name is required."}), 400

    if Location.query.filter(db.func.lower(Location.name) == name.lower()).first():
        return jsonify({"error": "Location already exists."}), 409

    location = Location(name=name)
    db.session.add(location)
    db.session.commit()
    return jsonify(location.as_dict()), 201


@app.route("/locations/<int:location_id>", methods=["PUT"])
def update_location(location_id: int):
    location = Location.query.get_or_404(location_id)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()

    if not name:
        return jsonify({"error": "Location name is required."}), 400

    existing = Location.query.filter(
        db.func.lower(Location.name) == name.lower(), Location.id != location.id
    ).first()
    if existing:
        return jsonify({"error": "Location already exists."}), 409

    old_name = location.name
    location.name = name

    for item in InventoryItem.query.filter_by(location=old_name).all():
        item.location = name

    db.session.commit()
    return jsonify(location.as_dict())


@app.route("/locations/<int:location_id>", methods=["DELETE"])
def delete_location(location_id: int):
    location = Location.query.get_or_404(location_id)
    old_name = location.name

    InventoryItem.query.filter_by(location=old_name).update(
        {"location": None}, synchronize_session=False
    )

    db.session.delete(location)
    db.session.commit()
    return jsonify({"status": "deleted"})


def _parse_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        flash("Invalid coordinates provided", "error")
        return None


def _parse_date(value):
    if value in (None, ""):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date format. Use YYYY-MM-DD.", "error")
        return None


def _generate_qr_png(data: str) -> BytesIO:
    if not data:
        raise RuntimeError("Unable to generate QR code: no data provided")

    if not hasattr(qrcode, "QRCode"):
        if hasattr(qrcode, "make"):
            image = qrcode.make(data)
        else:
            raise RuntimeError(
                "QR code generation library is unavailable. Install the 'qrcode' package."
            )
    else:
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    # Pillow-based image objects exposed by the qrcode library implement save().
    try:
        image.save(buffer, format="PNG")
    except TypeError as exc:
        # Some backends (e.g. PyPNG) do not accept a format keyword.
        if "unexpected keyword argument 'format'" not in str(exc):
            raise
        image.save(buffer)
    buffer.seek(0)
    return buffer


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
