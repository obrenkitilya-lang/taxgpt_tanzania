from flask import Flask, request, jsonify, send_file, Response, stream_with_context
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import PyPDF2
import json
from datetime import datetime, timedelta
import re
import urllib.request
import urllib.parse

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "taxgpt-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///taxgpt.db")
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
    is_premium = db.Column(db.Boolean, default=False)
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
        return {'id': self.id, 'title': self.title, 'filename': self.filename, 'doc_type': self.doc_type, 'source': self.source, 'jurisdiction': self.jurisdiction, 'verified': self.verified, 'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')}

class NewsUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    excerpt = db.Column(db.String(500), nullable=True)
    category = db.Column(db.String(50), default='general')
    source = db.Column(db.String(200), nullable=True)
    source_url = db.Column(db.String(500), nullable=True)
    is_pinned = db.Column(db.Boolean, default=False)
    is_admin_post = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    def to_dict(self):
        delta = datetime.now() - self.created_at if self.created_at else timedelta(days=999)
        days_ago = 'Today' if delta.days == 0 else ('1 day ago' if delta.days == 1 else str(delta.days) + ' days ago')
        return {'id': self.id, 'title': self.title, 'content': self.content, 'excerpt': self.excerpt or self.content[:200] + '...', 'category': self.category, 'source': self.source, 'source_url': self.source_url, 'is_pinned': self.is_pinned, 'is_admin_post': self.is_admin_post, 'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None, 'days_ago': days_ago}

class TaxComparisonData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tax_type = db.Column(db.String(50), nullable=False)
    country = db.Column(db.String(50), nullable=False)
    metric = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(500), nullable=False)
    details = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    def to_dict(self):
        return {'id': self.id, 'tax_type': self.tax_type, 'country': self.country, 'metric': self.metric, 'value': self.value, 'details': self.details}

class TaxDeadline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=False)
    recurrence = db.Column(db.String(50), default='monthly')
    country = db.Column(db.String(50), default='Tanzania')
    penalty_note = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    def to_dict(self):
        days_until = (self.due_date - datetime.now()).days
        status = 'urgent' if days_until <= 7 else 'upcoming' if days_until <= 30 else 'normal'
        return {'id': self.id, 'name': self.name, 'description': self.description, 'due_date': self.due_date.strftime('%Y-%m-%d'), 'due_date_formatted': self.due_date.strftime('%B %d, %Y'), 'recurrence': self.recurrence, 'country': self.country, 'penalty_note': self.penalty_note, 'days_until': days_until, 'status': status, 'is_active': self.is_active}

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    def to_dict(self):
        return {'id': self.id, 'action': self.action, 'entity_type': self.entity_type, 'entity_id': self.entity_id, 'details': self.details, 'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None}

class BusinessLead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    business_type = db.Column(db.String(100), nullable=False)
    business_description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='new')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'email': self.email, 'phone': self.phone, 'country': self.country, 'business_type': self.business_type, 'business_description': self.business_description, 'status': self.status, 'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None}

CORS(app, supports_credentials=True)

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

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

_ANTI_HALLUCINATION = """
You are TaxGPT, a helpful AI tax assistant for East Africa.
- Answer tax, finance, and business questions for Tanzania, Kenya, and Uganda.
- For calculations show step-by-step workings. Tanzania rates: VAT 18%, SDL 4%, WCF 0.5%, Corporate tax 30%. PAYE: deduct NSSF first (10% gross, max 100,000 TZS), then apply monthly bands 0%%/8%%/20%%/25%%/30%%.
- Cite laws confidently. Only say verify with TRA for genuinely uncertain specific figures.
- If web search results provided, use them and cite source URL.
- After each answer suggest ONE sidebar tool: Calculator (tax math), Deadlines (filing dates), Documents (TRA notices), Business Setup (registration), Tax Updates (news).
- End with: Verify current figures with TRA (tra.go.tz).
"""

TOOL_PROMPTS = {
    "tax_research": (
        "You are TaxGPT, an AI tax assistant specialising in East African tax law - primarily Tanzania, Kenya, and Uganda. "
        "You have knowledge of: Income Tax Act Cap 332, VAT Act Cap 148, Tax Administration Act 2015, Excise Act, "
        "Stamp Duty Act, SDL Act, WCF Act, and TRA procedures. "
        "Provide clear, accurate answers with references to specific laws and sections where confident they exist. "
        + _ANTI_HALLUCINATION
    ),
    "documents": (
        "You are TaxGPT, an AI assistant specialising in Tanzanian TRA tax documents and notices. "
        "Help users understand what a document means, what action is required, and what their rights are. "
        "Common documents include: demand notices, tax examination reports, audit findings, VAT verification letters, "
        "tax investigation notices, and TRA correspondence. Explain in plain language and identify key deadlines. "
        + _ANTI_HALLUCINATION
    ),
    "calculators": (
        "You are TaxGPT, a tax calculation assistant for Tanzania, Kenya, and Uganda. "
        "Help verify calculations for: PAYE (Tanzania graduated bands), VAT (18% standard), "
        "SDL (4% of gross payroll), WCF (0.5% of gross payroll), Corporate Income Tax (30%), "
        "and Withholding Tax. Always show workings step by step. "
        + _ANTI_HALLUCINATION
    ),
    "deadlines": (
        "You are TaxGPT, a tax compliance assistant for Tanzania. "
        "Provide accurate information on TRA filing deadlines: monthly VAT returns (last working day of following month), "
        "PAYE (7th of following month), SDL/WCF (7th of following month), annual CIT returns (6 months after year end), "
        "provisional tax (3 equal instalments). Explain late filing penalties clearly. "
        + _ANTI_HALLUCINATION
    ),
    "business_setup": (
        "You are TaxGPT, a business registration and tax compliance advisor for Tanzania. "
        "Guide users through: BRELA registration, TIN application, VAT registration (threshold TZS 100M/year), "
        "business licences, sector-specific permits, and ongoing compliance. "
        "Be clear about mandatory vs optional steps, and typical timelines and costs where known. "
        + _ANTI_HALLUCINATION
    ),
    "tax_updates": (
        "You are TaxGPT, a tax news assistant for East Africa. "
        "Provide information on TRA announcements, Finance Act amendments, budget changes for Tanzania, Kenya, Uganda. "
        "Be clear about what year information relates to and flag if unsure whether information is current. "
        + _ANTI_HALLUCINATION
    ),
}

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
        visitor = VisitorLog(ip_address=ip, user_agent=user_agent, page_visited=page or request.path, is_logged_in=current_user.is_authenticated, user_id=current_user.id if current_user.is_authenticated else None, country=current_user.country if current_user.is_authenticated else None)
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
        count = GuestActivity.query.filter(GuestActivity.ip_address == ip, GuestActivity.activity_type == activity_type, GuestActivity.created_at >= today).count()
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


