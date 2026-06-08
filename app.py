from flask import Flask, request, jsonify, send_file, Response, stream_with_context
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import tempfile
import PyPDF2
import json
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "taxgpt-secret-key-change-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///taxgpt.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Session configuration for cross-domain persistence
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ========================
# DATABASE MODELS
# ========================

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    country = db.Column(db.String(50), default='Tanzania')
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    is_guest = db.Column(db.Boolean, default=False)

    sessions = db.relationship('ChatSession', backref='user', lazy=True, cascade='all, delete-orphan')
    documents = db.relationship('Document', backref='user', lazy=True, cascade='all, delete-orphan')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False, default="New Chat")
    tool = db.Column(db.String(50), default="tax_research")
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'tool': self.tool,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M')
        }

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    content_text = db.Column(db.Text, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'uploaded_at': self.uploaded_at.strftime('%Y-%m-%d %H:%M')
        }

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
            'id': self.id,
            'title': self.title,
            'filename': self.filename,
            'doc_type': self.doc_type,
            'source': self.source,
            'jurisdiction': self.jurisdiction,
            'verified': self.verified,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }

CORS(app, supports_credentials=True)

# Role-based access decorators
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

# OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# Tool-specific system prompts
TOOL_PROMPTS = {
    "tax_research": "You are a Tanzanian tax research assistant. Provide detailed explanations with references to the Income Tax Act, VAT Act, and other relevant laws.",
    "documents": "You are a tax document expert. Help users understand tax forms, notices, and other tax documents.",
    "calculators": "You are a tax calculation expert. Provide step-by-step calculations for VAT, PAYE, SDL, WCF, corporate tax, and other Tanzanian taxes.",
    "deadlines": "You are a tax compliance expert. Provide specific filing deadlines and explain penalties for late filing.",
    "business_setup": "You are a business registration advisor. Explain TIN registration, tax clearance, VAT registration, and ongoing compliance requirements."
}

# Guest limits
GUEST_CHAT_LIMIT = 10
GUEST_DOCUMENT_LIMIT = 2
GUEST_CALCULATOR_LIMIT = 10

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or 'unknown'

