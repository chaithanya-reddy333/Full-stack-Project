"""
Automated Quiz Engine with PDF Certification Generation
========================================================
Full-stack Flask application with:
  - User authentication (register / login / logout)
  - Admin panel (quiz & question management)
  - Quiz engine with timer & randomised questions
  - Automatic PDF certificate generation via ReportLab
  - SQLite database (Flask-SQLAlchemy)
  - Leaderboard
"""

import os
import uuid
import datetime

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, send_from_directory, abort
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

# ============================================================
#  Application & Database Setup
# ============================================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CERT_DIR = os.path.join(BASE_DIR, 'certificates')
os.makedirs(CERT_DIR, exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'quiz-engine-super-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ============================================================
#  Database Models
# ============================================================

class User(db.Model):
    """Stores registered users (regular + admin)."""
    __tablename__ = 'users'
    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(120), nullable=False)
    email    = db.Column(db.String(200), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    results  = db.relationship('Result', backref='user', lazy=True)


class Quiz(db.Model):
    """A quiz with a title, description and a passing score threshold."""
    __tablename__ = 'quizzes'
    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(200), nullable=False)
    description   = db.Column(db.Text, default='')
    passing_score = db.Column(db.Integer, default=60)   # percentage
    time_limit    = db.Column(db.Integer, default=600)  # seconds (0 = no limit)
    created_at    = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    questions = db.relationship('Question', backref='quiz', lazy=True,
                                cascade='all, delete-orphan')
    results   = db.relationship('Result',   backref='quiz', lazy=True,
                                cascade='all, delete-orphan')


class Question(db.Model):
    """A single multiple-choice question belonging to a Quiz."""
    __tablename__ = 'questions'
    id             = db.Column(db.Integer, primary_key=True)
    quiz_id        = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    question       = db.Column(db.Text, nullable=False)
    option1        = db.Column(db.String(300), nullable=False)
    option2        = db.Column(db.String(300), nullable=False)
    option3        = db.Column(db.String(300), nullable=False)
    option4        = db.Column(db.String(300), nullable=False)
    correct_option = db.Column(db.Integer, nullable=False)  # 1-4


class Result(db.Model):
    """Stores the result of a user's quiz attempt."""
    __tablename__ = 'results'
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quiz_id        = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    score          = db.Column(db.Float, nullable=False)      # percentage
    passed         = db.Column(db.Boolean, default=False)
    certificate_id = db.Column(db.String(36), unique=True, nullable=True)
    taken_at       = db.Column(db.DateTime, default=datetime.datetime.utcnow)


# ============================================================
#  Helpers
# ============================================================

