"""Legacy inventory routes (preserved, login-gated)."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import login_required
import qrcode

from extensions import db
from models import Category, InventoryItem, Location

legacy_bp = Blueprint("legacy", __name__)


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


def _qr_png(data: str) -> BytesIO:
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


@legacy_bp.route("/inventory")
@login_required
def inventory_dashboard():
    items = InventoryItem.query.order_by(InventoryItem.name).all()
    maintenance_due_items = InventoryItem.query.filter(
        InventoryItem.maintenance_due != None,  # noqa: E711
        InventoryItem.maintenance_due <= datetime.utcnow().date(),
    ).all()
    return render_template(
        "dashboard.html",
        items=items,
        total_items=len(items),
        checked_out_count=InventoryItem.query.filter_by(status="checked_out").count(),
        maintenance_due_items=maintenance_due_items,
    )


@legacy_bp.route("/inventory/new", methods=["GET", "POST"])
@login_required
def new_inventory():
    if request.method == "POST":
        item = InventoryItem(
            name=(request.form.get("name") or "").strip(),
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
            return redirect(url_for("legacy.new_inventory"))
        db.session.add(item)
        db.session.commit()
        flash("Inventory item created", "success")
        return redirect(url_for("legacy.inventory_dashboard"))
    categories = Category.query.order_by(Category.name).all()
    locations = Location.query.order_by(Location.name).all()
    return render_template(
        "inventory_form.html",
        item=None,
        action="Create",
        categories=categories,
        locations=locations,
        categories_json=[c.as_dict() for c in categories],
        locations_json=[loc.as_dict() for loc in locations],
    )


@legacy_bp.route("/inventory/<int:item_id>")
@login_required
def inventory_detail(item_id: int):
    return render_template(
        "inventory_detail.html", item=InventoryItem.query.get_or_404(item_id)
    )


@legacy_bp.route("/inventory/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_inventory(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Name is required", "error")
            return redirect(url_for("legacy.edit_inventory", item_id=item_id))
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
        return redirect(url_for("legacy.inventory_detail", item_id=item_id))
    categories = Category.query.order_by(Category.name).all()
    locations = Location.query.order_by(Location.name).all()
    return render_template(
        "inventory_form.html",
        item=item,
        action="Update",
        categories=categories,
        locations=locations,
        categories_json=[c.as_dict() for c in categories],
        locations_json=[loc.as_dict() for loc in locations],
    )


@legacy_bp.route("/inventory/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_inventory(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Inventory item deleted", "success")
    return redirect(url_for("legacy.inventory_dashboard"))


@legacy_bp.route("/inventory/<int:item_id>/checkin", methods=["POST"])
@login_required
def checkin_inventory(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    item.status = "available"
    item.last_checked_in = datetime.utcnow()
    db.session.commit()
    flash(f"{item.name} checked in", "success")
    return redirect(url_for("legacy.inventory_detail", item_id=item_id))


@legacy_bp.route("/inventory/<int:item_id>/checkout", methods=["POST"])
@login_required
def checkout_inventory(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    item.status = "checked_out"
    item.last_checked_out = datetime.utcnow()
    item.location = request.form.get("checkout_location") or item.location
    db.session.commit()
    flash(f"{item.name} checked out", "success")
    return redirect(url_for("legacy.inventory_detail", item_id=item_id))


@legacy_bp.route("/inventory/<int:item_id>/maintenance", methods=["POST"])
@login_required
def schedule_maintenance(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    item.maintenance_due = _parse_date(request.form.get("maintenance_due"))
    item.maintenance_notes = request.form.get("maintenance_notes")
    db.session.commit()
    flash("Maintenance schedule updated", "success")
    return redirect(url_for("legacy.inventory_detail", item_id=item_id))


@legacy_bp.route("/inventory/<int:item_id>/gps", methods=["POST"])
@login_required
def update_gps(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    item.gps_lat = _parse_float(request.form.get("gps_lat"))
    item.gps_lng = _parse_float(request.form.get("gps_lng"))
    db.session.commit()
    flash("GPS coordinates updated", "success")
    return redirect(url_for("legacy.inventory_detail", item_id=item_id))


@legacy_bp.route("/inventory/<int:item_id>/qr")
@login_required
def inventory_qr(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    return send_file(
        _qr_png(url_for("legacy.inventory_detail", item_id=item.id, _external=True)),
        mimetype="image/png",
        download_name=f"inventory-{item.id}.png",
    )


@legacy_bp.route("/inventory/map")
@login_required
def inventory_map():
    items = InventoryItem.query.order_by(InventoryItem.name).all()
    return render_template(
        "map.html", items=items, items_data=[i.as_dict() for i in items]
    )


@legacy_bp.route("/api/items")
@login_required
def items_api():
    return jsonify([i.as_dict() for i in InventoryItem.query.all()])


@legacy_bp.route("/categories", methods=["GET", "POST"])
@login_required
def manage_categories():
    if request.method == "GET":
        return jsonify([c.as_dict() for c in Category.query.order_by(Category.name)])
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


@legacy_bp.route("/categories/<int:category_id>", methods=["PUT", "DELETE"])
@login_required
def mutate_category(category_id: int):
    category = Category.query.get_or_404(category_id)
    if request.method == "DELETE":
        InventoryItem.query.filter_by(category=category.name).update(
            {"category": None}, synchronize_session=False
        )
        db.session.delete(category)
        db.session.commit()
        return jsonify({"status": "deleted"})
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Category name is required."}), 400
    if Category.query.filter(
        db.func.lower(Category.name) == name.lower(), Category.id != category.id
    ).first():
        return jsonify({"error": "Category already exists."}), 409
    old = category.name
    category.name = name
    for item in InventoryItem.query.filter_by(category=old):
        item.category = name
    db.session.commit()
    return jsonify(category.as_dict())


@legacy_bp.route("/locations", methods=["GET", "POST"])
@login_required
def manage_locations():
    if request.method == "GET":
        return jsonify([loc.as_dict() for loc in Location.query.order_by(Location.name)])
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


@legacy_bp.route("/locations/<int:location_id>", methods=["PUT", "DELETE"])
@login_required
def mutate_location(location_id: int):
    location = Location.query.get_or_404(location_id)
    if request.method == "DELETE":
        InventoryItem.query.filter_by(location=location.name).update(
            {"location": None}, synchronize_session=False
        )
        db.session.delete(location)
        db.session.commit()
        return jsonify({"status": "deleted"})
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Location name is required."}), 400
    if Location.query.filter(
        db.func.lower(Location.name) == name.lower(), Location.id != location.id
    ).first():
        return jsonify({"error": "Location already exists."}), 409
    old = location.name
    location.name = name
    for item in InventoryItem.query.filter_by(location=old):
        item.location = name
    db.session.commit()
    return jsonify(location.as_dict())