def web_search(query, max_results=4):
    """Search the web using Tavily API for live tax information."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return ""
    try:
        import json as _json
        data = _json.dumps({
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_domains": [],
            "exclude_domains": []
        }).encode('utf-8')
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            result = _json.loads(resp.read().decode('utf-8'))
        results = result.get("results", [])
        if not results:
            return ""
        parts = []
        for r in results[:max_results]:
            title = r.get("title", "")
            url = r.get("url", "")
            content_snippet = r.get("content", "")[:600]
            parts.append(f"SOURCE: {title}\nURL: {url}\nCONTENT: {content_snippet}\n")
        return "\n---\n".join(parts)
    except Exception as e:
        print("Web search error:", str(e))
        return ""

LIVE_SEARCH_TRIGGERS = [
    "current", "latest", "today", "now", "recent", "2024", "2025", "2026",
    "who is", "who are", "commissioner", "minister", "director", "ceo", "chairman",
    "new law", "new regulation", "amendment", "budget", "announced", "just",
    "this year", "this month", "last month", "breaking", "update",
    "procedure", "procedures", "how to", "how do", "steps to", "process",
    "appeal", "trab", "trat", "objection", "dispute", "deadline", "penalty",
    "form", "requirement", "requirements", "register", "registration",
    "what is the", "what are the", "when is", "when are", "how much",
    "appeal", "trab", "trat", "objection", "procedure", "procedures",
    "how to", "steps", "form ", "trb", "deadline", "penalty", "requirement"
]

def needs_web_search(question):
    q = question.lower()
    return any(trigger in q for trigger in LIVE_SEARCH_TRIGGERS)

def search_training_docs(query, jurisdiction="Tanzania", max_results=3):
    try:
        docs = TrainingDocument.query.filter(TrainingDocument.jurisdiction == jurisdiction).all()
        if not docs:
            return ""
        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))
        tax_keywords = {
            'tax': ['tax', 'taxation', 'revenue', 'tra'],
            'vat': ['vat', 'value added tax', 'vat act', 'vat registration'],
            'income': ['income', 'income tax', 'paye', 'taxable income'],
            'appeal': ['appeal', 'appeals', 'tribunal', 'dispute', 'objection'],
            'business': ['business', 'company', 'corporation', 'enterprise', 'tin'],
            'certificate': ['certificate', 'clearance', 'tcc', 'compliance'],
            'withholding': ['withholding', 'wht', 'deduction', 'deducted'],
            'customs': ['customs', 'import', 'export', 'duty', 'tariff'],
            'stamp': ['stamp', 'stamp duty', 'transfer', 'conveyance'],
            'tourism': ['tourism', 'tourist', 'hotel', 'travel'],
            'training': ['training', 'vocational', 'education', 'skill'],
            'amendment': ['amendment', 'amended', 'change', 'update', 'revision'],
            'reserve': ['reserve', 'certificate', 'tax reserve'],
        }
        expanded_words = set(query_words)
        for key, related in tax_keywords.items():
            if any(word in query_lower for word in related):
                expanded_words.update(related)
        scored_docs = []
        for doc in docs:
            if not doc.content_text or len(doc.content_text) < 50:
                continue
            doc_title_lower = doc.title.lower()
            doc_content_lower = doc.content_text[:8000].lower()
            title_score = 0
            content_score = 0
            for word in expanded_words:
                if len(word) > 2:
                    title_score += doc_title_lower.count(word) * 5
                    content_score += doc_content_lower.count(word) * 1
            if query_lower in doc_title_lower:
                title_score += 50
            doc_type_lower = doc.doc_type.lower()
            if any(word in doc_type_lower for word in expanded_words):
                title_score += 20
            total_score = title_score + content_score
            if total_score > 0:
                scored_docs.append((total_score, doc))
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        top_docs = scored_docs[:max_results]
        if not top_docs:
            fallback_docs = [d for d in docs if d.content_text and len(d.content_text) > 50][:2]
            if fallback_docs:
                top_docs = [(1, d) for d in fallback_docs]
            else:
                return ""
        context_parts = []
        for score, doc in top_docs:
            content_preview = doc.content_text[:3000]
            context_parts.append("--- DOCUMENT: " + doc.title + " (" + doc.doc_type + ") ---\n" + content_preview + "\n")
        return "\n".join(context_parts)
    except Exception as e:
        print("RAG search error: " + str(e))
        return ""

def build_rag_prompt(question, tool="tax_research", jurisdiction="Tanzania"):
    doc_context = search_training_docs(question, jurisdiction)
    web_context = ""
    if needs_web_search(question):
        web_context = web_search(question + " Tanzania tax " + jurisdiction)
    base_prompt = TOOL_PROMPTS.get(tool, TOOL_PROMPTS["tax_research"])
    extra = ""
    if doc_context:
        extra += "\n\nOFFICIAL UPLOADED DOCUMENTS (use as primary source):\n" + doc_context
    if web_context:
        extra += "\n\nLIVE WEB SEARCH RESULTS (current information from the web):\n" + web_context + "\nWhen using web results, cite the source URL."
    if extra:
        return base_prompt + extra + "\n\nUser question: " + question
    else:
        return base_prompt + "\n\nUser question: " + question

def log_audit(action, entity_type=None, entity_id=None, details=None):
    try:
        user_id = current_user.id if current_user.is_authenticated else None
        log = AuditLog(user_id=user_id, action=action, entity_type=entity_type, entity_id=entity_id, details=details)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print("Audit log error: " + str(e))

# ========================
# SEED DATA FUNCTIONS
# ========================

def seed_comparison_data():
    if TaxComparisonData.query.first():
        return
    data = [
        {'tax_type': 'vat', 'country': 'Tanzania', 'metric': 'Standard Rate', 'value': '18%', 'details': 'Applied to most goods and services'},
        {'tax_type': 'vat', 'country': 'Kenya', 'metric': 'Standard Rate', 'value': '16%', 'details': 'Reduced from 18% in 2020, restored to 16% in 2023'},
        {'tax_type': 'vat', 'country': 'Uganda', 'metric': 'Standard Rate', 'value': '18%', 'details': 'Standard rate since 2015'},
        {'tax_type': 'vat', 'country': 'Tanzania', 'metric': 'Registration Threshold', 'value': 'TZS 100M annually', 'details': 'Mandatory registration if turnover exceeds threshold'},
        {'tax_type': 'vat', 'country': 'Kenya', 'metric': 'Registration Threshold', 'value': 'KES 5M annually', 'details': 'Approx. USD 37,000'},
        {'tax_type': 'vat', 'country': 'Uganda', 'metric': 'Registration Threshold', 'value': 'UGX 150M annually', 'details': 'Approx. USD 40,000'},
        {'tax_type': 'vat', 'country': 'Tanzania', 'metric': 'Filing Frequency', 'value': 'Monthly (20th)', 'details': 'Due by 20th of following month'},
        {'tax_type': 'vat', 'country': 'Kenya', 'metric': 'Filing Frequency', 'value': 'Monthly (20th)', 'details': 'iTax portal filing'},
        {'tax_type': 'vat', 'country': 'Uganda', 'metric': 'Filing Frequency', 'value': 'Monthly (15th)', 'details': 'URF portal filing'},
        {'tax_type': 'vat', 'country': 'Tanzania', 'metric': 'Zero-Rated Items', 'value': 'Exports, meds, education', 'details': 'Includes agricultural inputs, medical supplies'},
        {'tax_type': 'vat', 'country': 'Kenya', 'metric': 'Zero-Rated Items', 'value': 'Exports, meds, education', 'details': 'Includes agricultural inputs'},
        {'tax_type': 'vat', 'country': 'Uganda', 'metric': 'Zero-Rated Items', 'value': 'Exports, meds, education', 'details': 'Includes agricultural inputs, medical supplies'},
        {'tax_type': 'vat', 'country': 'Tanzania', 'metric': 'Exempt Items', 'value': 'Financial services', 'details': 'Also includes residential rent, insurance'},
        {'tax_type': 'vat', 'country': 'Kenya', 'metric': 'Exempt Items', 'value': 'Financial services', 'details': 'Also includes residential rent'},
        {'tax_type': 'vat', 'country': 'Uganda', 'metric': 'Exempt Items', 'value': 'Financial services', 'details': 'Also includes residential rent, insurance'},
        {'tax_type': 'vat', 'country': 'Tanzania', 'metric': 'Late Filing Penalty', 'value': '1% per month', 'details': 'Plus interest on unpaid tax'},
        {'tax_type': 'vat', 'country': 'Kenya', 'metric': 'Late Filing Penalty', 'value': '2% per month', 'details': 'Plus interest on unpaid tax'},
        {'tax_type': 'vat', 'country': 'Uganda', 'metric': 'Late Filing Penalty', 'value': '2% per month', 'details': 'Plus interest on unpaid tax'},
        {'tax_type': 'vat', 'country': 'Tanzania', 'metric': 'Late Payment Penalty', 'value': '20% of tax due', 'details': 'Plus 1% monthly interest'},
        {'tax_type': 'vat', 'country': 'Kenya', 'metric': 'Late Payment Penalty', 'value': '20% of tax due', 'details': 'Plus 1% monthly interest'},
        {'tax_type': 'vat', 'country': 'Uganda', 'metric': 'Late Payment Penalty', 'value': '20% of tax due', 'details': 'Plus 1% monthly interest'},
        {'tax_type': 'paye', 'country': 'Tanzania', 'metric': 'Top Rate', 'value': '30%', 'details': 'For income above TZS 1,000,000/month'},
        {'tax_type': 'paye', 'country': 'Kenya', 'metric': 'Top Rate', 'value': '30%', 'details': 'For income above KES 800,000/month'},
        {'tax_type': 'paye', 'country': 'Uganda', 'metric': 'Top Rate', 'value': '40%', 'details': 'For income above UGX 10,000,000/month'},
        {'tax_type': 'paye', 'country': 'Tanzania', 'metric': 'Monthly Threshold', 'value': 'TZS 270,000', 'details': 'No tax on first TZS 270,000'},
        {'tax_type': 'paye', 'country': 'Kenya', 'metric': 'Monthly Threshold', 'value': 'KES 24,000', 'details': 'No tax on first KES 24,000 (2026/2027)'},
        {'tax_type': 'paye', 'country': 'Uganda', 'metric': 'Monthly Threshold', 'value': 'UGX 235,000', 'details': 'No tax on first UGX 235,000'},
        {'tax_type': 'corporate', 'country': 'Tanzania', 'metric': 'Standard Rate', 'value': '30%', 'details': 'For resident companies'},
        {'tax_type': 'corporate', 'country': 'Kenya', 'metric': 'Standard Rate', 'value': '30%', 'details': 'For resident companies'},
        {'tax_type': 'corporate', 'country': 'Uganda', 'metric': 'Standard Rate', 'value': '30%', 'details': 'For resident companies'},
        {'tax_type': 'corporate', 'country': 'Tanzania', 'metric': 'Small Business Rate', 'value': '25%', 'details': 'For companies with turnover < TZS 100M'},
        {'tax_type': 'corporate', 'country': 'Kenya', 'metric': 'Turnover Tax', 'value': '3%', 'details': 'For businesses with turnover KES 1M-25M'},
        {'tax_type': 'corporate', 'country': 'Uganda', 'metric': 'Small Business Rate', 'value': '25%', 'details': 'For companies with turnover < UGX 150M'},
        {'tax_type': 'withholding', 'country': 'Tanzania', 'metric': 'Dividends', 'value': '10%', 'details': 'Final tax for resident shareholders'},
        {'tax_type': 'withholding', 'country': 'Kenya', 'metric': 'Dividends', 'value': '5%', 'details': 'Final tax for resident shareholders'},
        {'tax_type': 'withholding', 'country': 'Uganda', 'metric': 'Dividends', 'value': '15%', 'details': 'Final tax for resident shareholders'},
        {'tax_type': 'withholding', 'country': 'Tanzania', 'metric': 'Interest', 'value': '10%', 'details': 'On interest payments to residents'},
        {'tax_type': 'withholding', 'country': 'Kenya', 'metric': 'Interest', 'value': '15%', 'details': 'On interest payments to residents'},
        {'tax_type': 'withholding', 'country': 'Uganda', 'metric': 'Interest', 'value': '15%', 'details': 'On interest payments to residents'},
        {'tax_type': 'withholding', 'country': 'Tanzania', 'metric': 'Royalties', 'value': '15%', 'details': 'On royalty payments'},
        {'tax_type': 'withholding', 'country': 'Kenya', 'metric': 'Royalties', 'value': '5%', 'details': 'On royalty payments'},
        {'tax_type': 'withholding', 'country': 'Uganda', 'metric': 'Royalties', 'value': '15%', 'details': 'On royalty payments'},
    ]
    for item in data:
        db.session.add(TaxComparisonData(**item))
    db.session.commit()
    print("Seeded tax comparison data")

def seed_deadlines():
    if TaxDeadline.query.first():
        return
    now = datetime.now()
    next_month_20 = (now.replace(day=1) + timedelta(days=32)).replace(day=20)
    if next_month_20 < now:
        next_month_20 = (next_month_20.replace(day=1) + timedelta(days=32)).replace(day=20)
    next_month_7 = (now.replace(day=1) + timedelta(days=32)).replace(day=7)
    if next_month_7 < now:
        next_month_7 = (next_month_7.replace(day=1) + timedelta(days=32)).replace(day=7)
    annual_date = now.replace(month=6, day=30)
    if annual_date < now:
        annual_date = annual_date.replace(year=annual_date.year + 1)
    q_dates = []
    for month in [3, 6, 9, 12]:
        q_date = now.replace(month=month, day=31 if month in [3, 12] else 30)
        if q_date < now:
            q_date = q_date.replace(year=q_date.year + 1)
        q_dates.append(q_date)
    deadlines = [
        {'name': 'Monthly VAT Return', 'description': 'Monthly VAT returns for all registered taxpayers must be filed by the 20th of the following month.', 'due_date': next_month_20, 'recurrence': 'monthly', 'country': 'Tanzania', 'penalty_note': '1% per month penalty + interest on unpaid tax'},
        {'name': 'Monthly PAYE Return', 'description': 'Employers must submit PAYE returns and remit withheld taxes to TRA by the 7th of each month.', 'due_date': next_month_7, 'recurrence': 'monthly', 'country': 'Tanzania', 'penalty_note': 'Late filing penalty applies'},
        {'name': 'Annual Income Tax Return', 'description': 'Final annual tax returns for the financial year. Includes audited financial statements for companies.', 'due_date': annual_date, 'recurrence': 'annual', 'country': 'Tanzania', 'penalty_note': '20% penalty on tax due + interest'},
        {'name': 'Provisional Tax Payment (Q1)', 'description': 'Quarterly installment payment for corporate taxpayers. Based on estimated annual tax liability.', 'due_date': q_dates[0], 'recurrence': 'quarterly', 'country': 'Tanzania', 'penalty_note': 'Interest on late payment'},
        {'name': 'Provisional Tax Payment (Q2)', 'description': 'Quarterly installment payment for corporate taxpayers. Based on estimated annual tax liability.', 'due_date': q_dates[1], 'recurrence': 'quarterly', 'country': 'Tanzania', 'penalty_note': 'Interest on late payment'},
        {'name': 'Provisional Tax Payment (Q3)', 'description': 'Quarterly installment payment for corporate taxpayers. Based on estimated annual tax liability.', 'due_date': q_dates[2], 'recurrence': 'quarterly', 'country': 'Tanzania', 'penalty_note': 'Interest on late payment'},
        {'name': 'Provisional Tax Payment (Q4)', 'description': 'Quarterly installment payment for corporate taxpayers. Based on estimated annual tax liability.', 'due_date': q_dates[3], 'recurrence': 'quarterly', 'country': 'Tanzania', 'penalty_note': 'Interest on late payment'},
        {'name': 'Monthly SDL Return', 'description': 'Skills and Development Levy returns must be filed by the 7th of each month.', 'due_date': next_month_7, 'recurrence': 'monthly', 'country': 'Tanzania', 'penalty_note': 'Late filing penalty applies'},
    ]
    for d in deadlines:
        db.session.add(TaxDeadline(**d))
    db.session.commit()
    print("Seeded tax deadlines")

def seed_sample_news():
    if NewsUpdate.query.first():
        return
    news = [
        {'title': 'TRA Announces New E-Filing System for VAT Returns', 'content': 'Starting July 1, 2026, all VAT-registered taxpayers must file returns through the new TRA Online Portal. Key changes include auto-calculation features, mobile payment integration (M-Pesa, Tigo Pesa), and a new penalty structure for late filing. The new system aims to reduce manual errors and improve compliance tracking.', 'excerpt': 'Starting July 1, 2026, all VAT-registered taxpayers must file returns through the new TRA Online Portal.', 'category': 'tz', 'source': 'Tanzania Revenue Authority', 'source_url': 'https://tra.go.tz', 'is_pinned': True, 'is_admin_post': False},
        {'title': 'Finance Act 2026: Key Changes for Businesses', 'content': 'New tax brackets effective July 1, 2026. Digital services tax introduced at 2%. Corporate tax rate remains 30% but new incentives for manufacturing sector. Updated PAYE thresholds for monthly income. The Act also introduces tax relief for startups in the technology sector.', 'excerpt': 'New tax brackets effective July 1, 2026. Digital services tax introduced at 2%.', 'category': 'tz', 'source': 'Ministry of Finance Tanzania', 'source_url': 'https://mof.go.tz', 'is_pinned': False, 'is_admin_post': True},
        {'title': 'EAC Harmonizes VAT Rules Across Member States', 'content': 'Member states agree on unified VAT treatment for cross-border digital services. New guidelines for e-commerce transactions. Simplified registration process for businesses operating in multiple EAC countries. This harmonization aims to reduce compliance burden for cross-border businesses.', 'excerpt': 'Member states agree on unified VAT treatment for cross-border digital services.', 'category': 'eac', 'source': 'East African Community', 'source_url': 'https://eac.int', 'is_pinned': False, 'is_admin_post': False},
        {'title': 'Kenya Updates PAYE Thresholds for 2026/2027', 'content': 'Monthly PAYE threshold raised to KES 24,000. New tax bands announced. Digital marketplace withholding tax at 5%. Changes effective from July 1, 2026. The Kenya Revenue Authority (KRA) has also introduced new filing requirements for digital service providers.', 'excerpt': 'Monthly PAYE threshold raised to KES 24,000. New tax bands announced.', 'category': 'ke', 'source': 'Kenya Revenue Authority', 'source_url': 'https://kra.go.ke', 'is_pinned': False, 'is_admin_post': False},
        {'title': 'Uganda Introduces Electronic Fiscal Receipting', 'content': 'All VAT-registered taxpayers must use EFRIS (Electronic Fiscal Receipting and Invoicing System) by September 2026. Penalties for non-compliance announced. Training sessions available nationwide. The Uganda Revenue Authority (URA) is providing free EFRIS devices to small businesses.', 'excerpt': 'All VAT-registered taxpayers must use EFRIS by September 2026.', 'category': 'ug', 'source': 'Uganda Revenue Authority', 'source_url': 'https://ura.go.ug', 'is_pinned': False, 'is_admin_post': False},
    ]
    for n in news:
        db.session.add(NewsUpdate(**n))
    db.session.commit()
    print("Seeded sample news updates")

# ========================
# AUTH ROUTES
# ========================

@app.route("/api/auth/me", methods=["GET"])
def get_current_user():
    if current_user.is_authenticated:
        return jsonify({"logged_in": True, "email": current_user.email, "country": current_user.country, "role": current_user.role, "is_guest": current_user.is_guest, "is_premium": getattr(current_user, "is_premium", False)})
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
        return jsonify({"message": "Account created successfully", "email": user.email, "country": user.country, "role": user.role})
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
        return jsonify({"message": "Login successful", "email": user.email, "country": user.country, "role": user.role})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/auth/logout", methods=["POST"])
@login_required
def api_logout():
    logout_user()
    return jsonify({"message": "Logged out successfully"})

@app.route("/api/account/change-password", methods=["POST"])
@login_required
def change_password():
    try:
        data = request.get_json()
        current_password = data.get("current_password", "")
        new_password = data.get("new_password", "")
        if not current_password or not new_password:
            return jsonify({"error": "Both current and new password are required"}), 400
        if len(new_password) < 6:
            return jsonify({"error": "New password must be at least 6 characters"}), 400
        if not check_password_hash(current_user.password, current_password):
            return jsonify({"error": "Current password is incorrect"}), 401
        current_user.password = generate_password_hash(new_password)
        db.session.commit()
        return jsonify({"message": "Password changed successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/account/change-country", methods=["POST"])
@login_required
def change_country():
    try:
        data = request.get_json()
        country = data.get("country", "").strip()
        if country not in ["Tanzania", "Kenya", "Uganda"]:
            return jsonify({"error": "Country must be Tanzania, Kenya, or Uganda"}), 400
        current_user.country = country
        db.session.commit()
        return jsonify({"message": "Country updated successfully", "country": country})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/account/delete", methods=["DELETE"])
@login_required
def delete_account():
    try:
        data = request.get_json() or {}
        password = data.get("password", "")
        if not check_password_hash(current_user.password, password):
            return jsonify({"error": "Incorrect password"}), 401
        user_id = current_user.id
        logout_user()
        user = User.query.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()
        return jsonify({"message": "Account deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/')
def home():
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'index_fixed.html'))

@app.route('/admin')
def admin_page():
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'index_fixed.html'))

@app.route('/<tool>')
def tool_page(tool):
    valid_tools = ['tax_updates', 'documents', 'calculators', 'deadlines', 'business_setup', 'tax_research', 'account']
    if tool in valid_tools:
        return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'index_fixed.html'))
    return "Tool not found", 404

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            return "<script>window.location.href='/';</script>"
        return "<script>alert('Invalid credentials');window.location.href='/login';</script>"
    return "<!DOCTYPE html><html><head><title>TaxGPT Login</title><style>body{background:#020817;display:flex;justify-content:center;align-items:center;height:100vh;font-family:Inter,sans-serif;color:white;margin:0}.card{background:#07123a;padding:40px;border-radius:20px;width:400px}input{width:100%;padding:15px;margin-top:15px;background:#020817;border:1px solid #334155;color:white;border-radius:10px;box-sizing:border-box}button{width:100%;padding:15px;margin-top:20px;background:#d9ff00;border:none;border-radius:10px;font-weight:bold;cursor:pointer;font-size:16px}button:hover{background:#c8e600}</style></head><body><div class=\"card\"><div style=\"display:flex;justify-content:space-between;margin-bottom:20px\"><a href=\"/\" style=\"color:white;text-decoration:none;font-weight:bold\">← Home</a><a href=\"/signup\" style=\"color:#d9ff00;text-decoration:none;font-weight:bold\">Sign Up</a></div><h1>TaxGPT Login</h1><form method=\"POST\"><input name=\"email\" placeholder=\"Email\" type=\"email\" required><input name=\"password\" placeholder=\"Password\" type=\"password\" required><button type=\"submit\">Login</button></form></div></body></html>"

@app.route("/signup", methods=["GET", "POST"])
def signup_page():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        country = request.form.get("country", "Tanzania").strip()
        if not email or not password:
            return "<script>alert('All fields required');window.location.href='/signup';</script>"
        if len(password) < 6:
            return "<script>alert('Password must be at least 6 characters');window.location.href='/signup';</script>"
        if User.query.filter_by(email=email).first():
            return "<script>alert('Email already registered');window.location.href='/signup';</script>"
        if country not in ['Tanzania', 'Kenya', 'Uganda']:
            return "<script>alert('Country must be Tanzania, Kenya, or Uganda');window.location.href='/signup';</script>"
        hashed_password = generate_password_hash(password)
        user = User(email=email, password=hashed_password, country=country, role='user', is_guest=False)
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        return "<script>window.location.href='/';</script>"
    return "<!DOCTYPE html><html><head><title>TaxGPT Sign Up</title><style>body{background:#020817;display:flex;justify-content:center;align-items:center;height:100vh;font-family:Inter,sans-serif;color:white;margin:0}.card{background:#07123a;padding:40px;border-radius:20px;width:400px}input,select{width:100%;padding:15px;margin-top:15px;background:#020817;border:1px solid #334155;color:white;border-radius:10px;box-sizing:border-box}select{color:white;background:#020817}option{background:#07123a;color:white}button{width:100%;padding:15px;margin-top:20px;background:#d9ff00;border:none;border-radius:10px;font-weight:bold;cursor:pointer;font-size:16px}button:hover{background:#c8e600}</style></head><body><div class=\"card\"><div style=\"display:flex;justify-content:space-between;margin-bottom:20px\"><a href=\"/\" style=\"color:white;text-decoration:none;font-weight:bold\">← Home</a><a href=\"/login\" style=\"color:#d9ff00;text-decoration:none;font-weight:bold\">Login</a></div><h1>TaxGPT Sign Up</h1><form method=\"POST\"><input name=\"email\" placeholder=\"Email\" type=\"email\" required><input name=\"password\" placeholder=\"Password\" type=\"password\" required><select name=\"country\" required><option value=\"Tanzania\">Tanzania</option><option value=\"Kenya\">Kenya</option><option value=\"Uganda\">Uganda</option></select><button type=\"submit\">Create Account</button></form></div></body></html>"

# ========================
# API ROUTES - SESSIONS & CHAT
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
        jurisdiction = current_user.country if current_user.is_authenticated else "Tanzania"
        system_prompt = build_rag_prompt(question, tool, jurisdiction)
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

        def generate():
            full_response = ""
            yield "data: " + json.dumps({'type': 'session', 'session_id': chat_session.id}) + "\n\n"
            stream = client.chat.completions.create(
                model="gpt-4o", 
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
                    yield "data: " + json.dumps({'type': 'token', 'content': text}) + "\n\n"
            ai_msg = ChatMessage(session_id=chat_session.id, role='ai', content=full_response)
            db.session.add(ai_msg)
            db.session.commit()
            yield "data: " + json.dumps({'type': 'done', 'remaining': msg if isinstance(msg, int) else None}) + "\n\n"

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
        return jsonify({"payment_amount": payment_amount, "payment_type": payment_type, "withholding_rate": str(rate * 100) + "%", "withholding_amount": withholding_amount, "net_payment": net_payment, "remaining": msg if isinstance(msg, int) else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/calculate/gross_from_net", methods=["POST"])
def calculate_gross_from_net():
    try:
        data = request.get_json()
        net_pay = float(data.get("net_pay", 0))
        lo, hi = net_pay, net_pay * 3
        for _ in range(60):
            mid = (lo + hi) / 2
            nssf = min(mid * 0.10, 100000)
            taxable = mid - nssf
            if taxable <= 270000: paye = 0
            elif taxable <= 520000: paye = (taxable - 270000) * 0.08
            elif taxable <= 760000: paye = 20000 + (taxable - 520000) * 0.20
            elif taxable <= 1000000: paye = 68000 + (taxable - 760000) * 0.25
            else: paye = 128000 + (taxable - 1000000) * 0.30
            computed_net = mid - nssf - paye
            if abs(computed_net - net_pay) < 0.01: break
            if computed_net < net_pay: lo = mid
            else: hi = mid
        gross_salary = round(mid, 2)
        nssf = round(min(gross_salary * 0.10, 100000), 2)
        taxable = gross_salary - nssf
        if taxable <= 270000: paye = 0
        elif taxable <= 520000: paye = (taxable - 270000) * 0.08
        elif taxable <= 760000: paye = 20000 + (taxable - 520000) * 0.20
        elif taxable <= 1000000: paye = 68000 + (taxable - 760000) * 0.25
        else: paye = 128000 + (taxable - 1000000) * 0.30
        return jsonify({"net_pay": net_pay, "gross_salary": round(gross_salary), "nssf": round(nssf), "paye": round(paye)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/calculate/vat_inclusive", methods=["POST"])
def calculate_vat_inclusive():
    try:
        data = request.get_json()
        inclusive_amount = float(data.get("amount", 0))
        vat_amount = inclusive_amount * 18 / 118
        exclusive_amount = inclusive_amount - vat_amount
        return jsonify({"inclusive_amount": round(inclusive_amount, 2), "vat_amount": round(vat_amount, 2), "exclusive_amount": round(exclusive_amount, 2)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/calculate/import_duty", methods=["POST"])
def calculate_import_duty():
    try:
        data = request.get_json()
        cif_value = float(data.get("cif_value", 0))
        category = data.get("category", "vehicles")
        origin = data.get("origin", "outside")
        rates = {"vehicles":0.25,"electronics":0.25,"clothing":0.25,"food":0.25,"building":0.10,"machinery":0,"medicine":0,"fuel":0.10,"furniture":0.25,"agriculture":0,"used_clothes":0.35,"gems":0.10}
        duty_rate = 0 if origin == "eac" else rates.get(category, 0.25)
        import_duty = cif_value * duty_rate
        dutiable_value = cif_value + import_duty
        vat_amount = dutiable_value * 0.18
        rdl_amount = cif_value * 0.015
        total_landed_cost = cif_value + import_duty + vat_amount + rdl_amount
        return jsonify({"cif_value": round(cif_value), "category": category, "origin": origin, "duty_rate": str(int(duty_rate*100)) + "%", "import_duty": round(import_duty), "vat_amount": round(vat_amount), "rdl_amount": round(rdl_amount), "total_landed_cost": round(total_landed_cost)})
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
                content_text = "Could not extract text: " + str(e)
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            content_text = "[Image uploaded - visual analysis available via chat]"
        else:
            content_text = "[Document uploaded: " + filename + "]"
        doc = Document(filename=filename, content_text=content_text, user_id=current_user.id if current_user.is_authenticated else None)
        db.session.add(doc)
        db.session.commit()
        return jsonify({"message": "Document uploaded successfully", "document": doc.to_dict(), "content_preview": content_text[:500] if content_text else "", "remaining": msg if isinstance(msg, int) else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/documents/<int:doc_id>", methods=["GET"])
def get_document(doc_id):
    try:
        doc = Document.query.get_or_404(doc_id)
        if current_user.is_authenticated and doc.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403
        return jsonify({"id": doc.id, "filename": doc.filename, "content_text": doc.content_text, "uploaded_at": doc.uploaded_at.strftime('%Y-%m-%d %H:%M')})
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
        chat_session = ChatSession(title="Doc: " + doc.filename[:30], tool="documents", user_id=current_user.id if current_user.is_authenticated else None)
        db.session.add(chat_session)
        db.session.commit()
        user_msg = ChatMessage(session_id=chat_session.id, role='user', content="[Document: " + doc.filename + "] " + question)
        db.session.add(user_msg)
        db.session.commit()
        doc_content = doc.content_text[:3000] if doc.content_text else "No text content available."
        doc_prompt = "Document content:\n" + doc_content + "\n\nQuestion: " + question
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[
                {"role": "system", "content": TOOL_PROMPTS["documents"]}, 
                {"role": "user", "content": doc_prompt}
            ]
        )
        answer = response.choices[0].message.content
        ai_msg = ChatMessage(session_id=chat_session.id, role='ai', content=answer)
        db.session.add(ai_msg)
        db.session.commit()
        return jsonify({"answer": answer, "session_id": chat_session.id, "document_id": doc.id, "remaining": msg if isinstance(msg, int) else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# TAX UPDATES APIs
# ========================

@app.route("/api/news", methods=["GET"])
def get_news():
    try:
        category = request.args.get('category', 'all')
        query = NewsUpdate.query
        if category != 'all':
            query = query.filter_by(category=category)
        news = query.order_by(NewsUpdate.is_pinned.desc(), NewsUpdate.created_at.desc()).all()
        return jsonify([n.to_dict() for n in news])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/news/<int:news_id>", methods=["GET"])
def get_news_item(news_id):
    try:
        news = NewsUpdate.query.get_or_404(news_id)
        return jsonify(news.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/news", methods=["POST"])
@admin_required
def create_news():
    try:
        data = request.get_json()
        title = data.get("title", "").strip()
        content = data.get("content", "").strip()
        excerpt = data.get("excerpt", "").strip()
        category = data.get("category", "general")
        source = data.get("source", "").strip()
        source_url = data.get("source_url", "").strip()
        is_pinned = data.get("is_pinned", False)
        if not title or not content:
            return jsonify({"error": "Title and content are required"}), 400
        if category not in ['tz', 'ke', 'ug', 'eac', 'general']:
            return jsonify({"error": "Invalid category"}), 400
        news = NewsUpdate(title=title, content=content, excerpt=excerpt or None, category=category, source=source or None, source_url=source_url or None, is_pinned=is_pinned, is_admin_post=True, created_by=current_user.id)
        db.session.add(news)
        db.session.commit()
        log_audit("create_news", "news_update", news.id, "Created: " + title)
        return jsonify({"message": "News update created", "news": news.to_dict()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/news/<int:news_id>", methods=["PUT"])
@admin_required
def update_news(news_id):
    try:
        news = NewsUpdate.query.get_or_404(news_id)
        data = request.get_json()
        news.title = data.get("title", news.title).strip()
        news.content = data.get("content", news.content).strip()
        news.excerpt = data.get("excerpt", news.excerpt)
        news.category = data.get("category", news.category)
        news.source = data.get("source", news.source)
        news.source_url = data.get("source_url", news.source_url)
        news.is_pinned = data.get("is_pinned", news.is_pinned)
        db.session.commit()
        log_audit("update_news", "news_update", news.id, "Updated: " + news.title)
        return jsonify({"message": "News update updated", "news": news.to_dict()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/news/<int:news_id>", methods=["DELETE"])
@admin_required
def delete_news(news_id):
    try:
        news = NewsUpdate.query.get_or_404(news_id)
        db.session.delete(news)
        db.session.commit()
        log_audit("delete_news", "news_update", news_id, "Deleted: " + news.title)
        return jsonify({"message": "News update deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/news/<int:news_id>/pin", methods=["POST"])
@admin_required
def toggle_pin_news(news_id):
    try:
        news = NewsUpdate.query.get_or_404(news_id)
        news.is_pinned = not news.is_pinned
        db.session.commit()
        action = "pinned" if news.is_pinned else "unpinned"
        log_audit(action + "_news", "news_update", news.id)
        return jsonify({"message": "News " + action, "is_pinned": news.is_pinned})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# TAX COMPARISON APIs
# ========================

@app.route("/api/comparison", methods=["GET"])
def get_comparison():
    try:
        tax_type = request.args.get('tax_type', 'all')
        country = request.args.get('country', 'all')
        query = TaxComparisonData.query
        if tax_type != 'all':
            query = query.filter_by(tax_type=tax_type)
        if country != 'all':
            query = query.filter_by(country=country)
        data = query.all()
        return jsonify([d.to_dict() for d in data])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/comparison/<tax_type>", methods=["GET"])
def get_comparison_by_type(tax_type):
    try:
        data = TaxComparisonData.query.filter_by(tax_type=tax_type).all()
        if not data:
            return jsonify({"error": "Tax type not found"}), 404
        return jsonify([d.to_dict() for d in data])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/comparison", methods=["POST"])
@admin_required
def create_comparison_data():
    try:
        data = request.get_json()
        item = TaxComparisonData(tax_type=data.get("tax_type"), country=data.get("country"), metric=data.get("metric"), value=data.get("value"), details=data.get("details"))
        db.session.add(item)
        db.session.commit()
        log_audit("create_comparison", "tax_comparison", item.id)
        return jsonify({"message": "Comparison data added", "data": item.to_dict()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/comparison/<int:item_id>", methods=["PUT"])
@admin_required
def update_comparison_data(item_id):
    try:
        item = TaxComparisonData.query.get_or_404(item_id)
        data = request.get_json()
        item.tax_type = data.get("tax_type", item.tax_type)
        item.country = data.get("country", item.country)
        item.metric = data.get("metric", item.metric)
        item.value = data.get("value", item.value)
        item.details = data.get("details", item.details)
        db.session.commit()
        log_audit("update_comparison", "tax_comparison", item.id)
        return jsonify({"message": "Comparison data updated", "data": item.to_dict()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/comparison/<int:item_id>", methods=["DELETE"])
@admin_required
def delete_comparison_data(item_id):
    try:
        item = TaxComparisonData.query.get_or_404(item_id)
        db.session.delete(item)
        db.session.commit()
        log_audit("delete_comparison", "tax_comparison", item_id)
        return jsonify({"message": "Comparison data deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# DEADLINES APIs
# ========================

@app.route("/api/deadlines", methods=["GET"])
def get_deadlines():
    try:
        country = request.args.get('country', 'all')
        query = TaxDeadline.query.filter_by(is_active=True)
        if country != 'all':
            query = query.filter_by(country=country)
        deadlines = query.order_by(TaxDeadline.due_date.asc()).all()
        return jsonify([d.to_dict() for d in deadlines])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/deadlines/<int:deadline_id>", methods=["GET"])
def get_deadline(deadline_id):
    try:
        deadline = TaxDeadline.query.get_or_404(deadline_id)
        return jsonify(deadline.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/deadlines", methods=["POST"])
@admin_required
def create_deadline():
    try:
        data = request.get_json()
        name = data.get("name", "").strip()
        description = data.get("description", "").strip()
        due_date_str = data.get("due_date")
        recurrence = data.get("recurrence", "monthly")
        country = data.get("country", "Tanzania")
        penalty_note = data.get("penalty_note", "").strip()
        if not name or not due_date_str:
            return jsonify({"error": "Name and due date are required"}), 400
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        deadline = TaxDeadline(name=name, description=description, due_date=due_date, recurrence=recurrence, country=country, penalty_note=penalty_note)
        db.session.add(deadline)
        db.session.commit()
        log_audit("create_deadline", "tax_deadline", deadline.id, "Created: " + name)
        return jsonify({"message": "Deadline created", "deadline": deadline.to_dict()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/deadlines/<int:deadline_id>", methods=["PUT"])
@admin_required
def update_deadline(deadline_id):
    try:
        deadline = TaxDeadline.query.get_or_404(deadline_id)
        data = request.get_json()
        deadline.name = data.get("name", deadline.name).strip()
        deadline.description = data.get("description", deadline.description)
        if data.get("due_date"):
            deadline.due_date = datetime.strptime(data.get("due_date"), '%Y-%m-%d')
        deadline.recurrence = data.get("recurrence", deadline.recurrence)
        deadline.country = data.get("country", deadline.country)
        deadline.penalty_note = data.get("penalty_note", deadline.penalty_note)
        deadline.is_active = data.get("is_active", deadline.is_active)
        db.session.commit()
        log_audit("update_deadline", "tax_deadline", deadline.id, "Updated: " + deadline.name)
        return jsonify({"message": "Deadline updated", "deadline": deadline.to_dict()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/deadlines/<int:deadline_id>", methods=["DELETE"])
@admin_required
def delete_deadline(deadline_id):
    try:
        deadline = TaxDeadline.query.get_or_404(deadline_id)
        db.session.delete(deadline)
        db.session.commit()
        log_audit("delete_deadline", "tax_deadline", deadline_id, "Deleted: " + deadline.name)
        return jsonify({"message": "Deadline deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# ADMIN APIs
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
        return jsonify({"total_visitors": total_visitors, "total_visits": total_visits, "today_visitors": today_visitors, "today_unique": today_unique, "country_stats": [{"country": c, "count": count} for c, count in country_stats], "recent_visitors": [{"ip": v.ip_address, "page": v.page_visited, "is_logged_in": v.is_logged_in, "country": v.country, "time": v.created_at.strftime("%Y-%m-%d %H:%M")} for v in recent]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/users-detailed", methods=["GET"])
@admin_required
def admin_users_detailed():
    try:
        users = User.query.order_by(User.created_at.desc()).all()
        return jsonify([{"id": u.id, "email": u.email, "country": u.country, "role": u.role, "is_guest": u.is_guest, "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else None, "session_count": ChatSession.query.filter_by(user_id=u.id).count(), "document_count": Document.query.filter_by(user_id=u.id).count()} for u in users])
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
        log_audit("update_role", "user", user_id, "Changed from " + old_role + " to " + new_role)
        return jsonify({"message": "User role updated from " + old_role + " to " + new_role, "user_id": user.id, "email": user.email, "new_role": new_role})
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
        doc = TrainingDocument(title=title, filename=filename, content_text=content_text[:50000], doc_type=doc_type, source="admin_upload", jurisdiction=jurisdiction, uploaded_by=current_user.id)
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

@app.route("/api/feedback/stats", methods=["GET"])
@admin_required
def feedback_stats():
    try:
        return jsonify({"helpful": 0, "incomplete": 0, "incorrect": 0})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/audit-logs", methods=["GET"])
@admin_required
def get_audit_logs():
    try:
        logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
        return jsonify([l.to_dict() for l in logs])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/stats", methods=["GET"])
@admin_required
def admin_stats():
    try:
        total_users = User.query.count()
        total_sessions = ChatSession.query.count()
        return jsonify({"users": {"total": total_users}, "activity": {"sessions": total_sessions}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/news", methods=["GET"])
@admin_required
def admin_get_all_news():
    try:
        news = NewsUpdate.query.order_by(NewsUpdate.created_at.desc()).all()
        return jsonify([n.to_dict() for n in news])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/deadlines", methods=["GET"])
@admin_required
def admin_get_all_deadlines():
    try:
        deadlines = TaxDeadline.query.order_by(TaxDeadline.due_date.asc()).all()
        return jsonify([d.to_dict() for d in deadlines])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/comparison", methods=["GET"])
@admin_required
def admin_get_all_comparison():
    try:
        data = TaxComparisonData.query.order_by(TaxComparisonData.tax_type, TaxComparisonData.country).all()
        return jsonify([d.to_dict() for d in data])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/create-admin/<email>")
def create_admin(email):
    try:
        user = User.query.filter_by(email=email.lower()).first()
        if not user:
            hashed_password = generate_password_hash("temp123")
            user = User(email=email.lower(), password=hashed_password, country="Tanzania", role="admin", is_guest=False)
            db.session.add(user)
            db.session.commit()
            return jsonify({"message": "Created " + email + " as admin", "password": "temp123", "action": "created"})
        else:
            user.role = "admin"
            db.session.commit()
            return jsonify({"message": email + " is now admin", "action": "promoted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/rag-test", methods=["GET", "POST"])
@admin_required
def test_rag():
    try:
        if request.method == "POST":
            data = request.get_json() or {}
            query = data.get("query", "What is VAT in Tanzania?")
            jurisdiction = data.get("jurisdiction", "Tanzania")
        else:
            query = request.args.get("query", "What is VAT in Tanzania?")
            jurisdiction = request.args.get("jurisdiction", "Tanzania")
        context = search_training_docs(query, jurisdiction)
        all_docs = TrainingDocument.query.filter(TrainingDocument.jurisdiction == jurisdiction).all()
        doc_list = []
        for doc in all_docs:
            doc_list.append({"id": doc.id, "title": doc.title, "type": doc.doc_type, "content_length": len(doc.content_text) if doc.content_text else 0, "has_content": bool(doc.content_text and len(doc.content_text) > 50)})
        return jsonify({"query": query, "jurisdiction": jurisdiction, "context_found": bool(context), "context_length": len(context), "context_preview": context[:2000] if context else "No relevant documents found", "total_documents": len(all_docs), "documents": doc_list})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/test")
def test():
    return jsonify({"status": "ok"})

# ========================
# DATABASE INIT & MIGRATION
# ========================

# ========================
# BUSINESS LEADS APIs
# ========================

@app.route("/api/business-leads", methods=["POST"])
def create_business_lead():
    try:
        data = request.get_json()
        name = data.get("name", "").strip()
        email = data.get("email", "").strip()
        phone = data.get("phone", "").strip()
        country = data.get("country", "").strip()
        business_type = data.get("business_type", "").strip()
        business_description = data.get("business_description", "").strip()
        if not name or not email or not phone or not business_type:
            return jsonify({"error": "Name, email, phone and business type are required"}), 400
        lead = BusinessLead(name=name, email=email, phone=phone, country=country, business_type=business_type, business_description=business_description)
        db.session.add(lead)
        db.session.commit()
        log_audit("new_business_lead", "business_lead", lead.id, "Lead: " + name + " - " + business_type)
        return jsonify({"message": "Thank you! Our advisors will contact you within 24 hours.", "lead_id": lead.id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/business-leads", methods=["GET"])
@admin_required
def get_business_leads():
    try:
        leads = BusinessLead.query.order_by(BusinessLead.created_at.desc()).all()
        return jsonify([l.to_dict() for l in leads])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/business-leads/<int:lead_id>/status", methods=["PUT"])
@admin_required
def update_lead_status(lead_id):
    try:
        lead = BusinessLead.query.get_or_404(lead_id)
        data = request.get_json()
        lead.status = data.get("status", lead.status)
        db.session.commit()
        return jsonify({"message": "Status updated", "lead": lead.to_dict()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


class DraftedResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    response_type = db.Column(db.String(100), nullable=False)
    document_name = db.Column(db.String(300), nullable=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    def to_dict(self):
        return {'id': self.id, 'response_type': self.response_type, 'document_name': self.document_name, 'content': self.content, 'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None}

# ========================
# TRA RESPONSE DRAFTER APIs
# ========================

RESPONSE_PROMPTS = {
    'demand_notice': 'Draft a formal response to a TRA Demand Notice. The response should: acknowledge receipt, dispute or clarify the amounts if applicable, reference relevant sections of the Income Tax Act or VAT Act Cap 148, request supporting schedules, and propose a payment plan if appropriate. Use formal legal language suitable for submission to TRA Tanzania.',
    'tax_examination': 'Draft a formal response to a TRA Tax Examination Notice. The response should: acknowledge the examination notice, confirm availability for examination, list documents to be provided, reference taxpayer rights under the Tax Administration Act, and request reasonable timeframes.',
    'tax_audit': 'Draft a formal response to a TRA Tax Audit Notice. The response should: acknowledge the audit, confirm cooperation, list documents being provided, raise any procedural objections if applicable, and reference the Tax Administration Act Cap 438.',
    'vat_verification': 'Draft a formal response to a TRA VAT Verification Notice. The response should: acknowledge the verification, provide explanations for any VAT discrepancies, reference the VAT Act Cap 148, and attach relevant supporting schedules.',
    'tax_investigation': 'Draft a formal response to a TRA Tax Investigation Notice. The response should: acknowledge the investigation, assert taxpayer rights, request disclosure of specific allegations, and reference the Tax Administration Act Cap 438.',
    'objection': 'Draft a formal Objection to TRA assessment. The objection must: be filed within 30 days, reference the specific assessment, state grounds of objection with reference to specific tax laws, include supporting facts and calculations, and comply with Section 51 of the Tax Administration Act Cap 438.',
    'notice_of_appeal': 'Draft a formal Notice of Intention to Appeal to the Tax Revenue Appeals Board (TRAB). The notice should: reference the TRA objection decision, state grounds for appeal, reference Section 16 of the Tax Revenue Appeals Act Cap 408, and be filed within 30 days of the objection decision.',
    'trab_appeal': 'Draft a formal Appeal Statement to the Tax Revenue Appeals Board (TRAB). The statement should: include statement of facts, grounds of appeal referencing specific tax laws, relief sought, reference the Tax Revenue Appeals Act Cap 408, and follow TRAB procedural rules.',
    'trat_appeal': 'Draft a formal Appeal Statement to the Tax Revenue Appeals Tribunal (TRAT). The statement should: reference the TRAB decision, state grounds of appeal on points of law, reference Section 25 of the Tax Revenue Appeals Act Cap 408, and follow formal tribunal drafting standards.',
    'high_court_appeal': 'Draft a formal Appeal Statement to the High Court of Tanzania (Commercial Division). The statement should: reference the TRAT decision, limit grounds to questions of law, follow High Court Civil Procedure Rules, reference the Tax Revenue Appeals Act Cap 408 and relevant precedents, and use formal court pleading style.'
}

RESPONSE_LABELS = {
    'demand_notice': 'Response to Demand Notice',
    'tax_examination': 'Response to Tax Examination Notice',
    'tax_audit': 'Response to Tax Audit Notice',
    'vat_verification': 'Response to VAT Verification',
    'tax_investigation': 'Response to Tax Investigation',
    'objection': 'Draft Objection to TRA',
    'notice_of_appeal': 'Notice of Intention to Appeal',
    'trab_appeal': 'Appeal Statement to TRAB',
    'trat_appeal': 'Appeal Statement to TRAT',
    'high_court_appeal': 'Appeal Statement to High Court'
}

@app.route("/api/documents/<int:doc_id>/draft-response", methods=["POST"])
@login_required
def draft_tra_response(doc_id):
    try:
        doc = Document.query.get_or_404(doc_id)
        if doc.user_id != current_user.id and current_user.role != 'admin':
            return jsonify({"error": "Access denied"}), 403
        data = request.get_json()
        response_type = data.get("response_type", "").strip()
        if response_type not in RESPONSE_PROMPTS:
            return jsonify({"error": "Invalid response type"}), 400
        doc_text = ""
        try:
            import PyPDF2, io
            file_data = doc.file_data
            if doc.filename.lower().endswith('.pdf'):
                reader = PyPDF2.PdfReader(io.BytesIO(file_data))
                doc_text = " ".join(page.extract_text() or "" for page in reader.pages)
            else:
                doc_text = file_data.decode('utf-8', errors='ignore')
            doc_text = doc_text[:6000]
        except Exception:
            doc_text = "[Document content could not be extracted - draft based on response type only]"
        system_prompt = """You are an expert Tanzanian tax lawyer and advocate with deep knowledge of:
