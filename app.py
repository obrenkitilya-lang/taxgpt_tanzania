from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
from dotenv import load_dotenv
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import PyPDF2
import json
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "taxgpt-secret-key")
database_url = os.environ.get("DATABASE_URL", "sqlite:///taxgpt.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    country = db.Column(db.String(50), default='Tanzania')
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    is_guest = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/api/create-admin/<email>")
def create_admin(email):
    try:
        user = User.query.filter_by(email=email.lower()).first()
        if not user:
            hashed_password = generate_password_hash("temp123")
            user = User(email=email.lower(), password=hashed_password, country="Tanzania", role="admin", is_guest=False)
            db.session.add(user)
            db.session.commit()
            return jsonify({"message": f"Created {email} as admin", "password": "temp123"})
        else:
            user.role = "admin"
            db.session.commit()
            return jsonify({"message": f"{email} is now admin"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/test")
def test():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