def track_visitor(page=None):
    try:
        ip = get_client_ip()
        user_agent = request.headers.get("User-Agent", "")[:500]

        visitor = VisitorLog(
            ip_address=ip,
            user_agent=user_agent,
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

# ========================
# AUDIT LOG HELPER
# ========================

def log_audit(action, entity_type, entity_id):
    """Simple audit logging. Expand later with AuditLog table if needed."""
    user_id = current_user.id if current_user.is_authenticated else None
    print(f"AUDIT: {action} on {entity_type} id={entity_id} by user={user_id}")

# ========================
# AUTH ROUTES
# ========================

@app.route("/api/auth/me", methods=["GET"])
def get_current_user():
    if current_user.is_authenticated:
        return jsonify({
            "logged_in": True,
            "email": current_user.email,
            "country": current_user.country,
            "role": current_user.role,
            "is_guest": current_user.is_guest
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

        # AUTO-ADMIN: First user ever becomes admin automatically
        is_first_user = User.query.count() == 0
        role = 'admin' if is_first_user else 'user'

        hashed_password = generate_password_hash(password)
        user = User(
            email=email, 
            password=hashed_password, 
            country=country, 
            role=role,
            is_guest=False
        )
        db.session.add(user)
        db.session.commit()

        login_user(user, remember=True)

        return jsonify({
            "message": "Account created successfully",
            "email": user.email,
            "country": user.country,
            "role": user.role
        })
    except Exception as e:
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

        return jsonify({
            "message": "Login successful",
            "email": user.email,
            "country": user.country,
            "role": user.role
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/auth/logout", methods=["POST"])
@login_required
def api_logout():
    logout_user()
    return jsonify({"message": "Logged out successfully"})

# ========================
# FRONTEND PAGES
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
<!DOCTYPE html>
<html>
<head>
<title>TaxGPT Login</title>
<style>
body{background:#020817;display:flex;justify-content:center;align-items:center;height:100vh;font-family:Arial;color:white;margin:0}
.card{background:#07123a;padding:40px;border-radius:20px;width:400px}
input{width:100%;padding:15px;margin-top:15px;background:#020817;border:1px solid #334155;color:white;border-radius:10px;box-sizing:border-box}
button{width:100%;padding:15px;margin-top:20px;background:#d9ff00;border:none;border-radius:10px;font-weight:bold;cursor:pointer;font-size:16px}
button:hover{background:#c8e600}
</style>
</head>
<body>
<div class="card">
<div style="display:flex;justify-content:space-between;margin-bottom:20px">
<a href="/" style="color:white;text-decoration:none;font-weight:bold">← Home</a>
<a href="/signup" style="color:#d9ff00;text-decoration:none;font-weight:bold">Sign Up</a>
</div>
<h1>TaxGPT Login</h1>
<form method="POST">
<input name="email" placeholder="Email" type="email" required>
<input name="password" placeholder="Password" type="password" required>
<button type="submit">Login</button>
</form>
</div>
</body>
</html>
"""

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
        user = User(
            email=email, 
            password=hashed_password, 
            country=country, 
            role='user',
            is_guest=False
        )
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        return """<script>window.location.href='/';</script>"""

    return """
<!DOCTYPE html>
<html>
<head>
<title>TaxGPT Sign Up</title>
<style>
body{background:#020817;display:flex;justify-content:center;align-items:center;height:100vh;font-family:Arial;color:white;margin:0}
.card{background:#07123a;padding:40px;border-radius:20px;width:400px}
input,select{width:100%;padding:15px;margin-top:15px;background:#020817;border:1px solid #334155;color:white;border-radius:10px;box-sizing:border-box}
select{color:white;background:#020817}
option{background:#07123a;color:white}
button{width:100%;padding:15px;margin-top:20px;background:#d9ff00;border:none;border-radius:10px;font-weight:bold;cursor:pointer;font-size:16px}
button:hover{background:#c8e600}
</style>
</head>
<body>
<div class="card">
<div style="display:flex;justify-content:space-between;margin-bottom:20px">
<a href="/" style="color:white;text-decoration:none;font-weight:bold">← Home</a>
<a href="/login" style="color:#d9ff00;text-decoration:none;font-weight:bold">Login</a>
</div>
<h1>TaxGPT Sign Up</h1>
<form method="POST">
<input name="email" placeholder="Email" type="email" required>
<input name="password" placeholder="Password" type="password" required>
<select name="country" required>
<option value="Tanzania">Tanzania</option>
<option value="Kenya">Kenya</option>
<option value="Uganda">Uganda</option>
</select>
<button type="submit">Create Account</button>
</form>
</div>
</body>
</html>
"""

# ========================
# API ROUTES
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
        session = ChatSession.query.get_or_404(session_id)
        if current_user.is_authenticated and session.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403

        messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
        return jsonify([m.to_dict() for m in messages])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sessions/<int:session_id>", methods=["DELETE"])
def delete_session(session_id):
    try:
        session = ChatSession.query.get_or_404(session_id)
        if current_user.is_authenticated and session.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403

        db.session.delete(session)
        db.session.commit()
        return jsonify({"message": "Session deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# STREAMING CHAT API
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
            chat_session = ChatSession.query.get(session_id)
            if not chat_session:
                chat_session = ChatSession(
                    title=question[:50], 
                    tool=tool, 
                    user_id=current_user.id if current_user.is_authenticated else None
                )
                db.session.add(chat_session)
                db.session.commit()
            elif current_user.is_authenticated and chat_session.user_id != current_user.id:
                return jsonify({"error": "Unauthorized"}), 403
        else:
            chat_session = ChatSession(
                title=question[:50], 
                tool=tool, 
                user_id=current_user.id if current_user.is_authenticated else None
            )
            db.session.add(chat_session)
            db.session.commit()

        user_msg = ChatMessage(session_id=chat_session.id, role='user', content=question)
        db.session.add(user_msg)
        db.session.commit()

        def generate():
            full_response = ""

            yield f"data: {json.dumps({'type': 'session', 'session_id': chat_session.id})}\n\n"

            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                stream=True
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_response += text
                    yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"

            ai_msg = ChatMessage(session_id=chat_session.id, role='ai', content=full_response)
            db.session.add(ai_msg)
            db.session.commit()

            yield f"data: {json.dumps({'type': 'done', 'remaining': msg if isinstance(msg, int) else None})}\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# CALCULATOR APIs
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

        if taxable_pay <= 270000:
            paye = 0
        elif taxable_pay <= 520000:
            paye = (taxable_pay - 270000) * 0.08
        elif taxable_pay <= 760000:
            paye = 20000 + (taxable_pay - 520000) * 0.20
        elif taxable_pay <= 1000000:
            paye = 68000 + (taxable_pay - 760000) * 0.25
        else:
            paye = 128000 + (taxable_pay - 1000000) * 0.30

        wcf = gross_salary * 0.01
        net_pay = gross_salary - nssf - paye

        return jsonify({
            "gross_salary": gross_salary,
            "nssf": nssf,
            "paye": paye,
            "wcf": wcf,
            "net_pay": net_pay,
            "taxable_pay": taxable_pay,
            "remaining": msg if isinstance(msg, int) else None
        })
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
        vat_rate = 0.18

        vat_amount = amount * vat_rate
        total = amount + vat_amount

        return jsonify({
            "amount": amount,
            "vat_rate": "18%",
            "vat_amount": vat_amount,
            "total": total,
            "remaining": msg if isinstance(msg, int) else None
        })
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
        sdl_rate = 0.04

        sdl_amount = gross_payroll * sdl_rate

        return jsonify({
            "gross_payroll": gross_payroll,
            "sdl_rate": "4%",
            "sdl_amount": sdl_amount,
            "total_cost": gross_payroll + sdl_amount,
            "remaining": msg if isinstance(msg, int) else None
        })
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
        wcf_rate = 0.01

        wcf_amount = gross_payroll * wcf_rate

        return jsonify({
            "gross_payroll": gross_payroll,
            "wcf_rate": "1%",
            "wcf_amount": wcf_amount,
            "total_cost": gross_payroll + wcf_amount,
            "remaining": msg if isinstance(msg, int) else None
        })
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
        tax_rate = 0.30

        tax_amount = taxable_income * tax_rate
        net_income = taxable_income - tax_amount

        return jsonify({
            "taxable_income": taxable_income,
            "tax_rate": "30%",
            "tax_amount": tax_amount,
            "net_income": net_income,
            "remaining": msg if isinstance(msg, int) else None
        })
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

        rates = {
            "dividends": 0.10,
            "interest": 0.10,
            "royalties": 0.15,
            "rent": 0.10,
            "services": 0.05,
            "consulting": 0.15
        }

        rate = rates.get(payment_type, 0.10)
        withholding_amount = payment_amount * rate
        net_payment = payment_amount - withholding_amount

        return jsonify({
            "payment_amount": payment_amount,
            "payment_type": payment_type,
            "withholding_rate": f"{rate*100}%",
            "withholding_amount": withholding_amount,
            "net_payment": net_payment,
            "remaining": msg if isinstance(msg, int) else None
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# DOCUMENT APIs
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
                    content_text += page.extract_text() + "
"
            except Exception as e:
                content_text = f"Could not extract text: {str(e)}"
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            content_text = "[Image uploaded - visual analysis available via chat]"
        else:
            content_text = f"[Document uploaded: {filename}]"

        doc = Document(
            filename=filename, 
            content_text=content_text,
            user_id=current_user.id if current_user.is_authenticated else None
        )
        db.session.add(doc)
        db.session.commit()

        return jsonify({
            "message": "Document uploaded successfully",
            "document": doc.to_dict(),
            "content_preview": content_text[:500] if content_text else "",
            "remaining": msg if isinstance(msg, int) else None
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/documents/<int:doc_id>", methods=["GET"])
def get_document(doc_id):
    try:
        doc = Document.query.get_or_404(doc_id)
        if current_user.is_authenticated and doc.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403

        return jsonify({
            "id": doc.id,
            "filename": doc.filename,
            "content_text": doc.content_text,
            "uploaded_at": doc.uploaded_at.strftime('%Y-%m-%d %H:%M')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/documents/<int:doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    try:
        doc = Document.query.get_or_404(doc_id)
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

        doc = Document.query.get_or_404(doc_id)
        if current_user.is_authenticated and doc.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403

        chat_session = ChatSession(
            title=f"Doc: {doc.filename[:30]}", 
            tool="documents",
            user_id=current_user.id if current_user.is_authenticated else None
        )
        db.session.add(chat_session)
        db.session.commit()

        user_msg = ChatMessage(session_id=chat_session.id, role='user', content=f"[Document: {doc.filename}] {question}")
        db.session.add(user_msg)
        db.session.commit()

        doc_content = doc.content_text[:3000] if doc.content_text else "No text content available."

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": TOOL_PROMPTS["documents"]},
                {"role": "user", "content": f"Document content:
{doc_content}

Question: {question}"}
            ]
        )
        answer = response.choices[0].message.content

        ai_msg = ChatMessage(session_id=chat_session.id, role='ai', content=answer)
        db.session.add(ai_msg)
        db.session.commit()

        return jsonify({
            "answer": answer,
            "session_id": chat_session.id,
            "document_id": doc.id,
            "remaining": msg if isinstance(msg, int) else None
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# DATABASE INIT & MIGRATION
# ========================

def migrate_db():
    with app.app_context():
        try:
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()

            if 'user' in tables:
                columns = [c['name'] for c in inspector.get_columns('user')]
                if 'created_at' not in columns:
                    db.session.execute(db.text("ALTER TABLE user ADD COLUMN created_at DATETIME"))
                    db.session.commit()
                    print("Migration: Added created_at to user")
                if 'is_guest' not in columns:
                    db.session.execute(db.text("ALTER TABLE user ADD COLUMN is_guest BOOLEAN DEFAULT 0"))
                    db.session.commit()
                    print("Migration: Added is_guest to user")

            if 'chat_session' in tables:
                columns = [c['name'] for c in inspector.get_columns('chat_session')]
                if 'user_id' not in columns:
                    db.session.execute(db.text("ALTER TABLE chat_session ADD COLUMN user_id INTEGER"))
                    db.session.commit()
                    print("Migration: Added user_id to chat_session")

            if 'document' in tables:
                columns = [c['name'] for c in inspector.get_columns('document')]
                if 'user_id' not in columns:
                    db.session.execute(db.text("ALTER TABLE document ADD COLUMN user_id INTEGER"))
                    db.session.commit()
                    print("Migration: Added user_id to document")
                if 'content_text' not in columns:
                    db.session.execute(db.text("ALTER TABLE document ADD COLUMN content_text TEXT"))
                    db.session.commit()
                    print("Migration: Added content_text to document")
                if 'session_id' not in columns:
                    db.session.execute(db.text("ALTER TABLE document ADD COLUMN session_id INTEGER"))
                    db.session.commit()
                    print("Migration: Added session_id to document")

            db.create_all()
        except Exception as e:
            print(f"Migration warning: {e}")
            db.create_all()

migrate_db()

@app.route("/api/test")
def test():
    return jsonify({"status": "ok"})

# ========================
# VISITOR ANALYTICS APIs
# ========================

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
            "total_visitors": total_visitors,
            "total_visits": total_visits,
            "today_visitors": today_visitors,
            "today_unique": today_unique,
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
            "id": u.id,
            "email": u.email,
            "country": u.country,
            "role": u.role,
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
            return jsonify({"error": "Invalid role. Must be user, admin, or tax_professional"}), 400

        user = User.query.get_or_404(user_id)
        old_role = user.role
        user.role = new_role
        db.session.commit()

        log_audit("update_role", "user", user_id)

        return jsonify({
            "message": f"User role updated from {old_role} to {new_role}",
            "user_id": user.id,
            "email": user.email,
            "new_role": new_role
        })
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
                    content_text += page.extract_text() + "
"
            except Exception as e:
                content_text = "Could not extract text: " + str(e)
        else:
            content_text = file.read().decode("utf-8", errors="ignore")

        doc = TrainingDocument(
            title=title,
            filename=filename,
            content_text=content_text[:50000],
            doc_type=doc_type,
            source="admin_upload",
            jurisdiction=jurisdiction,
            uploaded_by=current_user.id
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)