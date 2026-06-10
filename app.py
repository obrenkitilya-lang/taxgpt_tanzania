from flask import Flask, request, jsonify, send_file, Response, stream_with_context
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
app.secret_key = os.environ.get("SECRET_KEY", "taxgpt-secret-key-change-in-production")

# Fix postgres:// -> postgresql:// for Render/Heroku
database_url = os.environ.get("DATABASE_URL", "sqlite:///taxgpt.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("RENDER") is not None
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "None" if os.environ.get("RENDER") else "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=30)
app.config["REMEMBER_COOKIE_SECURE"] = os.environ.get("RENDER") is not None
app.config["REMEMBER_COOKIE_HTTPONLY"] = True
app.config["REMEMBER_COOKIE_SAMESITE"] = "None" if os.environ.get("RENDER") else "Lax"

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({"error": "Authentication required"}), 401

# ========================
# MODELS
# ========================

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(512), nullable=False)
    country = db.Column(db.String(50), default='Tanzania')
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    is_guest = db.Column(db.Boolean, default=False)
    sessions = db.relationship('ChatSession', backref='user', lazy=True, cascade='all, delete-orphan')
    documents = db.relationship('Document', backref='user', lazy=True, cascade='all, delete-orphan')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False, default="New Chat")
    tool = db.Column(db.String(50), default="tax_research")
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade='all, delete-orphan')
    def to_dict(self):
        return {'id': self.id, 'title': self.title, 'tool': self.tool, 'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')}

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    def to_dict(self):
        return {'id': self.id, 'role': self.role, 'content': self.content, 'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M')}

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    content_text = db.Column(db.Text, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=True)
    def to_dict(self):
        return {'id': self.id, 'filename': self.filename, 'uploaded_at': self.uploaded_at.strftime('%Y-%m-%d %H:%M')}

class GuestActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False)
    activity_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class VisitorLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.String(500), nullable=True)
    page_visited = db.Column(db.String(200), nullable=True)
    is_logged_in = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    country = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class TrainingDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    filename = db.Column(db.String(255), nullable=True)
    content_text = db.Column(db.Text, nullable=False)
    doc_type = db.Column(db.String(100), nullable=False)
    source = db.Column(db.String(200), nullable=False)
    jurisdiction = db.Column(db.String(50), default='Tanzania')
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    def to_dict(self):
        return {
            'id': self.id, 'title': self.title, 'filename': self.filename,
            'doc_type': self.doc_type, 'source': self.source,
            'jurisdiction': self.jurisdiction, 'verified': self.verified,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    feedback_type = db.Column(db.String(20), nullable=False)
    question = db.Column(db.Text, nullable=True)
    answer = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    def to_dict(self):
        return {
            'id': self.id, 'action': self.action,
            'entity_type': self.entity_type, 'entity_id': self.entity_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }

CORS(app, supports_credentials=True, origins=["*"])

# ========================
# DECORATORS
# ========================

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function

def tax_professional_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'tax_professional']:
            return jsonify({"error": "Tax professional access required"}), 403
        return f(*args, **kwargs)
    return decorated_function

# ========================
# CONFIG
# ========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

TOOL_PROMPTS = {
    "tax_research": "You are a Tanzanian tax research assistant. Provide detailed explanations with references to the Income Tax Act, VAT Act, and other relevant laws.",
    "documents": "You are a tax document expert. Help users understand tax forms, notices, and other tax documents.",
    "calculators": "You are a tax calculation expert. Provide step-by-step calculations for VAT, PAYE, SDL, WCF, corporate tax, and other Tanzanian taxes.",
    "deadlines": "You are a tax compliance expert. Provide specific filing deadlines and explain penalties for late filing.",
    "business_setup": "You are a business registration advisor. Explain TIN registration, tax clearance, VAT registration, and ongoing compliance requirements."
}

GUEST_CHAT_LIMIT = 10
GUEST_DOCUMENT_LIMIT = 2
GUEST_CALCULATOR_LIMIT = 10

