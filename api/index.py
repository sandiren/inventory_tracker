# api/index.py
from app import app            # reuse the existing Flask app from app.py
from flask import jsonify

@app.get("/health")            # keep path simple; you'll hit /health
def health():
    return jsonify(ok=True)