def login_required(f):
    """Decorator: user must be logged in."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator: user must be an admin."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('admin_login'))
        user = db.session.get(User, session['user_id'])
        if not user or not user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def current_user():
    """Return the User object for the active session, or None."""
    if 'user_id' in session:
        return db.session.get(User, session['user_id'])
    return None


def generate_certificate_pdf(result_id: int) -> str:
    """
    Generate a professional PDF certificate using ReportLab.
    Returns the certificate filename (stored in /certificates/).
    """
    result = db.session.get(Result, result_id)
    user   = db.session.get(User, result.user_id)
    quiz   = db.session.get(Quiz, result.quiz_id)

    filename  = f"certificate_{result.certificate_id}.pdf"
    filepath  = os.path.join(CERT_DIR, filename)

    # --- Canvas setup (landscape A4) ---
    page_w, page_h = landscape(A4)
    c = canvas.Canvas(filepath, pagesize=landscape(A4))

    # Background gradient simulation (layered rectangles)
    c.setFillColor(colors.HexColor('#0f0e17'))
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Decorative top band
    c.setFillColor(colors.HexColor('#6C63FF'))
    c.rect(0, page_h - 18, page_w, 18, fill=1, stroke=0)

    # Decorative bottom band
    c.setFillColor(colors.HexColor('#43C6AC'))
    c.rect(0, 0, page_w, 12, fill=1, stroke=0)

    # Outer border
    c.setStrokeColor(colors.HexColor('#6C63FF'))
    c.setLineWidth(3)
    c.rect(20, 20, page_w - 40, page_h - 40, fill=0, stroke=1)

    # Inner decorative border (dashed look)
    c.setStrokeColor(colors.HexColor('#43C6AC'))
    c.setLineWidth(1)
    c.setDash(6, 4)
    c.rect(30, 30, page_w - 60, page_h - 60, fill=0, stroke=1)
    c.setDash()  # reset dash

    # ---- Certificate seal / emoji substitute ----
    c.setFont('Helvetica-Bold', 60)
    c.setFillColor(colors.HexColor('#FFD700'))
    c.drawCentredString(page_w / 2, page_h - 100, '🏆')

    # ---- Titles ----
    c.setFont('Helvetica-Bold', 30)
    c.setFillColor(colors.HexColor('#FFD700'))
    c.drawCentredString(page_w / 2, page_h - 140, 'Certificate of Achievement')

    c.setFont('Helvetica', 13)
    c.setFillColor(colors.HexColor('#a89dff'))
    c.drawCentredString(page_w / 2, page_h - 165, 'THIS IS TO CERTIFY THAT')

    # ---- User name ----
    c.setFont('Helvetica-Bold', 38)
    c.setFillColor(colors.white)
    c.drawCentredString(page_w / 2, page_h - 210, user.name)

    # Underline for name
    name_w = c.stringWidth(user.name, 'Helvetica-Bold', 38)
    c.setStrokeColor(colors.HexColor('#43C6AC'))
    c.setLineWidth(2)
    c.line(page_w / 2 - name_w / 2, page_h - 215,
           page_w / 2 + name_w / 2, page_h - 215)

    # ---- Body text ----
    c.setFont('Helvetica', 14)
    c.setFillColor(colors.HexColor('#cccccc'))
    c.drawCentredString(page_w / 2, page_h - 245, 'has successfully completed the quiz')

    c.setFont('Helvetica-Bold', 20)
    c.setFillColor(colors.HexColor('#6C63FF'))
    c.drawCentredString(page_w / 2, page_h - 275, f'"{quiz.title}"')

    # ---- Score ----
    c.setFont('Helvetica-Bold', 16)
    c.setFillColor(colors.HexColor('#43C6AC'))
    score_text = f'with a score of  {result.score:.1f}%'
    c.drawCentredString(page_w / 2, page_h - 310, score_text)

    # ---- Date ----
    date_str = result.taken_at.strftime('%B %d, %Y')
    c.setFont('Helvetica', 13)
    c.setFillColor(colors.HexColor('#aaaaaa'))
    c.drawCentredString(page_w / 2, page_h - 340, f'Date of Completion: {date_str}')

    # ---- Footer columns ----
    footer_y = 70

    # Signature placeholder (left)
    c.setFont('Helvetica-Oblique', 20)
    c.setFillColor(colors.HexColor('#6C63FF'))
    c.drawCentredString(page_w * 0.25, footer_y + 20, 'Administrator')
    c.setStrokeColor(colors.HexColor('#6C63FF'))
    c.setLineWidth(1.5)
    c.line(page_w * 0.12, footer_y + 14, page_w * 0.38, footer_y + 14)
    c.setFont('Helvetica', 10)
    c.setFillColor(colors.HexColor('#888888'))
    c.drawCentredString(page_w * 0.25, footer_y, 'Authorized Signature')

    # Certificate ID (center)
    c.setFont('Helvetica', 9)
    c.setFillColor(colors.HexColor('#666666'))
    c.drawCentredString(page_w / 2, footer_y + 10, 'CERTIFICATE ID')
    c.setFont('Courier-Bold', 10)
    c.setFillColor(colors.HexColor('#a89dff'))
    c.drawCentredString(page_w / 2, footer_y - 4, result.certificate_id)

    # Passing score (right)
    c.setFont('Helvetica', 10)
    c.setFillColor(colors.HexColor('#888888'))
    c.drawCentredString(page_w * 0.75, footer_y + 10, 'PASSING SCORE')
    c.setFont('Helvetica-Bold', 14)
    c.setFillColor(colors.HexColor('#43C6AC'))
    c.drawCentredString(page_w * 0.75, footer_y - 5, f'{quiz.passing_score}%')

    c.save()
    return filename


# ============================================================
#  Initialise DB + Seed Sample Data
# ============================================================

def seed_sample_data():
    """Insert sample quizzes, questions, and an admin account if empty."""

    # Admin account
    if not User.query.filter_by(email='admin@quiz.com').first():
        admin = User(
            name='Admin',
            email='admin@quiz.com',
            password=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)

    # Sample user
    if not User.query.filter_by(email='user@quiz.com').first():
        user = User(
            name='Alice Johnson',
            email='user@quiz.com',
            password=generate_password_hash('user123'),
        )
        db.session.add(user)

    if Quiz.query.count() == 0:
        # --- Quiz 1: Python Basics ---
        q1 = Quiz(title='Python Fundamentals',
                  description='Test your knowledge of core Python concepts.',
                  passing_score=60, time_limit=300)
        db.session.add(q1)
        db.session.flush()
        questions_q1 = [
            Question(quiz_id=q1.id,
                     question='What is the output of print(type([]))?',
                     option1='<class "list">',  option2='<class "tuple">',
                     option3='<class "dict">',  option4='<class "set">',
                     correct_option=1),
            Question(quiz_id=q1.id,
                     question='Which keyword is used to define a function in Python?',
                     option1='function', option2='fun',
                     option3='def',      option4='define',
                     correct_option=3),
            Question(quiz_id=q1.id,
                     question='What does "PEP 8" refer to?',
                     option1='A Python library',
                     option2='A style guide for Python code',
                     option3='A Python testing framework',
                     option4='A Python data structure',
                     correct_option=2),
            Question(quiz_id=q1.id,
                     question='Which of these is a mutable data type?',
                     option1='tuple', option2='string',
                     option3='int',   option4='list',
                     correct_option=4),
            Question(quiz_id=q1.id,
                     question='What is a lambda function in Python?',
                     option1='A named function',
                     option2='An anonymous function',
                     option3='A recursive function',
                     option4='A built-in library',
                     correct_option=2),
        ]
        db.session.add_all(questions_q1)

        # --- Quiz 2: Web Development ---
        q2 = Quiz(title='Web Development Essentials',
                  description='HTML, CSS, JavaScript, and HTTP fundamentals.',
                  passing_score=70, time_limit=420)
        db.session.add(q2)
        db.session.flush()
        questions_q2 = [
            Question(quiz_id=q2.id,
                     question='What does HTML stand for?',
                     option1='Hyperlinks and Text Markup Language',
                     option2='Hyper Text Markup Language',
                     option3='Home Tool Markup Language',
                     option4='Hyper Tool Markup Language',
                     correct_option=2),
            Question(quiz_id=q2.id,
                     question='Which CSS property controls text size?',
                     option1='font-weight', option2='text-size',
                     option3='font-size',   option4='text-height',
                     correct_option=3),
            Question(quiz_id=q2.id,
                     question='Which of the following is NOT a valid HTTP method?',
                     option1='GET',    option2='POST',
                     option3='FETCH',  option4='DELETE',
                     correct_option=3),
            Question(quiz_id=q2.id,
                     question='What does the DOM stand for?',
                     option1='Document Object Model',
                     option2='Data Object Method',
                     option3='Design Output Model',
                     option4='Document Order Method',
                     correct_option=1),
            Question(quiz_id=q2.id,
                     question='Which JavaScript method is used to add an element to the end of an array?',
                     option1='append()', option2='add()',
                     option3='push()',   option4='insert()',
                     correct_option=3),
            Question(quiz_id=q2.id,
                     question='What is the default display property of a <div> element?',
                     option1='inline',       option2='block',
                     option3='inline-block', option4='flex',
                     correct_option=2),
        ]
        db.session.add_all(questions_q2)

        # --- Quiz 3: Data Science ---
        q3 = Quiz(title='Data Science & ML Basics',
                  description='Intro-level concepts in data science and machine learning.',
                  passing_score=65, time_limit=480)
        db.session.add(q3)
        db.session.flush()
        questions_q3 = [
            Question(quiz_id=q3.id,
                     question='What does "overfitting" mean in machine learning?',
                     option1='Model performs poorly on training data',
                     option2='Model performs well on training but poorly on new data',
                     option3='Model is too simple',
                     option4='Model takes too long to train',
                     correct_option=2),
            Question(quiz_id=q3.id,
                     question='Which Python library is primarily used for data manipulation?',
                     option1='NumPy', option2='Matplotlib',
                     option3='Pandas', option4='Scikit-learn',
                     correct_option=3),
            Question(quiz_id=q3.id,
                     question='What is a "feature" in the context of machine learning?',
                     option1='A bug in the model',
                     option2='An individual measurable property of the data',
                     option3='The output of the model',
                     option4='A type of neural network',
                     correct_option=2),
            Question(quiz_id=q3.id,
                     question='What does "supervised learning" mean?',
                     option1='Learning without any data',
                     option2='Learning with labeled training data',
                     option3='Learning with unlabeled data',
                     option4='Learning using reinforcement',
                     correct_option=2),
            Question(quiz_id=q3.id,
                     question='What is the purpose of a confusion matrix?',
                     option1='To visualize model architecture',
                     option2='To show training loss over epochs',
                     option3='To evaluate classification model performance',
                     option4='To debug Python code',
                     correct_option=3),
        ]
        db.session.add_all(questions_q3)

    db.session.commit()


# ============================================================
#  Context Processor – inject current_user into every template
# ============================================================

@app.context_processor
def inject_user():
    return dict(current_user=current_user())


# ============================================================
#  Public Routes
# ============================================================

@app.route('/')
def index():
    """Home page – show published quizzes."""
    quizzes = Quiz.query.all()
    # Leaderboard: top 5 results sorted by score desc
    top_results = (
        db.session.query(Result, User, Quiz)
        .join(User, Result.user_id == User.id)
        .join(Quiz, Result.quiz_id == Quiz.id)
        .filter(Result.passed == True)
        .order_by(Result.score.desc())
        .limit(5)
        .all()
    )
    return render_template('index.html', quizzes=quizzes, top_results=top_results)


# ---- Auth ----

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        if not all([name, email, password, confirm]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'danger')
            return redirect(url_for('register'))

        user = User(name=name, email=email,
                    password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email, is_admin=False).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ---- Dashboard ----

@app.route('/dashboard')
@login_required
def dashboard():
    user    = current_user()
    quizzes = Quiz.query.all()
    results = (Result.query
               .filter_by(user_id=user.id)
               .order_by(Result.taken_at.desc())
               .all())
    # Map quiz_id -> result for quick lookup
    result_map = {}
    for r in results:
        if r.quiz_id not in result_map:
            result_map[r.quiz_id] = r  # first (most recent) attempt only

    total_taken   = len(set(r.quiz_id for r in results))
    total_passed  = sum(1 for r in results if r.passed)
    avg_score     = round(sum(r.score for r in results) / len(results), 1) if results else 0

    return render_template('dashboard.html',
                           user=user,
                           quizzes=quizzes,
                           results=results,
                           result_map=result_map,
                           total_taken=total_taken,
                           total_passed=total_passed,
                           avg_score=avg_score)


# ---- Quiz ----

@app.route('/quiz/<int:quiz_id>')
@login_required
def quiz(quiz_id):
    """Display the quiz page with all questions."""
    quiz_obj = db.get_or_404(Quiz, quiz_id)
    if not quiz_obj.questions:
        flash('This quiz has no questions yet.', 'warning')
        return redirect(url_for('dashboard'))

    import random
    questions = quiz_obj.questions[:]
    random.shuffle(questions)
    return render_template('quiz.html', quiz=quiz_obj, questions=questions)


@app.route('/quiz/<int:quiz_id>/submit', methods=['POST'])
@login_required
def submit_quiz(quiz_id):
    """Process submitted quiz answers, compute score, store result."""
    quiz_obj  = db.get_or_404(Quiz, quiz_id)
    user      = current_user()
    questions = quiz_obj.questions

    correct = 0
    for q in questions:
        ans = request.form.get(f'question_{q.id}')
        if ans and int(ans) == q.correct_option:
            correct += 1

    total   = len(questions)
    score   = round((correct / total) * 100, 1) if total else 0
    passed  = score >= quiz_obj.passing_score
    cert_id = str(uuid.uuid4()) if passed else None

    result = Result(
        user_id=user.id,
        quiz_id=quiz_obj.id,
        score=score,
        passed=passed,
        certificate_id=cert_id
    )
    db.session.add(result)
    db.session.commit()

    # Generate the PDF immediately if passed
    if passed and cert_id:
        generate_certificate_pdf(result.id)

    return redirect(url_for('result', result_id=result.id))


@app.route('/result/<int:result_id>')
@login_required
def result(result_id):
    """Show quiz result to the user."""
    r    = db.get_or_404(Result, result_id)
    user = current_user()
    # Security: users may only view their own results
    if r.user_id != user.id and not user.is_admin:
        abort(403)
    return render_template('result.html', result=r,
                           quiz=r.quiz, user=r.user)


@app.route('/certificate/<int:result_id>/download')
@login_required
def download_certificate(result_id):
    """Download the certificate PDF for a passed quiz."""
    r    = db.get_or_404(Result, result_id)
    user = current_user()
    if r.user_id != user.id and not user.is_admin:
        abort(403)
    if not r.passed or not r.certificate_id:
        flash('No certificate available for this result.', 'warning')
        return redirect(url_for('result', result_id=result_id))

    filename = f"certificate_{r.certificate_id}.pdf"
    if not os.path.exists(os.path.join(CERT_DIR, filename)):
        generate_certificate_pdf(r.id)

    return send_from_directory(CERT_DIR, filename,
                               as_attachment=True,
                               download_name=f"Certificate_{r.quiz.title.replace(' ', '_')}.pdf")


@app.route('/certificate/verify/<cert_id>')
def verify_certificate(cert_id):
    """Public page to verify a certificate by its unique ID."""
    result_obj = Result.query.filter_by(certificate_id=cert_id).first()
    if not result_obj:
        return render_template('verify.html', valid=False, cert_id=cert_id)
    return render_template('verify.html', valid=True,
                           result=result_obj, user=result_obj.user,
                           quiz=result_obj.quiz)


@app.route('/leaderboard')
def leaderboard():
    """Global leaderboard of top passing scores."""
    quizzes = Quiz.query.all()
    # Best (highest score) attempt per user per quiz
    top = (
        db.session.query(Result, User, Quiz)
        .join(User, Result.user_id == User.id)
        .join(Quiz, Result.quiz_id == Quiz.id)
        .filter(Result.passed == True)
        .order_by(Result.score.desc())
        .limit(50)
        .all()
    )
    return render_template('leaderboard.html', top_results=top, quizzes=quizzes)


# ============================================================
#  Admin Routes
# ============================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        admin = User.query.filter_by(email=email, is_admin=True).first()
        if admin and check_password_hash(admin.password, password):
            session['user_id'] = admin.id
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin credentials.', 'danger')
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    total_users   = User.query.filter_by(is_admin=False).count()
    total_quizzes = Quiz.query.count()
    total_results = Result.query.count()
    total_certs   = Result.query.filter_by(passed=True).count()
    recent_results = (
        db.session.query(Result, User, Quiz)
        .join(User, Result.user_id == User.id)
        .join(Quiz, Result.quiz_id == Quiz.id)
        .order_by(Result.taken_at.desc())
        .limit(10)
        .all()
    )
    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           total_quizzes=total_quizzes,
                           total_results=total_results,
                           total_certs=total_certs,
                           recent_results=recent_results)


# ---- Quiz Management ----

@app.route('/admin/quizzes')
@admin_required
def admin_quizzes():
    quizzes = Quiz.query.order_by(Quiz.created_at.desc()).all()
    return render_template('admin/quizzes.html', quizzes=quizzes)


@app.route('/admin/quiz/create', methods=['GET', 'POST'])
@admin_required
def admin_create_quiz():
    if request.method == 'POST':
        title         = request.form.get('title', '').strip()
        description   = request.form.get('description', '').strip()
        passing_score = int(request.form.get('passing_score', 60))
        time_limit    = int(request.form.get('time_limit', 600))
        if not title:
            flash('Quiz title is required.', 'danger')
            return redirect(url_for('admin_create_quiz'))
        quiz = Quiz(title=title, description=description,
                    passing_score=passing_score, time_limit=time_limit)
        db.session.add(quiz)
        db.session.commit()
        flash('Quiz created successfully!', 'success')
        return redirect(url_for('admin_questions', quiz_id=quiz.id))
    return render_template('admin/quiz_form.html', quiz=None)


@app.route('/admin/quiz/<int:quiz_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_quiz(quiz_id):
    quiz = db.get_or_404(Quiz, quiz_id)
    if request.method == 'POST':
        quiz.title         = request.form.get('title', quiz.title).strip()
        quiz.description   = request.form.get('description', '').strip()
        quiz.passing_score = int(request.form.get('passing_score', 60))
        quiz.time_limit    = int(request.form.get('time_limit', 600))
        db.session.commit()
        flash('Quiz updated.', 'success')
        return redirect(url_for('admin_quizzes'))
    return render_template('admin/quiz_form.html', quiz=quiz)


@app.route('/admin/quiz/<int:quiz_id>/delete', methods=['POST'])
@admin_required
def admin_delete_quiz(quiz_id):
    quiz = db.get_or_404(Quiz, quiz_id)
    db.session.delete(quiz)
    db.session.commit()
    flash('Quiz deleted.', 'success')
    return redirect(url_for('admin_quizzes'))


# ---- Question Management ----

@app.route('/admin/quiz/<int:quiz_id>/questions')
@admin_required
def admin_questions(quiz_id):
    quiz = db.get_or_404(Quiz, quiz_id)
    return render_template('admin/questions.html', quiz=quiz)


@app.route('/admin/quiz/<int:quiz_id>/question/add', methods=['GET', 'POST'])
@admin_required
def admin_add_question(quiz_id):
    quiz = db.get_or_404(Quiz, quiz_id)
    if request.method == 'POST':
        q = Question(
            quiz_id        = quiz_id,
            question       = request.form.get('question', '').strip(),
            option1        = request.form.get('option1', '').strip(),
            option2        = request.form.get('option2', '').strip(),
            option3        = request.form.get('option3', '').strip(),
            option4        = request.form.get('option4', '').strip(),
            correct_option = int(request.form.get('correct_option', 1)),
        )
        if not all([q.question, q.option1, q.option2, q.option3, q.option4]):
            flash('Please fill in all fields.', 'danger')
            return redirect(url_for('admin_add_question', quiz_id=quiz_id))
        db.session.add(q)
        db.session.commit()
        flash('Question added.', 'success')
        return redirect(url_for('admin_questions', quiz_id=quiz_id))
    return render_template('admin/question_form.html', quiz=quiz, question=None)


@app.route('/admin/question/<int:q_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_question(q_id):
    q = db.get_or_404(Question, q_id)
    if request.method == 'POST':
        q.question       = request.form.get('question', '').strip()
        q.option1        = request.form.get('option1', '').strip()
        q.option2        = request.form.get('option2', '').strip()
        q.option3        = request.form.get('option3', '').strip()
        q.option4        = request.form.get('option4', '').strip()
        q.correct_option = int(request.form.get('correct_option', 1))
        db.session.commit()
        flash('Question updated.', 'success')
        return redirect(url_for('admin_questions', quiz_id=q.quiz_id))
    return render_template('admin/question_form.html', quiz=q.quiz, question=q)


@app.route('/admin/question/<int:q_id>/delete', methods=['POST'])
@admin_required
def admin_delete_question(q_id):
    q = db.get_or_404(Question, q_id)
    quiz_id = q.quiz_id
    db.session.delete(q)
    db.session.commit()
    flash('Question deleted.', 'success')
    return redirect(url_for('admin_questions', quiz_id=quiz_id))


# ---- User & Results Management ----

@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@app.route('/admin/results')
@admin_required
def admin_results():
    all_results = (
        db.session.query(Result, User, Quiz)
        .join(User, Result.user_id == User.id)
        .join(Quiz, Result.quiz_id == Quiz.id)
        .order_by(Result.taken_at.desc())
        .all()
    )
    return render_template('admin/results.html', all_results=all_results)


# ============================================================
#  Error Handlers
# ============================================================

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404


# ============================================================
#  Entry Point
# ============================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_sample_data()
    app.run(debug=True, port=5000)
