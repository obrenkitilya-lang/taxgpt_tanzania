from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

# Load environment variables
load_dotenv()

# Flask app
app = Flask(__name__)
app.secret_key = "taxgpt-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///taxgpt.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
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

# Serve frontend pages
@app.route('/')
def home():
    return send_file('frontend/index_fixed.html')

@app.route('/<tool>')
def tool_page(tool):
    valid_tools = ['tax_research', 'documents', 'calculators', 'deadlines', 'business_setup']
    if tool in valid_tools:
        return send_file('frontend/index_fixed.html')
    return "Tool not found", 404

# API Routes
@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    try:
        sessions = ChatSession.query.order_by(ChatSession.created_at.desc()).all()
        return jsonify([s.to_dict() for s in sessions])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sessions/<int:session_id>", methods=["GET"])
def get_session_messages(session_id):
    try:
        messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
        return jsonify([m.to_dict() for m in messages])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sessions/<int:session_id>", methods=["DELETE"])
def delete_session(session_id):
    try:
        session = ChatSession.query.get_or_404(session_id)
        db.session.delete(session)
        db.session.commit()
        return jsonify({"message": "Session deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        question = data.get("question")
        session_id = data.get("session_id")
        tool = data.get("tool", "tax_research")

        if not question:
            return jsonify({"error": "No question provided"}), 400

        system_prompt = TOOL_PROMPTS.get(tool, TOOL_PROMPTS["tax_research"])

        if session_id:
            session = ChatSession.query.get(session_id)
            if not session:
                session = ChatSession(title=question[:50], tool=tool)
                db.session.add(session)
                db.session.commit()
        else:
            session = ChatSession(title=question[:50], tool=tool)
            db.session.add(session)
            db.session.commit()

        user_msg = ChatMessage(session_id=session.id, role='user', content=question)
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

        ai_msg = ChatMessage(session_id=session.id, role='ai', content=answer)
        db.session.add(ai_msg)
        db.session.commit()

        return jsonify({
            "answer": answer,
            "session_id": session.id,
            "tool": tool
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Calculator API - Hardcoded formulas
@app.route("/api/calculate/paye", methods=["POST"])
def calculate_paye():
    try:
        data = request.get_json()
        gross_salary = float(data.get("gross_salary", 0))
        
        # Tanzanian PAYE calculation (simplified)
        # NSSF: 10% of gross (employee contribution)
        nssf = gross_salary * 0.10
        
        # Taxable pay after NSSF
        taxable_pay = gross_salary - nssf
        
        # PAYE brackets (monthly)
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
        
        # WCF: 1% of gross (employer, not deducted from employee)
        wcf = gross_salary * 0.01
        
        net_pay = gross_salary - nssf - paye
        
        return jsonify({
            "gross_salary": gross_salary,
            "nssf": nssf,
            "paye": paye,
            "wcf": wcf,
            "net_pay": net_pay,
            "taxable_pay": taxable_pay
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/calculate/vat", methods=["POST"])
def calculate_vat():
    try:
        data = request.get_json()
        amount = float(data.get("amount", 0))
        vat_rate = 0.18  # 18% VAT in Tanzania
        
        vat_amount = amount * vat_rate
        total = amount + vat_amount
        
        return jsonify({
            "amount": amount,
            "vat_rate": "18%",
            "vat_amount": vat_amount,
            "total": total
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/login", methods=["GET", "POST"])
def login():
    return """
<!DOCTYPE html>
<html>
<head>
<title>TaxGPT Login</title>
<style>
body{
    background:#020817;
    display:flex;
    justify-content:center;
    align-items:center;
    height:100vh;
    font-family:Arial;
    color:white;
}
.card{
    background:#07123a;
    padding:40px;
    border-radius:20px;
    width:400px;
}
input{
    width:100%;
    padding:15px;
    margin-top:15px;
    background:#020817;
    border:1px solid #334155;
    color:white;
    border-radius:10px;
}
button{
    width:100%;
    padding:15px;
    margin-top:20px;
    background:#d9ff00;
    border:none;
    border-radius:10px;
    font-weight:bold;
}
</style>
</head>
<body>
<div class="card">
<div style="display:flex; justify-content:space-between; margin-bottom:20px;">
<a href="/" style="color:white; text-decoration:none; font-weight:bold;">← Home</a>
<a href="/signup" style="color:#d9ff00; text-decoration:none; font-weight:bold;">Sign Up</a>
</div>
<h1>TaxGPT Login</h1>
<input placeholder="Email">
<input placeholder="Password" type="password">
<button>Login</button>
</div>
</body>
</html>
"""

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)