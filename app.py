from flask import Flask, request, jsonify, send_file, session
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
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "taxgpt-secret-key-change-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///taxgpt.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

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
    activity_type = db.Column(db.String(20), nullable=False)  # 'chat', 'document', 'calculator'
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

CORS(app)

# OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# Tool-specific system prompts
TOOL_PROMPTS = {
    "tax_research": "You are a Tanzanian tax research assistant. Provide detailed explanations with references to the Income Tax Act, VAT Act, and other relevant laws.",
    "documents": "You are a tax document expert. Help users understand tax forms, notices, and draft formal letters, appeals, or tax documents in proper format.",
    "calculators": "You are a tax calculation expert. Provide step-by-step calculations for VAT, PAYE, SDL, WCF, corporate tax, and other Tanzanian taxes. Show your work clearly.",
    "deadlines": "You are a tax compliance expert. Provide specific filing deadlines, explain penalties for late filing, and guide users on how to request extensions or appeal penalties.",
    "business_setup": "You are a business registration advisor. Explain TIN registration, tax clearance, VAT registration, and ongoing compliance requirements for businesses in Tanzania."
}

# Guest limits
GUEST_CHAT_LIMIT = 5
GUEST_DOCUMENT_LIMIT = 2
GUEST_CALCULATOR_LIMIT = 10

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or 'unknown'

def check_guest_limit(activity_type, limit):
    if current_user.is_authenticated:
        return True, None

    ip = get_client_ip()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    count = GuestActivity.query.filter(
        GuestActivity.ip_address == ip,
        GuestActivity.activity_type == activity_type,
        GuestActivity.created_at >= today
    ).count()

    if count >= limit:
        return False, f"Guest limit reached. You have used {limit} {activity_type} actions today. Please sign up for unlimited access."

    # Record the activity
    activity = GuestActivity(ip_address=ip, activity_type=activity_type)
    db.session.add(activity)
    db.session.commit()

    remaining = limit - count - 1
    return True, remaining

# ========================
# AUTH ROUTES
# ========================

@app.route("/api/auth/me", methods=["GET"])
def get_current_user():
    if current_user.is_authenticated:
        return jsonify({
            "logged_in": True,
            "email": current_user.email,
            "is_guest": current_user.is_guest
        })
    return jsonify({"logged_in": False})

@app.route("/api/auth/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already registered"}), 400

        hashed_password = generate_password_hash(password)
        user = User(email=email, password=hashed_password, is_guest=False)
        db.session.add(user)
        db.session.commit()

        login_user(user)

        return jsonify({
            "message": "Account created successfully",
            "email": user.email
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

        login_user(user)

        return jsonify({
            "message": "Login successful",
            "email": user.email
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
            login_user(user)
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
.link{color:#d9ff00;text-decoration:none}
.error{color:#f87171;margin-top:10px}
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

        if not email or not password:
            return """<script>alert('All fields required');window.location.href='/signup';</script>"""

        if len(password) < 6:
            return """<script>alert('Password must be at least 6 characters');window.location.href='/signup';</script>"""

        if User.query.filter_by(email=email).first():
            return """<script>alert('Email already registered');window.location.href='/signup';</script>"""

        hashed_password = generate_password_hash(password)
        user = User(email=email, password=hashed_password, is_guest=False)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return """<script>window.location.href='/';</script>"""

    return """
<!DOCTYPE html>
<html>
<head>
<title>TaxGPT Sign Up</title>
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
<a href="/login" style="color:#d9ff00;text-decoration:none;font-weight:bold">Login</a>
</div>
<h1>TaxGPT Sign Up</h1>
<form method="POST">
<input name="email" placeholder="Email" type="email" required>
<input name="password" placeholder="Password" type="password" required>
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
            # For guests, don't show any sessions (fresh experience)
            sessions = []
        return jsonify([s.to_dict() for s in sessions])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sessions/<int:session_id>", methods=["GET"])
def get_session_messages(session_id):
    try:
        session = ChatSession.query.get_or_404(session_id)
        # Verify ownership
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

@app.route("/ask", methods=["POST"])
def ask():
    try:
        # Check guest limit
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

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ]
        )
        answer = response.choices[0].message.content

        ai_msg = ChatMessage(session_id=chat_session.id, role='ai', content=answer)
        db.session.add(ai_msg)
        db.session.commit()

        return jsonify({
            "answer": answer,
            "session_id": chat_session.id,
            "tool": tool,
            "remaining": msg if isinstance(msg, int) else None
        })

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
                    content_text += page.extract_text() + "\n"
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
                {"role": "user", "content": f"Document content:\n{doc_content}\n\nQuestion: {question}"}
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
# DATABASE INIT
# ========================

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)