# ========================
# HELPERS
# ========================

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or 'unknown'

def track_visitor(page=None):
    try:
        ip = get_client_ip()
        user_agent = request.headers.get("User-Agent", "")[:500]
        visitor = VisitorLog(
            ip_address=ip, user_agent=user_agent,
            page_visited=page or request.path,
            is_logged_in=current_user.is_authenticated,
            user_id=current_user.id if current_user.is_authenticated else None,
            country=current_user.country if current_user.is_authenticated else None
        )
        db.session.add(visitor)
        db.session.commit()
    except Exception as e:
        print("Visitor tracking error: " + str(e))

def check_guest_limit(activity_type, limit):
    if current_user.is_authenticated:
        return True, None
    try:
        ip = get_client_ip()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        count = GuestActivity.query.filter(
            GuestActivity.ip_address == ip,
            GuestActivity.activity_type == activity_type,
            GuestActivity.created_at >= today
        ).count()
        if count >= limit:
            return False, "Guest limit reached. You have used " + str(limit) + " " + activity_type + " actions today. Please sign up for unlimited access."
        activity = GuestActivity(ip_address=ip, activity_type=activity_type)
        db.session.add(activity)
        db.session.commit()
        remaining = limit - count - 1
        return True, remaining
    except Exception as e:
        print("Guest limit check error: " + str(e))
        return True, None

def log_audit(action, entity_type=None, entity_id=None):
    try:
        user_id = current_user.id if current_user.is_authenticated else None
        log = AuditLog(user_id=user_id, action=action, entity_type=entity_type, entity_id=entity_id)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Audit log error: {e}")

def call_openai_chat(system_prompt, user_message, stream=False):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        training_docs = TrainingDocument.query.filter_by(verified=True).limit(5).all()
        if training_docs:
            context = "\n\n--- REFERENCE DOCUMENTS ---\n"
            for doc in training_docs:
                context += f"\n[{doc.title}]:\n{doc.content_text[:2000]}\n"
            system_prompt = system_prompt + context
    except:
        pass

    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "stream": stream
    }
    if stream:
        return requests.post(OPENAI_API_URL, headers=headers, json=data, stream=True)
    else:
        response = requests.post(OPENAI_API_URL, headers=headers, json=data)
        return response.json()

# ========================
# AUTH ROUTES
# ========================

@app.route("/api/auth/me", methods=["GET"])
def get_current_user():
    if current_user.is_authenticated:
        # Force reload from DB to get latest role
        user = db.session.get(User, current_user.id)
        if user:
            return jsonify({
                "logged_in": True,
                "email": user.email,
                "country": user.country,
                "role": user.role,
                "is_guest": user.is_guest
            })
    return jsonify({"logged_in": False})