- Income Tax Act Cap 332
- Value Added Tax Act Cap 148  
- Tax Administration Act Cap 438
- Tax Revenue Appeals Act Cap 408
- Tanzania Revenue Authority Act Cap 399
Draft formal, professional legal documents suitable for submission to TRA or Tanzanian courts/tribunals.
Always include: proper headings, date placeholders [DATE], reference numbers [REF NO], taxpayer details [TAXPAYER NAME/TIN], and signature blocks."""
        user_prompt = f"""Based on this TRA notice/document:

{doc_text}

{RESPONSE_PROMPTS[response_type]}

Draft the complete formal document now. Use [PLACEHOLDER] format for information that needs to be filled in by the client."""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            max_tokens=2000,
            temperature=0.3
        )
        draft_content = response.choices[0].message.content
        saved = False
        draft_id = None
        if current_user.is_premium:
            draft = DraftedResponse(user_id=current_user.id, document_id=doc_id, response_type=RESPONSE_LABELS[response_type], document_name=doc.filename, content=draft_content)
            db.session.add(draft)
            db.session.commit()
            saved = True
            draft_id = draft.id
        return jsonify({"draft": draft_content, "response_type": RESPONSE_LABELS[response_type], "saved": saved, "draft_id": draft_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/my-drafts", methods=["GET"])
@login_required
def get_my_drafts():
    if not current_user.is_premium:
        return jsonify({"error": "Premium feature. Upgrade to save and retrieve drafts."}), 403
    drafts = DraftedResponse.query.filter_by(user_id=current_user.id).order_by(DraftedResponse.created_at.desc()).all()
    return jsonify([d.to_dict() for d in drafts])

@app.route("/api/my-drafts/<int:draft_id>", methods=["DELETE"])
@login_required
def delete_draft(draft_id):
    draft = DraftedResponse.query.get_or_404(draft_id)
    if draft.user_id != current_user.id and current_user.role != 'admin':
        return jsonify({"error": "Access denied"}), 403
    db.session.delete(draft)
    db.session.commit()
    return jsonify({"message": "Draft deleted"})

@app.route("/api/admin/users/<int:user_id>/premium", methods=["PUT"])
@admin_required
def toggle_premium(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    user.is_premium = data.get("is_premium", False)
    db.session.commit()
    return jsonify({"message": "Updated", "is_premium": user.is_premium})


def migrate_db():
    with app.app_context():
        try:
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            if 'user' in tables:
                columns = [c['name'] for c in inspector.get_columns('user')]
                if 'created_at' not in columns:
                    db.session.execute(db.text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS created_at TIMESTAMP'))
                    db.session.commit()
                if 'is_guest' not in columns:
                    db.session.execute(db.text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_guest BOOLEAN DEFAULT FALSE'))
                    db.session.commit()
            if 'chat_session' in tables:
                columns = [c['name'] for c in inspector.get_columns('chat_session')]
                if 'user_id' not in columns:
                    db.session.execute(db.text("ALTER TABLE chat_session ADD COLUMN IF NOT EXISTS user_id INTEGER"))
                    db.session.commit()
            if 'document' in tables:
                columns = [c['name'] for c in inspector.get_columns('document')]
                if 'user_id' not in columns:
                    db.session.execute(db.text("ALTER TABLE document ADD COLUMN IF NOT EXISTS user_id INTEGER"))
                    db.session.commit()
                if 'content_text' not in columns:
                    db.session.execute(db.text("ALTER TABLE document ADD COLUMN IF NOT EXISTS content_text TEXT"))
                    db.session.commit()
                if 'session_id' not in columns:
                    db.session.execute(db.text("ALTER TABLE document ADD COLUMN IF NOT EXISTS session_id INTEGER"))
                    db.session.commit()
                if 'is_premium' not in columns:
                    db.session.execute(db.text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT FALSE'))
                    db.session.commit()
            db.create_all()
            seed_comparison_data()
            seed_deadlines()
            seed_sample_news()
        except Exception as e:
            print("Migration warning: " + str(e))
            db.create_all()
            seed_comparison_data()
            seed_deadlines()
            seed_sample_news()

migrate_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)