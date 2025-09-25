import os
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


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///inventory.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

db = SQLAlchemy(app)


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

    return render_template("inventory_form.html", item=None, action="Create")


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

    return render_template("inventory_form.html", item=item, action="Update")


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
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(
        buffer,
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


@app.before_first_request
def create_tables():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
