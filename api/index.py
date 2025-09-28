from flask import Flask, jsonify
app = Flask(__name__)

@app.get("/api/health")
def health():
  return jsonify(ok=True)