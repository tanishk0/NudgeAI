from flask import Flask, jsonify, render_template
from demo import run_demo

app = Flask(__name__)

@app.get("/")
def home():
    return render_template("index.html")

@app.post("/api/run")
def run():
    return jsonify(run_demo())
