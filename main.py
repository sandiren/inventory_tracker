from datetime import datetime

from flask import Flask, redirect, render_template_string, request, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///inventory.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)


TEMPLATE = """
<!doctype html>
<title>Inventory Tracker</title>
<h1>Inventory Items</h1>
<form method="post" action="{{ url_for('add_item') }}">
  <label for="name">Name</label>
  <input id="name" name="name" required>
  <label for="quantity">Quantity</label>
  <input id="quantity" name="quantity" type="number" min="0" value="0">
  <button type="submit">Add Item</button>
</form>
<ul>
  {% for item in items %}
    <li>{{ item.name }} — {{ item.quantity }} (added {{ item.added_at.strftime('%Y-%m-%d %H:%M') }})</li>
  {% else %}
    <li>No inventory items yet.</li>
  {% endfor %}
</ul>
"""


@app.route("/")
def index():
    items = InventoryItem.query.order_by(InventoryItem.added_at.desc()).all()
    return render_template_string(TEMPLATE, items=items)


@app.post("/add")
def add_item():
    name = request.form.get("name", "").strip()
    quantity = request.form.get("quantity", "0").strip()

    if not name:
        return redirect(url_for("index"))

    try:
        quantity_value = int(quantity)
    except ValueError:
        quantity_value = 0

    item = InventoryItem(name=name, quantity=max(quantity_value, 0))
    db.session.add(item)
    db.session.commit()
    return redirect(url_for("index"))


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
