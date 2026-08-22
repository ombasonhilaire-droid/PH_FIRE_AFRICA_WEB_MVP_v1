import psycopg2
from psycopg2.extras import RealDictCursor
import sys
from io import StringIO
from flask_socketio import SocketIO, emit, join_room
import google.generativeai as genai
import time 
import os
import re
from datetime import datetime
from functools import wraps
from pathlib import Path
from flask import (
    Flask, g, redirect, render_template, request, session, url_for, flash,
    jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- CONSTANTES ---
APP_NAME = "PH FIRE AFRICA"
THEME_COLOR = "#ff2d8d"
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?\d{6,15}$")
socketio = SocketIO()

def utcnow_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def create_app() -> Flask:
    app = Flask(__name__)
    socketio.init_app(app, cors_allowed_origins="*")
    
    # --- CONFIGURATION ---
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB
    app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
    
    # PostgreSQL Configuration
    app.config["DB_HOST"] = os.getenv("DB_HOST", "localhost")
    app.config["DB_PORT"] = os.getenv("DB_PORT", "5432")
    app.config["DB_NAME"] = os.getenv("DB_NAME", "ph_fire_db")
    app.config["DB_USER"] = os.getenv("DB_USER", "ph_admin")
    app.config["DB_PASSWORD"] = os.getenv("DB_PASSWORD", "hilaire2026")
    
    # --- IA MWALIMU ---
    api_key_ia = os.getenv('PH_FIRE_AFRICA_KEY')
    model_ia = None
    if api_key_ia:
        try:
            genai.configure(api_key=api_key_ia)
            model_ia = genai.GenerativeModel('gemini-1.5-flash-latest') 
            print("✅ MWALIMU EST BRANCHÉ")
        except Exception as e:
            print(f"❌ Erreur IA : {e}")

    # --- DATABASE HELPERS (MAÎTRE) ---
    def db_conn():
        db = getattr(g, "db", None)
        if db is None:
            try:
                db = psycopg2.connect(
                    dbname=app.config["DB_NAME"],
                    user=app.config["DB_USER"],
                    password=app.config["DB_PASSWORD"],
                    host=app.config["DB_HOST"],
                    port=app.config["DB_PORT"],
                    cursor_factory=RealDictCursor
                )
                g.db = db
            except Exception as e:
                print(f"❌ ERREUR CONNEXION POSTGRES : {e}")
                raise e
        return db

    def db_one(sql, params=()):
        conn = db_conn()
        with conn.cursor() as cur:
            try:
                cur.execute(sql, params)
                res = cur.fetchone()
                conn.commit()
                return res
            except Exception as e:
                conn.rollback()
                print(f"❌ DB_ONE ERR: {e}")
                return None

    def db_all(sql, params=()):
        conn = db_conn()
        with conn.cursor() as cur:
            try:
                cur.execute(sql, params)
                res = cur.fetchall()
                conn.commit()
                return res
            except Exception as e:
                conn.rollback()
                print(f"❌ DB_ALL ERR: {e}")
                return []

    def db_execute(sql, params=()):
        conn = db_conn()
        with conn.cursor() as cur:
            try:
                cur.execute(sql, params)
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"❌ DB_EXECUTE ERR: {e}")
                raise e

    def current_user():
        uid = session.get("user_id")
        if not uid: return None
        return db_one("SELECT * FROM users WHERE id=%s", (uid,))

    # --- CONTEXT PROCESSOR ---
    @app.context_processor
    def inject_globals():
        me = current_user()
        unread_notifs = 0
        unread_msgs = 0
        if me:
            row_n = db_one("SELECT COUNT(*) AS c FROM notifications WHERE user_id=%s AND is_read=0", (me['id'],))
            unread_notifs = row_n['c'] if row_n else 0
            row_m = db_one("SELECT COUNT(*) AS c FROM messages WHERE recipient_id=%s AND is_read=0", (me['id'],))
            unread_msgs = row_m['c'] if row_m else 0
        return {"APP_NAME": APP_NAME, "me": me, "unread_notifications": unread_notifs, "unread_messages": unread_msgs}

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None: db.close()

    # --- AUTH ---
    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user():
                flash("Connecte-toi d'abord.", "warn")
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)
        return wrapped

    @app.get("/")
    def index():
        if current_user(): return redirect(url_for("feed"))
        return render_template("landing.html")

    @app.get("/signup")
    def signup(): return render_template("signup.html")

    @app.post("/signup")
    def signup_post():
        username = (request.form.get("username") or "").strip().lower()
        display_name = (request.form.get("display_name") or "").strip() or username
        identifier = (request.form.get("identifier") or "").strip()
        password = request.form.get("password") or ""

        if not USERNAME_RE.match(username) or len(password) < 6:
            flash("Données invalides.", "error")
            return redirect(url_for("signup"))

        pw_hash = generate_password_hash(password)
        try:    
            db_execute("INSERT INTO users(username, identifier, display_name, bio, password_hash, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                      (username, identifier, display_name, "", pw_hash, utcnow_iso()))
            user = db_one("SELECT id FROM users WHERE username = %s", (username,))
            session["user_id"] = user["id"]
            return redirect(url_for("feed"))
        except Exception as e:
            flash("Erreur : Pseudo ou Identifiant déjà pris.", "error")
            return redirect(url_for("signup"))

    @app.get("/login")
    def login(): return render_template("login.html", next=request.args.get("next") or "")

    @app.post("/login")
    def login_post():
        identifier = (request.form.get("identifier") or "").strip()
        password = request.form.get("password") or ""
        user = db_one("SELECT * FROM users WHERE identifier = %s OR username = %s", (identifier, identifier.lower()))
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("feed"))
        flash("Identifiants incorrects.", "error")
        return redirect(url_for("login"))

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    # --- FEED & POSTS ---
    @app.get("/feed")
    @login_required
    def feed():
        me = current_user()
        posts = get_feed_posts(me["id"])
        suggestions = get_suggestions(me["id"])
        return render_template("feed.html", posts=posts, suggestions=suggestions)

    @app.post("/post")
    @login_required
    def create_post():
        me = current_user()
        content = (request.form.get("content") or "").strip()
        file = request.files.get("image")
        image_filename = None
        if file and file.filename != '':
            ext = file.filename.rsplit('.', 1)[1].lower()
            image_filename = f"{me['id']}_{int(time.time())}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
        
        if content or image_filename:
            db_execute("INSERT INTO posts(user_id, content, image_filename, created_at) VALUES (%s, %s, %s, %s)",
                      (me['id'], content, image_filename, utcnow_iso()))
        return redirect(url_for("feed"))

    def get_feed_posts(user_id):
        query = """
        SELECT p.*, u.username, u.display_name, u.profile_pic,
               (SELECT COUNT(*) FROM likes WHERE post_id = p.id) AS like_count,
               (SELECT COUNT(*) FROM comments WHERE post_id = p.id) AS comment_count,
               COALESCE((SELECT 1 FROM likes WHERE user_id = %s AND post_id = p.id LIMIT 1), 0) AS liked_by_me
        FROM posts p JOIN users u ON u.id = p.user_id
        ORDER BY p.created_at DESC LIMIT 50"""
        return db_all(query, (user_id,))

    def get_suggestions(user_id):
        return db_all("""SELECT id, username, display_name, profile_pic FROM users 
                         WHERE id != %s AND id NOT IN (SELECT followed_id FROM follows WHERE follower_id = %s) 
                         ORDER BY created_at DESC LIMIT 5""", (user_id, user_id))

    # --- ACTIONS ---
    @app.post("/like/<int:post_id>")
    @login_required
    def toggle_like(post_id: int):
        me = current_user()
        liked = db_one("SELECT 1 FROM likes WHERE user_id = %s AND post_id = %s", (me["id"], post_id))
        if liked:
            db_execute("DELETE FROM likes WHERE user_id = %s AND post_id = %s", (me["id"], post_id))
        else:
            db_execute("INSERT INTO likes(user_id, post_id, created_at) VALUES (%s, %s, %s)", (me["id"], post_id, utcnow_iso()))
        return redirect(request.referrer or url_for("feed"))

    @app.get("/wallet")
    @login_required
    def wallet():
        me = current_user()
        w = db_one("SELECT * FROM wallets WHERE user_id=%s", (me['id'],))
        if not w:
            db_execute("INSERT INTO wallets (user_id) VALUES (%s)", (me['id'],))
            w = db_one("SELECT * FROM wallets WHERE user_id=%s", (me['id'],))
        return render_template("wallet.html", wallet=w)

    # --- MESSAGERIE & SOCKET ---
    @socketio.on('join')
    def on_join(data):
        me = current_user()
        room = f"chat_{min(me['id'], int(data['other_id']))}_{max(me['id'], int(data['other_id']))}"
        join_room(room)

    @socketio.on('send_msg')
    def handle_msg(data):
        me = current_user()
        db_execute("INSERT INTO messages (sender_id, recipient_id, content, created_at, is_read) VALUES (%s, %s, %s, %s, 0)",
                  (me['id'], data['recipient_id'], data['content'], utcnow_iso()))
        room = f"chat_{min(me['id'], int(data['recipient_id']))}_{max(me['id'], int(data['recipient_id']))}"
        emit('new_msg', {'content': data['content'], 'sender_id': me['id']}, room=room)

    # --- AUTO-SEED ---
    @app.before_request
    def _auto_seed():
        if not hasattr(g, 'seeded'):
            try:
                res = db_one("SELECT COUNT(*) as c FROM users")
                if res and res['c'] == 0:
                    pw = generate_password_hash("demo123")
                    db_execute("INSERT INTO users(username, identifier, display_name, password_hash, created_at) VALUES (%s, %s, %s, %s, %s)",
                              ("demo1", "demo1@pfa.com", "Demo 1", pw, utcnow_iso()))
                g.seeded = True
            except: pass

    return app

app = create_app()
if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)