@app.route("/api/auth/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        country = data.get("country", "Tanzania").strip()
        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400
        if country not in ['Tanzania', 'Kenya', 'Uganda']:
            return jsonify({"error": "Country must be Tanzania, Kenya, or Uganda"}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already registered"}), 400
        is_first_user = User.query.count() == 0
        role = 'admin' if is_first_user else 'user'
        hashed_password = generate_password_hash(password)
        user = User(email=email, password=hashed_password, country=country, role=role, is_guest=False)
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        log_audit("signup", "user", user.id)
        return jsonify({"message": "Account created successfully", "email": user.email, "country": user.country, "role": user.role})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            return jsonify({"error": "Invalid email or password"}), 401
        login_user(user, remember=True)
        log_audit("login", "user", user.id)
        return jsonify({"message": "Login successful", "email": user.email, "country": user.country, "role": user.role})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    if current_user.is_authenticated:
        log_audit("logout", "user", current_user.id)
        logout_user()
    return jsonify({"message": "Logged out successfully"})

@app.route("/api/auth/change-password", methods=["POST"])
@login_required
def change_password():
    try:
        data = request.get_json()
        current_password = data.get("current_password", "")
        new_password = data.get("new_password", "")
        if not current_password or not new_password:
            return jsonify({"error": "Current password and new password are required"}), 400
        if len(new_password) < 6:
            return jsonify({"error": "New password must be at least 6 characters"}), 400
        if not check_password_hash(current_user.password, current_password):
            return jsonify({"error": "Current password is incorrect"}), 401
        current_user.password = generate_password_hash(new_password)
        db.session.commit()
        log_audit("change_password", "user", current_user.id)
        return jsonify({"message": "Password changed successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ========================
# PAGE ROUTES
# ========================

@app.route('/')
def home():
    return send_file('frontend/index_fixed.html')

@app.route('/admin')
def admin_page():
    return send_file('frontend/index_fixed.html')

@app.route('/<tool>')
def tool_page(tool):
    valid_tools = ['tax_research', 'documents', 'calculators', 'deadlines', 'business_setup']
    if tool in valid_tools:
        return send_file('frontend/index_fixed.html')
    return "Tool not found", 404

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            return """<script>window.location.href='/';</script>"""
        return """<script>alert('Invalid credentials');window.location.href='/login';</script>"""
    return """
<!DOCTYPE html><html><head><title>TaxGPT Login</title>
<style>body{background:#020817;display:flex;justify-content:center;align-items:center;height:100vh;font-family:Arial;color:white;margin:0}.card{background:#07123a;padding:40px;border-radius:20px;width:400px}input{width:100%;padding:15px;margin-top:15px;background:#020817;border:1px solid #334155;color:white;border-radius:10px;box-sizing:border-box}button{width:100%;padding:15px;margin-top:20px;background:#d9ff00;border:none;border-radius:10px;font-weight:bold;cursor:pointer;font-size:16px}</style>
</head><body><div class="card">
<div style="display:flex;justify-content:space-between;margin-bottom:20px">
<a href="/" style="color:white;text-decoration:none;font-weight:bold">← Home</a>
<a href="/signup" style="color:#d9ff00;text-decoration:none;font-weight:bold">Sign Up</a></div>
<h1>TaxGPT Login</h1>
<form method="POST"><input name="email" placeholder="Email" type="email" required><input name="password" placeholder="Password" type="password" required><button type="submit">Login</button></form>
</div></body></html>"""

@app.route("/signup", methods=["GET", "POST"])
def signup_page():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        country = request.form.get("country", "Tanzania").strip()
        if not email or not password:
            return """<script>alert('All fields required');window.location.href='/signup';</script>"""
        if len(password) < 6:
            return """<script>alert('Password must be at least 6 characters');window.location.href='/signup';</script>"""
        if User.query.filter_by(email=email).first():
            return """<script>alert('Email already registered');window.location.href='/signup';</script>"""
        if country not in ['Tanzania', 'Kenya', 'Uganda']:
            return """<script>alert('Country must be Tanzania, Kenya, or Uganda');window.location.href='/signup';</script>"""
        hashed_password = generate_password_hash(password)
        is_first_user = User.query.count() == 0
        role = 'admin' if is_first_user else 'user'
        user = User(email=email, password=hashed_password, country=country, role=role, is_guest=False)
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        return """<script>window.location.href='/';</script>"""
    return """
<!DOCTYPE html><html><head><title>TaxGPT Sign Up</title>
<style>body{background:#020817;display:flex;justify-content:center;align-items:center;height:100vh;font-family:Arial;color:white;margin:0}.card{background:#07123a;padding:40px;border-radius:20px;width:400px}input,select{width:100%;padding:15px;margin-top:15px;background:#020817;border:1px solid #334155;color:white;border-radius:10px;box-sizing:border-box}button{width:100%;padding:15px;margin-top:20px;background:#d9ff00;border:none;border-radius:10px;font-weight:bold;cursor:pointer;font-size:16px}</style>
</head><body><div class="card">
<div style="display:flex;justify-content:space-between;margin-bottom:20px">
<a href="/" style="color:white;text-decoration:none;font-weight:bold">← Home</a>
<a href="/login" style="color:#d9ff00;text-decoration:none;font-weight:bold">Login</a></div>
<h1>TaxGPT Sign Up</h1>
<form method="POST"><input name="email" placeholder="Email" type="email" required><input name="password" placeholder="Password" type="password" required>
<select name="country" required><option value="Tanzania">Tanzania</option><option value="Kenya">Kenya</option><option value="Uganda">Uganda</option></select>
<button type="submit">Create Account</button></form>
</div></body></html>"""

# ========================
# SESSION ROUTES
# ========================

@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    try:
        if current_user.is_authenticated:
            sessions = ChatSession.query.filter_by(user_id=current_user.id).order_by(ChatSession.created_at.desc()).all()
        else:
            sessions = []
        return jsonify([s.to_dict() for s in sessions])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sessions/<int:session_id>", methods=["GET"])
def get_session_messages(session_id):
    try:
        session = db.session.get(ChatSession, session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        if current_user.is_authenticated and session.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403
        messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
        return jsonify([m.to_dict() for m in messages])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sessions/<int:session_id>", methods=["DELETE"])
def delete_session(session_id):
    try:
        session = db.session.get(ChatSession, session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        if current_user.is_authenticated and session.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403
        db.session.delete(session)
        db.session.commit()
        return jsonify({"message": "Session deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# CHAT ROUTE
# ========================

@app.route("/ask", methods=["POST"])
def ask():
    try:
        allowed, msg = check_guest_limit('chat', GUEST_CHAT_LIMIT)
        if not allowed:
            return jsonify({"error": msg, "limit_reached": True}), 403
        data = request.get_json()
        question = data.get("question")
        session_id = data.get("session_id")
        tool = data.get("tool", "tax_research")
        if not question:
            return jsonify({"error": "No question provided"}), 400
        system_prompt = TOOL_PROMPTS.get(tool, TOOL_PROMPTS["tax_research"])
        if session_id:
            chat_session = db.session.get(ChatSession, session_id)
            if not chat_session:
                chat_session = ChatSession(title=question[:50], tool=tool, user_id=current_user.id if current_user.is_authenticated else None)
                db.session.add(chat_session)
                db.session.commit()
            elif current_user.is_authenticated and chat_session.user_id != current_user.id:
                return jsonify({"error": "Unauthorized"}), 403
        else:
            chat_session = ChatSession(title=question[:50], tool=tool, user_id=current_user.id if current_user.is_authenticated else None)
            db.session.add(chat_session)
            db.session.commit()
        user_msg = ChatMessage(session_id=chat_session.id, role='user', content=question)
        db.session.add(user_msg)
        db.session.commit()
        def generate():
            full_response = ""
            yield "data: " + json.dumps({'type': 'session', 'session_id': chat_session.id}) + "\n\n"
            response = call_openai_chat(system_prompt, question, stream=True)
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data_str)
                            if chunk.get('choices') and chunk['choices'][0].get('delta') and chunk['choices'][0]['delta'].get('content'):
                                text = chunk['choices'][0]['delta']['content']
                                full_response += text
                                yield "data: " + json.dumps({'type': 'token', 'content': text}) + "\n\n"
                        except:
                            pass
            ai_msg = ChatMessage(session_id=chat_session.id, role='ai', content=full_response)
            db.session.add(ai_msg)
            db.session.commit()
            yield "data: " + json.dumps({'type': 'done', 'remaining': msg if isinstance(msg, int) else None}) + "\n\n"
        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# CALCULATOR ROUTES
# ========================

@app.route("/api/calculate/paye", methods=["POST"])
def calculate_paye():
    try:
        allowed, msg = check_guest_limit('calculator', GUEST_CALCULATOR_LIMIT)
        if not allowed:
            return jsonify({"error": msg, "limit_reached": True}), 403
        data = request.get_json()
        gross_salary = float(data.get("gross_salary", 0))
        nssf = gross_salary * 0.10
        taxable_pay = gross_salary - nssf
        if taxable_pay <= 270000: paye = 0
        elif taxable_pay <= 520000: paye = (taxable_pay - 270000) * 0.08
        elif taxable_pay <= 760000: paye = 20000 + (taxable_pay - 520000) * 0.20
        elif taxable_pay <= 1000000: paye = 68000 + (taxable_pay - 760000) * 0.25
        else: paye = 128000 + (taxable_pay - 1000000) * 0.30
        wcf = gross_salary * 0.01
        net_pay = gross_salary - nssf - paye
        return jsonify({"gross_salary": gross_salary, "nssf": nssf, "paye": paye, "wcf": wcf, "net_pay": net_pay, "taxable_pay": taxable_pay, "remaining": msg if isinstance(msg, int) else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/calculate/vat", methods=["POST"])
def calculate_vat():
    try:
        allowed, msg = check_guest_limit('calculator', GUEST_CALCULATOR_LIMIT)
        if not allowed:
            return jsonify({"error": msg, "limit_reached": True}), 403
        data = request.get_json()
        amount = float(data.get("amount", 0))
        vat_amount = amount * 0.18
        total = amount + vat_amount
        return jsonify({"amount": amount, "vat_rate": "18%", "vat_amount": vat_amount, "total": total, "remaining": msg if isinstance(msg, int) else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/calculate/sdl", methods=["POST"])
def calculate_sdl():
    try:
        allowed, msg = check_guest_limit('calculator', GUEST_CALCULATOR_LIMIT)
        if not allowed:
            return jsonify({"error": msg, "limit_reached": True}), 403
        data = request.get_json()
        gross_payroll = float(data.get("gross_payroll", 0))
        sdl_amount = gross_payroll * 0.04
        return jsonify({"gross_payroll": gross_payroll, "sdl_rate": "4%", "sdl_amount": sdl_amount, "total_cost": gross_payroll + sdl_amount, "remaining": msg if isinstance(msg, int) else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/calculate/wcf", methods=["POST"])
def calculate_wcf():
    try:
        allowed, msg = check_guest_limit('calculator', GUEST_CALCULATOR_LIMIT)
        if not allowed:
            return jsonify({"error": msg, "limit_reached": True}), 403
        data = request.get_json()
        gross_payroll = float(data.get("gross_payroll", 0))
        wcf_amount = gross_payroll * 0.01
        return jsonify({"gross_payroll": gross_payroll, "wcf_rate": "1%", "wcf_amount": wcf_amount, "total_cost": gross_payroll + wcf_amount, "remaining": msg if isinstance(msg, int) else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/calculate/corporate_tax", methods=["POST"])
def calculate_corporate_tax():
    try:
        allowed, msg = check_guest_limit('calculator', GUEST_CALCULATOR_LIMIT)
        if not allowed:
            return jsonify({"error": msg, "limit_reached": True}), 403
        data = request.get_json()
        taxable_income = float(data.get("taxable_income", 0))
        tax_amount = taxable_income * 0.30
        net_income = taxable_income - tax_amount
        return jsonify({"taxable_income": taxable_income, "tax_rate": "30%", "tax_amount": tax_amount, "net_income": net_income, "remaining": msg if isinstance(msg, int) else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/calculate/withholding", methods=["POST"])
def calculate_withholding():
    try:
        allowed, msg = check_guest_limit('calculator', GUEST_CALCULATOR_LIMIT)
        if not allowed:
            return jsonify({"error": msg, "limit_reached": True}), 403
        data = request.get_json()
        payment_amount = float(data.get("payment_amount", 0))
        payment_type = data.get("payment_type", "dividends")
        rates = {"dividends": 0.10, "interest": 0.10, "royalties": 0.15, "rent": 0.10, "services": 0.05, "consulting": 0.15}
        rate = rates.get(payment_type, 0.10)
        withholding_amount = payment_amount * rate
        net_payment = payment_amount - withholding_amount
        return jsonify({"payment_amount": payment_amount, "payment_type": payment_type, "withholding_rate": f"{rate*100}%", "withholding_amount": withholding_amount, "net_payment": net_payment, "remaining": msg if isinstance(msg, int) else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# DOCUMENT ROUTES
# ========================

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/api/documents", methods=["GET"])
def get_documents():
    try:
        if current_user.is_authenticated:
            docs = Document.query.filter_by(user_id=current_user.id).order_by(Document.uploaded_at.desc()).all()
        else:
            docs = []
        return jsonify([d.to_dict() for d in docs])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/documents/upload", methods=["POST"])
def upload_document():
    try:
        allowed, msg = check_guest_limit('document', GUEST_DOCUMENT_LIMIT)
        if not allowed:
            return jsonify({"error": msg, "limit_reached": True}), 403
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        if not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type. Allowed: PDF, DOC, DOCX, TXT, PNG, JPG"}), 400
        filename = secure_filename(file.filename)
        content_text = ""
        if filename.lower().endswith('.pdf'):
            try:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    content_text += page.extract_text() + "\n"
            except Exception as e:
                content_text = f"Could not extract text: {str(e)}"
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            content_text = "[Image uploaded - visual analysis available via chat]"
        else:
            content_text = file.read().decode('utf-8', errors='ignore')
        doc = Document(filename=filename, content_text=content_text, user_id=current_user.id if current_user.is_authenticated else None)
        db.session.add(doc)
        db.session.commit()
        return jsonify({"message": "Document uploaded successfully", "document": doc.to_dict(), "content_preview": content_text[:500] if content_text else "", "remaining": msg if isinstance(msg, int) else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/documents/<int:doc_id>", methods=["GET"])
def get_document(doc_id):
    try:
        doc = db.session.get(Document, doc_id)
        if not doc:
            return jsonify({"error": "Not found"}), 404
        if current_user.is_authenticated and doc.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403
        return jsonify({"id": doc.id, "filename": doc.filename, "content_text": doc.content_text, "uploaded_at": doc.uploaded_at.strftime('%Y-%m-%d %H:%M')})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/documents/<int:doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    try:
        doc = db.session.get(Document, doc_id)
        if not doc:
            return jsonify({"error": "Not found"}), 404
        if current_user.is_authenticated and doc.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403
        db.session.delete(doc)
        db.session.commit()
        return jsonify({"message": "Document deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/documents/analyze", methods=["POST"])
def analyze_document():
    try:
        allowed, msg = check_guest_limit('chat', GUEST_CHAT_LIMIT)
        if not allowed:
            return jsonify({"error": msg, "limit_reached": True}), 403
        data = request.get_json()
        doc_id = data.get("document_id")
        question = data.get("question", "Analyze this tax document")
        doc = db.session.get(Document, doc_id)
        if not doc:
            return jsonify({"error": "Document not found"}), 404
        if current_user.is_authenticated and doc.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403
        chat_session = ChatSession(title=f"Doc: {doc.filename[:30]}", tool="documents", user_id=current_user.id if current_user.is_authenticated else None)
        db.session.add(chat_session)
        db.session.commit()
        user_msg = ChatMessage(session_id=chat_session.id, role='user', content=f"[Document: {doc.filename}] {question}")
        db.session.add(user_msg)
        db.session.commit()
        doc_content = doc.content_text[:3000] if doc.content_text else "No text content available."
        doc_prompt = "Document content:\n" + doc_content + "\n\nQuestion: " + question
        result = call_openai_chat(TOOL_PROMPTS["documents"], doc_prompt)
        answer = result['choices'][0]['message']['content']
        ai_msg = ChatMessage(session_id=chat_session.id, role='ai', content=answer)
        db.session.add(ai_msg)
        db.session.commit()
        return jsonify({"answer": answer, "session_id": chat_session.id, "document_id": doc.id, "remaining": msg if isinstance(msg, int) else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# FEEDBACK ROUTES
# ========================

@app.route("/api/feedback", methods=["POST"])
def submit_feedback():
    try:
        data = request.get_json()
        feedback = Feedback(
            session_id=data.get("session_id"),
            user_id=current_user.id if current_user.is_authenticated else None,
            feedback_type=data.get("feedback_type", "helpful"),
            question=data.get("question", "")[:1000],
            answer=data.get("answer", "")[:2000]
        )
        db.session.add(feedback)
        db.session.commit()
        return jsonify({"message": "Feedback recorded"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/feedback/stats", methods=["GET"])
def feedback_stats():
    try:
        helpful = Feedback.query.filter_by(feedback_type='helpful').count()
        incomplete = Feedback.query.filter_by(feedback_type='incomplete').count()
        incorrect = Feedback.query.filter_by(feedback_type='incorrect').count()
        return jsonify({"helpful": helpful, "incomplete": incomplete, "incorrect": incorrect})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# ADMIN ROUTES
# ========================

@app.route("/api/admin/stats", methods=["GET"])
@admin_required
def admin_stats():
    try:
        total_users = User.query.count()
        total_sessions = ChatSession.query.count()
        total_messages = ChatMessage.query.count()
        total_docs = Document.query.count()
        return jsonify({
            "users": {"total": total_users},
            "activity": {"sessions": total_sessions, "messages": total_messages, "documents": total_docs}
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/visitors", methods=["GET"])
@admin_required
def admin_visitors():
    try:
        total_visitors = db.session.query(db.func.count(db.distinct(VisitorLog.ip_address))).scalar() or 0
        total_visits = VisitorLog.query.count()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_visitors = VisitorLog.query.filter(VisitorLog.created_at >= today).count()
        today_unique = db.session.query(db.func.count(db.distinct(VisitorLog.ip_address))).filter(VisitorLog.created_at >= today).scalar() or 0
        country_stats = db.session.query(VisitorLog.country, db.func.count(db.distinct(VisitorLog.ip_address))).filter(VisitorLog.country.isnot(None)).group_by(VisitorLog.country).all()
        recent = VisitorLog.query.order_by(VisitorLog.created_at.desc()).limit(50).all()
        return jsonify({
            "total_visitors": total_visitors, "total_visits": total_visits,
            "today_visitors": today_visitors, "today_unique": today_unique,
            "country_stats": [{"country": c, "count": count} for c, count in country_stats],
            "recent_visitors": [{"ip": v.ip_address, "page": v.page_visited, "is_logged_in": v.is_logged_in, "country": v.country, "time": v.created_at.strftime("%Y-%m-%d %H:%M")} for v in recent]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/users-detailed", methods=["GET"])
@admin_required
def admin_users_detailed():
    try:
        users = User.query.order_by(User.created_at.desc()).all()
        return jsonify([{
            "id": u.id, "email": u.email, "country": u.country, "role": u.role,
            "is_guest": u.is_guest,
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else None,
            "session_count": ChatSession.query.filter_by(user_id=u.id).count(),
            "document_count": Document.query.filter_by(user_id=u.id).count()
        } for u in users])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/users/<int:user_id>/role", methods=["PUT"])
@admin_required
def update_user_role(user_id):
    try:
        data = request.get_json()
        new_role = data.get("role")
        if new_role not in ['user', 'admin', 'tax_professional']:
            return jsonify({"error": "Invalid role"}), 400
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        old_role = user.role
        user.role = new_role
        db.session.commit()
        log_audit("update_role", "user", user_id)
        return jsonify({"message": f"Role updated from {old_role} to {new_role}", "user_id": user.id, "email": user.email, "new_role": new_role})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/training-docs", methods=["GET"])
@admin_required
def get_training_docs():
    try:
        docs = TrainingDocument.query.order_by(TrainingDocument.created_at.desc()).all()
        return jsonify([d.to_dict() for d in docs])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/training-docs/upload", methods=["POST"])
@admin_required
def upload_training_doc():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        title = request.form.get("title", file.filename)
        doc_type = request.form.get("doc_type", "general")
        jurisdiction = request.form.get("jurisdiction", "Tanzania")
        filename = secure_filename(file.filename)
        content_text = ""
        if filename.lower().endswith(".pdf"):
            try:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    content_text += page.extract_text() + "\n"
            except Exception as e:
                content_text = "Could not extract text: " + str(e)
        else:
            content_text = file.read().decode("utf-8", errors="ignore")
        doc = TrainingDocument(
            title=title, filename=filename,
            content_text=content_text[:50000],
            doc_type=doc_type, source="admin_upload",
            jurisdiction=jurisdiction,
            uploaded_by=current_user.id,
            verified=True
        )
        db.session.add(doc)
        db.session.commit()
        log_audit("upload_training_doc", "training_document", doc.id)
        return jsonify({"message": "Training document uploaded", "document": doc.to_dict()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/training-docs/<int:doc_id>", methods=["DELETE"])
@admin_required
def delete_training_doc(doc_id):
    try:
        doc = db.session.get(TrainingDocument, doc_id)
        if not doc:
            return jsonify({"error": "Document not found"}), 404
        db.session.delete(doc)
        db.session.commit()
        log_audit("delete_training_doc", "training_document", doc_id)
        return jsonify({"message": "Training document deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/audit-logs", methods=["GET"])
@admin_required
def admin_audit_logs():
    try:
        logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
        return jsonify([l.to_dict() for l in logs])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# STUB ROUTES
# ========================

@app.route("/api/precedents", methods=["GET", "POST"])
@admin_required
def precedents():
    return jsonify([])

@app.route("/api/precedents/search", methods=["POST"])
@admin_required
def search_precedents():
    return jsonify([])

@app.route("/api/jurisdictions", methods=["GET", "POST"])
def jurisdictions():
    return jsonify([{"code": "TZ", "name": "Tanzania", "currency": "TZS", "tax_authority": "TRA", "active": True},
                    {"code": "KE", "name": "Kenya", "currency": "KES", "tax_authority": "KRA", "active": True},
                    {"code": "UG", "name": "Uganda", "currency": "UGX", "tax_authority": "URA", "active": True}])

# ========================
# UTILITY ROUTES
# ========================

@app.route("/api/test")
def test():
    return jsonify({"status": "ok", "db": "connected"})

# ADMIN BOOTSTRAP — makes any existing user admin by email
@app.route("/api/make-admin/<path:email>")
def make_admin(email):
    """Bootstrap route to grant admin access. Remove after initial setup."""
    secret = request.args.get("secret", "")
    bootstrap_secret = os.environ.get("BOOTSTRAP_SECRET", "taxgpt-bootstrap-2024")
    if secret != bootstrap_secret:
        return jsonify({"error": "Invalid secret. Add ?secret=taxgpt-bootstrap-2024 to the URL"}), 403
    email = email.strip().lower()
    try:
        user = User.query.filter_by(email=email).first()
        if not user:
            hashed_password = generate_password_hash("TaxGPT2024!")
            user = User(email=email, password=hashed_password, country="Tanzania", role="admin", is_guest=False)
            db.session.add(user)
            db.session.commit()
            return jsonify({"message": f"Created admin account for {email}", "temp_password": "TaxGPT2024!", "note": "Change your password after login"})
        else:
            user.role = "admin"
            db.session.commit()
            return jsonify({"message": f"{email} is now admin"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ========================
# DATABASE MIGRATION
# ========================

def migrate_db():
    with app.app_context():
        try:
            db.create_all()
            print("Database ready.")
        except Exception as e:
            print(f"Migration warning: {e}")
            db.session.rollback()

migrate_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)