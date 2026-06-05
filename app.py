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

APP_NAME = "PH FIRE AFRICA"
THEME_COLOR = "#ff2d8d"  # rose par défaut

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+\d{6,15}$")
socketio = SocketIO()


def utcnow_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def create_app() -> Flask:
    app = Flask(__name__)
    socketio.init_app(app, cors_allowed_origins="*")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB upload max
    app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
    
    # PostgreSQL Configuration
    app.config["DB_HOST"] = os.getenv("DB_HOST", "localhost")
    app.config["DB_PORT"] = os.getenv("DB_PORT", "5432")
    app.config["DB_NAME"] = os.getenv("DB_NAME", "ph_fire_db")
    app.config["DB_USER"] = os.getenv("DB_USER", "ph_admin")
    app.config["DB_PASSWORD"] = os.getenv("DB_PASSWORD", "hilaire2026")
    
    # --- CONFIGURATION MWALIMU : SOLUTION FINALE ---
    api_key_ia = os.getenv('PH_FIRE_AFRICA_KEY')
    model_ia = None

    if api_key_ia:
        try:
            genai.configure(api_key=api_key_ia)
            model_ia = genai.GenerativeModel('gemini-1.5-flash-latest') 
            print("✅ MWALIMU EST BRANCHÉ SUR LE MODÈLE FLASH LATEST")
        except Exception as e:
            print(f"❌ Erreur d'allumage : {e}")

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.context_processor
    def inject_globals():
        me = current_user()
        unread_notifs = 0
        unread_msgs = 0
        
        if me:
            # 1. Compter les notifications non lues
            row_n = db_one("SELECT COUNT(*) AS c FROM notifications WHERE user_id=%s AND is_read=FALSE", (me['id'],))
            unread_notifs = row_n['c'] if row_n else 0
            
            # 2. Compter les messages privés non lus
            row_m = db_one("SELECT COUNT(*) AS c FROM messages WHERE recipient_id=%s AND is_read=FALSE", (me['id'],))
            unread_msgs = row_m['c'] if row_m else 0
            
        return {
            "APP_NAME": APP_NAME,
            "me": me,
            "unread_notifications": unread_notifs,
            "unread_messages": unread_msgs
        }
    # ---------- AUTH ----------

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
        if current_user():
            return redirect(url_for("feed"))
        return render_template("landing.html")

    @app.get("/signup")
    def signup():
        return render_template("signup.html")

    @app.post("/signup")
    def signup_post():
        username = (request.form.get("username") or"").strip()
        display_name = (request.form.get("display_name") or "").strip() or username
        identifier = (request.form.get("identifier") or "").strip()
        password = request.form.get("password") or ""

        if not USERNAME_RE.match(username):
            flash("Nom d'utilisateur invalide (3–20 caractères, lettres/chiffres/_).", "error")
            return redirect(url_for("signup"))
        if not (EMAIL_RE.match(identifier) or PHONE_RE.match(identifier)):
            flash("Entre un email ou un numéro de téléphone (ex: +243...).", "error")
            return redirect(url_for("signup"))
        if len(password) < 6:
            flash("Mot de passe trop court (min 6).", "error")
            return redirect(url_for("signup"))

        pw_hash = generate_password_hash(password)
        try:    
            db_execute("""INSERT INTO users(username, identifier, display_name, bio, password_hash, created_at) 
                         VALUES (%s, %s, %s, %s, %s, %s)""",
                      (username.lower(), identifier, display_name, "", pw_hash, utcnow_iso()))
        except Exception as e:
            print(f"❌ ERREUR INSCRIPTION : {e}")
            flash("Ce nom d'utilisateur ou cet identifiant existe déjà.", "error")
            return redirect(url_for("signup"))

        user = db_one("SELECT * FROM users WHERE username = %s", (username.lower(),))
        session["user_id"] = user["id"]
        flash("Bienvenue sur PH FIRE AFRICA !", "ok")
        return redirect(url_for("feed"))

    @app.get("/login")
    def login():
        return render_template("login.html", next=request.args.get("next") or "")

    @app.post("/login")
    def login_post():
        identifier = (request.form.get("identifier") or "").strip()
        password = request.form.get("password") or ""
        next_url = (request.form.get("next") or "").strip() or url_for("feed")
    
        user = db_one("SELECT * FROM users WHERE identifier = %s OR username = %s", (identifier, identifier.lower()))
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Identifiant ou mot de passe incorrect.", "error")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        flash("Connexion réussie.", "ok")
        return redirect(next_url)

    @app.get("/logout")
    def logout():
        session.clear()
        flash("Déconnecté.", "ok")
        return redirect(url_for("index"))
    
    #========GUIDE D'UTILISATION RAPIDE========
    @app.get("/guide")
    @login_required
    def guide_utilisation():
        return render_template("guide.html")
    
    # =============A PROPOS DE LA PLATEFORME=========
    @app.get("/a-propos")
    def a_propos():
        return render_template("about.html")
    # ---------- FEED / POSTS ----------

    @app.get("/feed")
    @login_required
    def feed():
        me = current_user()
        posts = get_feed_posts(me["id"])
        suggestions = get_suggestions(me["id"])
        return render_template("feed.html", posts=posts, suggestions=suggestions, me=me)

    @app.get("/explore")
    @login_required
    def explore():
        posts = get_explore_posts()
        return render_template("explore.html", posts=posts)
    
    @app.post("/post")
    @login_required
    def create_post():
        me = current_user()
        content = (request.form.get("content") or "").strip()
        image_filename = None
        file = request.files.get("image")
        
        if file and file.filename != '':
            ext = file.filename.rsplit('.', 1)[1].lower()
            if ext in ['jpg', 'jpeg', 'png', 'gif', 'mp4', 'mov', 'avi']:
                image_filename = f"{me['id']}_{int(time.time())}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
        
        if content or image_filename:
            db_execute("""INSERT INTO posts(user_id, content, image_filename, created_at) 
                         VALUES (%s, %s, %s, %s)""",
                      (me['id'], content, image_filename, utcnow_iso()))
            flash("Publication réussie ! 🚀", "ok")
        return redirect(url_for("feed"))

    # --- ACADÉMIE : ACCUEIL ---
    @app.get("/academie")
    @login_required
    def academie_home():
        domaines = db_all("SELECT * FROM domains")
        return render_template("academie/home.html", domaines=domaines)
    
    @app.route("/academie/editeur", methods=["GET", "POST"])
    @app.route("/academie/editeur/<int:l_id>", methods=["GET", "POST"])
    @login_required
    def editeur_lecon(l_id=None):
        me = current_user()
        if me['username'] != 'frere': 
            return redirect(url_for('feed'))

        lecon = db_one("SELECT * FROM lessons WHERE id=%s", (l_id,)) if l_id else None

        if request.method == "POST":
            titre = request.form.get("titre")
            module_id = request.form.get("module_id")
            contenu = request.form.get("contenu")
            
            img_name = lecon['image_filename'] if lecon else None
            vid_name = lecon['video_filename'] if lecon else None
            
            f_img = request.files.get("lesson_image")
            if f_img and f_img.filename != '':
                img_name = f"lecon_img_{int(time.time())}.jpg"
                f_img.save(os.path.join(app.config['UPLOAD_FOLDER'], img_name))

            f_vid = request.files.get("lesson_video")
            if f_vid and f_vid.filename != '':
                vid_name = f"lecon_vid_{int(time.time())}.mp4"
                f_vid.save(os.path.join(app.config['UPLOAD_FOLDER'], vid_name))

            if l_id:
                db_execute("""UPDATE lessons SET titre=%s, module_id=%s, contenu=%s, 
                             image_filename=%s, video_filename=%s WHERE id=%s""", 
                           (titre, module_id, contenu, img_name, vid_name, l_id))
            else:
                db_execute("""INSERT INTO lessons (titre, module_id, contenu, image_filename, 
                             video_filename, exercice_obligatoire) VALUES (%s, %s, %s, %s, %s, TRUE)""", 
                           (titre, module_id, contenu, img_name, vid_name))
            
            return redirect(url_for('academie_home'))

        modules = db_all("""SELECT m.id, m.objectif, c.titre as cursus FROM modules m 
                           JOIN curriculums c ON m.curriculum_id = c.id""")
        return render_template("academie/forge_lecon.html", lecon=lecon, modules=modules)

    @app.get("/academie/domaine/<int:d_id>")
    @login_required
    def academie_domaine(d_id):
        domaine = db_one("SELECT * FROM domains WHERE id=%s", (d_id,))
        cursus = db_all("SELECT * FROM curriculums WHERE domain_id=%s", (d_id,))
        return render_template("academie/domaine.html", domaine=domaine, cursus=cursus)

    @app.get("/academie/cursus/<int:c_id>")
    @login_required
    def academie_cursus(c_id):
        cursus = db_one("SELECT * FROM curriculums WHERE id=%s", (c_id,))
        modules = db_all("SELECT * FROM modules WHERE curriculum_id=%s ORDER BY ordre ASC", (c_id,))
        structure = []
        for m in modules:
            lecons = db_all("SELECT id, titre FROM lessons WHERE module_id=%s ORDER BY id ASC", (m['id'],))
            structure.append({'module': m, 'lecons': lecons})
        
        return render_template("academie/cursus.html", cursus=cursus, structure=structure)

    @app.get("/academie/lecon/<int:l_id>")
    @login_required
    def academie_lecon(l_id):
        lecon = db_one("""
            SELECT l.*, m.curriculum_id, c.titre as cursus_titre, d.nom as domaine_nom 
            FROM lessons l 
            JOIN modules m ON l.module_id = m.id 
            JOIN curriculums c ON m.curriculum_id = c.id
            JOIN domains d ON c.domain_id = d.id
            WHERE l.id=%s""", (l_id,))
        return render_template("academie/lecon_view.html", lecon=lecon)

    @app.post("/academie/supprimer/<int:l_id>")
    @login_required
    def supprimer_lecon(l_id):
        me = current_user()
        if me['username'] != 'frere': 
            return redirect(url_for('feed'))
        db_execute("DELETE FROM lessons WHERE id=%s", (l_id,))
        flash("Brique de savoir retirée avec succès. 🗑️", "ok")
        return redirect(url_for('academie_home'))

    @app.route("/academie/branches", methods=["GET", "POST"])
    @app.route("/academie/branches/<int:c_id>", methods=["GET", "POST"])
    @login_required
    def forge_branches(c_id=None):
        me = current_user()
        if me['username'] != 'frere':
            flash("Accès réservé à l'Architecte.", "error")
            return redirect(url_for('feed'))

        curriculum = None
        if c_id:
            curriculum = db_one("SELECT * FROM curriculums WHERE id=%s", (c_id,))

        if request.method == "POST":
            titre = request.form.get("titre")
            domain_id = request.form.get("domain_id")
            niveau = request.form.get("niveau")
            duree = request.form.get("duree")

            if c_id:
                db_execute("""UPDATE curriculums SET titre=%s, domain_id=%s, niveau=%s, duree=%s 
                             WHERE id=%s""", 
                           (titre, domain_id, niveau, duree, c_id))
                flash(f"Branche '{titre}' mise à jour ! 🌿", "ok")
            else:
                db_execute("""INSERT INTO curriculums (titre, domain_id, niveau, duree) 
                             VALUES (%s, %s, %s, %s)""", 
                           (titre, domain_id, niveau, duree))
                flash(f"Nouvelle branche '{titre}' plantée dans l'Académie ! 🌱", "ok")
            
            return redirect(url_for('academie_home'))

        domaines = db_all("SELECT * FROM domains")
        return render_template("academie/forge_branches.html", curriculum=curriculum, domaines=domaines)

    @app.post("/like/<int:post_id>")
    @login_required
    def toggle_like(post_id: int):
        me = current_user()
        liked = db_one("SELECT 1 FROM likes WHERE user_id = %s AND post_id = %s", (me["id"], post_id))
        post = db_one("SELECT * FROM posts WHERE id = %s", (post_id,))
    
        if not post:
            return ("Non trouvé", 404)

        if liked:
            db_execute("DELETE FROM likes WHERE user_id = %s AND post_id = %s", (me["id"], post_id))
        else:
            db_execute("INSERT INTO likes(user_id, post_id, created_at) VALUES (%s, %s, %s)",
                      (me["id"], post_id, utcnow_iso()))
        return redirect(request.referrer or url_for("feed"))

    @app.post("/comment/<int:post_id>")
    @login_required
    def add_comment(post_id: int):
        me = current_user()
        content = (request.form.get("content") or "").strip()
        if not content:
            flash("Commentaire vide.", "warn")
            return redirect(request.referrer or url_for("feed"))
        if len(content) > 300:
            flash("Commentaire trop long (max 300).", "error")
            return redirect(request.referrer or url_for("feed"))

        post = db_one("SELECT * FROM posts WHERE id=%s", (post_id,))
        if not post:
            return ("Not found", 404)

        db_execute("""INSERT INTO comments(post_id, user_id, content, created_at) 
                     VALUES (%s, %s, %s, %s)""",
                  (post_id, me["id"], content, utcnow_iso()))
        if post["user_id"] != me["id"]:
            create_notification(user_id=post["user_id"], actor_id=me["id"], ntype="comment", post_id=post_id)

        flash("Commentaire envoyé.", "ok")
        return redirect(request.referrer or url_for("feed"))

    @app.get("/rechercher")
    @login_required
    def rechercher():
        q = request.args.get('q', '').strip()
        resultats = db_all("""SELECT id, username, display_name, profile_pic FROM users 
                             WHERE username ILIKE %s OR display_name ILIKE %s""", 
                           ('%'+q+'%', '%'+q+'%'))
        return render_template('recherche.html', resultats=resultats, mot_cle=q)

    @app.get("/savoir")
    @login_required
    def savoir():
        articles = db_all("""SELECT k.*, u.display_name FROM knowledge k 
                            JOIN users u ON u.id = k.author_id ORDER BY k.created_at DESC""")
        profs = db_all("""SELECT DISTINCT u.id, u.display_name, u.profile_pic FROM users u 
                         JOIN knowledge k ON k.author_id = u.id""")
        return render_template("savoir.html", articles=articles, profs=profs)

    @app.get("/lecon/<int:k_id>")
    @login_required
    def lecon(k_id):
        article = db_one("""SELECT k.*, u.display_name FROM knowledge k 
                           JOIN users u ON u.id = k.author_id WHERE k.id=%s""", (k_id,))
        return render_template("lecon.html", article=article)

    @app.get("/wallet")
    @login_required
    def wallet():
        me = current_user()
        w = db_one("SELECT * FROM wallets WHERE user_id=%s", (me['id'],))
        if not w:
            db_execute("INSERT INTO wallets (user_id) VALUES (%s)", (me['id'],))
            w = db_one("SELECT * FROM wallets WHERE user_id=%s", (me['id'],))
        return render_template("wallet.html", wallet=w)

    @app.post("/api/mine/heartbeat/<int:l_id>")
    @login_required
    def mine_heartbeat(l_id):
        me = current_user()
        gain = 0.0010
        
        db_execute("UPDATE wallets SET total_earnings = total_earnings + %s WHERE user_id = %s", 
                   (gain, me['id']))
        db_execute("UPDATE wallets SET watch_time = watch_time + 30 WHERE user_id = %s", 
                   (me['id'],))

        return jsonify({"status": "mining", "earned": gain})

    @app.get("/tuteur")
    @login_required
    def tuteur_view():
        return render_template("ia_tuteur.html")

    @app.post("/ask-ia")
    @login_required
    def ask_ia():
        if not model_ia:
            return jsonify({"response": "Mwalimu attend les instructions du Fondateur."})
        
        data = request.get_json()
        prompt = data.get("prompt")
        
        try:
            response = model_ia.generate_content(prompt)
            if response and response.text:
                return jsonify({"response": response.text})
            else:
                return jsonify({"response": "Mwalimu est en train de réfléchir. Réessaie dans 10 secondes."})
        except Exception as e:
            print(f"ERREUR CAPTURÉE : {e}")
            try:
                backup = genai.GenerativeModel('gemini-1.5-flash')
                res = backup.generate_content(prompt)
                return jsonify({"response": res.text})
            except:
                return jsonify({"response": "Le portail vers Google est encombré. Vérifie ton internet et réessaie."})

    @socketio.on('send_msg')
    def handle_msg(data):
        me = current_user()
        recipient_id = data['recipient_id']
        content = data['content']
        
        db_execute("""INSERT INTO messages (sender_id, recipient_id, content, created_at, is_read) 
                     VALUES (%s, %s, %s, %s, FALSE)""",
                  (me['id'], recipient_id, content, utcnow_iso()))
        
        room = f"chat_{min(me['id'], int(recipient_id))}_{max(me['id'], int(recipient_id))}"
        emit('new_msg', {
            'content': content,
            'sender_id': me['id'],
            'display_name': me['display_name']
        }, room=room)

    @socketio.on('join')
    def on_join(data):
        me = current_user()
        other_id = int(data['other_id'])
        room = f"chat_{min(me['id'], other_id)}_{max(me['id'], other_id)}"
        join_room(room)

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        me = current_user()
        if request.method == "POST":
            display_name = request.form.get("display_name", me['display_name']).strip()
            bio = request.form.get("bio", me['bio']).strip()
            language = request.form.get("language", me['language'])
            privacy = request.form.get("privacy_level", me['privacy_level'])
            video_pref = request.form.get("video_pref", me['video_pref'])
            
            filename_p = me['profile_pic']
            filename_c = me['cover_pic']

            if 'profile_pic' in request.files:
                f_p = request.files['profile_pic']
                if f_p.filename != '':
                    ext = f_p.filename.rsplit('.', 1)[1].lower()
                    filename_p = f"avatar_{me['id']}_{int(time.time())}.{ext}"
                    f_p.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_p))

            if 'cover_pic' in request.files:
                f_c = request.files['cover_pic']
                if f_c.filename != '':
                    ext = f_c.filename.rsplit('.', 1)[1].lower()
                    filename_c = f"cover_{me['id']}_{int(time.time())}.{ext}"
                    f_c.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_c))

            db_execute("""UPDATE users SET 
                          display_name=%s, bio=%s, profile_pic=%s, cover_pic=%s, 
                          language=%s, privacy_level=%s, video_pref=%s 
                          WHERE id=%s""", 
                       (display_name, bio, filename_p, filename_c, 
                        language, privacy, video_pref, me['id']))
            
            flash("Paramètres enregistrés ! ⚙️", "ok")
            return redirect(url_for("settings"))

        return render_template("settings.html", user=me)

    @app.get("/u/<username>")
    @login_required
    def profile(username: str):
        user = db_one("SELECT * FROM users WHERE username=%s", (username.lower(),))
        if not user:
            return ("Not found", 404)

        me = current_user()
        is_me = (me["id"] == user["id"])
        is_following = bool(db_one("SELECT 1 FROM follows WHERE follower_id=%s AND followed_id=%s",
                                   (me["id"], user["id"]))) if not is_me else False

        stats = {
            "posts": db_one("SELECT COUNT(*) AS c FROM posts WHERE user_id=%s", (user["id"],))["c"],
            "followers": db_one("SELECT COUNT(*) AS c FROM follows WHERE followed_id=%s", (user["id"],))["c"],
            "following": db_one("SELECT COUNT(*) AS c FROM follows WHERE follower_id=%s", (user["id"],))["c"],
        }
        posts = db_all("""
            SELECT p.*, u.username, u.display_name, 
            (SELECT COUNT(*) FROM likes WHERE post_id=p.id) AS like_count, 
            (SELECT COUNT(*) FROM comments WHERE post_id=p.id) AS comment_count, 
            (SELECT 1 FROM likes WHERE user_id=%s AND post_id=p.id) AS liked_by_me 
            FROM posts p JOIN users u ON u.id=p.user_id 
            WHERE p.user_id=%s ORDER BY p.created_at DESC LIMIT 50""",
            (me["id"], user["id"]))

        return render_template("profile.html", user=user, stats=stats, posts=posts, is_me=is_me, is_following=is_following)

    @app.post("/follow/<username>")
    @login_required
    def toggle_follow(username: str):
        me = current_user()
        other = db_one("SELECT * FROM users WHERE username=%s", (username.lower(),))
        if not other or other["id"] == me["id"]:
            return redirect(request.referrer or url_for("feed"))

        exists = db_one("SELECT 1 FROM follows WHERE follower_id=%s AND followed_id=%s",
                        (me["id"], other["id"]))
        if exists:
            db_execute("DELETE FROM follows WHERE follower_id=%s AND followed_id=%s", (me["id"], other["id"]))
        else:
            db_execute("""INSERT INTO follows(follower_id, followed_id, created_at) 
                         VALUES (%s, %s, %s)""",
                       (me["id"], other["id"], utcnow_iso()))
            create_notification(user_id=other["id"], actor_id=me["id"], ntype="follow", post_id=None)

        return redirect(request.referrer or url_for("profile", username=other["username"]))

    @app.get("/messages")
    @login_required
    def messages():
        me = current_user()
        threads = get_message_threads(me["id"])
        return render_template("messages.html", threads=threads)

    @app.route("/messages/<username>", methods=["GET", "POST"])
    @login_required
    def thread(username: str):
        me = current_user()
        other = db_one("SELECT * FROM users WHERE username=%s", (username.lower(),))
        if not other or other["id"] == me["id"]:
            return redirect(url_for("messages"))

        if request.method == "POST":
            content = (request.form.get("content") or "").strip()
            if content:
                db_execute("""INSERT INTO messages(sender_id, recipient_id, content, created_at, is_read) 
                             VALUES (%s, %s, %s, %s, FALSE)""",
                          (me["id"], other["id"], content[:1000], utcnow_iso()))
                flash("Message envoyé.", "ok")
            return redirect(url_for("thread", username=other["username"]))

        db_execute("UPDATE messages SET is_read=TRUE WHERE sender_id=%s AND recipient_id=%s",
                   (other["id"], me["id"]))

        msgs = db_all("""
            SELECT m.*, su.username AS sender_username, su.display_name AS sender_display_name, 
            ru.username AS recipient_username, ru.display_name AS recipient_display_name 
            FROM messages m 
            JOIN users su ON su.id=m.sender_id 
            JOIN users ru ON ru.id=m.recipient_id 
            WHERE (m.sender_id=%s AND m.recipient_id=%s) OR (m.sender_id=%s AND m.recipient_id=%s) 
            ORDER BY m.created_at ASC LIMIT 200""",
            (me["id"], other["id"], other["id"], me["id"]))
        return render_template("thread.html", other=other, messages=msgs)

    @app.get("/notifications")
    @login_required
    def notifications():
        me = current_user()
        rows = db_all("""
            SELECT n.*, a.username AS actor_username, a.display_name AS actor_display_name, 
            p.content AS post_content 
            FROM notifications n 
            JOIN users a ON a.id=n.actor_id 
            LEFT JOIN posts p ON p.id=n.post_id 
            WHERE n.user_id=%s ORDER BY n.created_at DESC LIMIT 100""",
            (me["id"],))
        return render_template("notifications.html", notifications=rows)

    @app.post("/notifications/read_all")
    @login_required
    def notifications_read_all():
        me = current_user()
        db_execute("UPDATE notifications SET is_read=TRUE WHERE user_id=%s", (me["id"],))
        return redirect(url_for("notifications"))

    @app.get("/api/me")
    def api_me():
        me = current_user()
        if not me:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return jsonify({"ok": True, "me": dict(me)})

    @app.get("/api/posts")
    def api_posts():
        limit = min(int(request.args.get("limit", 20)), 50)
        rows = db_all("""
            SELECT p.*, u.username, u.display_name, 
            (SELECT COUNT(*) FROM likes WHERE post_id=p.id) AS like_count, 
            (SELECT COUNT(*) FROM comments WHERE post_id=p.id) AS comment_count 
            FROM posts p JOIN users u ON u.id=p.user_id 
            ORDER BY p.created_at DESC LIMIT %s""",
            (limit,))
        return jsonify({"ok": True, "posts": [dict(r) for r in rows]})

    @app.get("/registre")
    @login_required
    def registre():
        me = current_user()
        if me['username'] != 'frere': 
            flash("Accès refusé. Seul le Fondateur peut consulter le Registre National.", "error")
            return redirect(url_for('feed'))

        batisseurs = db_all("""SELECT u.*, w.total_earnings FROM users u 
                              LEFT JOIN wallets w ON u.id = w.user_id ORDER BY u.created_at DESC""")
        res_mine = db_one("SELECT SUM(total_earnings) as total FROM wallets")
        mine_totale = res_mine['total'] if res_mine['total'] else 0
        taxe_totale = mine_totale * 0.10
        
        return render_template("registre.html", batisseurs=batisseurs, mine_totale=mine_totale, taxe_totale=taxe_totale)

    def repartir_richesse(montant_total, createur_id, apprenant_id):
        parts = {
            'createur': 0.60,
            'apprenant': 0.10,
            'plateforme': 0.15,
            'taxe': 0.10,
            'depannage': 0.05
        }

        val_createur = montant_total * parts['createur']
        val_apprenant = montant_total * parts['apprenant']
        val_plateforme = montant_total * parts['plateforme']
        val_taxe = montant_total * parts['taxe']
        val_depannage = montant_total * parts['depannage']

        db_execute("UPDATE wallets SET total_earnings = total_earnings + %s WHERE user_id = %s", 
                   (val_createur, createur_id))
        db_execute("UPDATE wallets SET total_earnings = total_earnings + %s WHERE user_id = %s", 
                   (val_apprenant, apprenant_id))
        db_execute("UPDATE wallets SET total_earnings = total_earnings + %s WHERE user_id = 1", 
                   (val_plateforme,))
        db_execute("""INSERT INTO pfa_registry (transaction_type, amount, category, created_at) 
                     VALUES (%s, %s, %s, %s)""", 
                   ('EXTRACTION', montant_total, 'PARTAGE_GLOBAL', utcnow_iso()))
        return True

    @app.post("/api/validate_lesson/<int:l_id>")
    @login_required
    def validate_lesson(l_id):
        me = current_user()
        success = True 

        if success:
            db_execute("""INSERT INTO student_progress (student_id, lesson_id, statut) 
                         VALUES (%s, %s, 'VALIDE')""", (me['id'], l_id))
            repartir_richesse(1.0, createur_id=1, apprenant_id=me['id'])
            flash("Félicitations ! Leçon validée et Mine d'Or créditée. 💰", "ok")
            return jsonify({"status": "success", "next_url": url_for('academie_home')})
    
        return jsonify({"status": "error", "message": "Discipline insuffisante. Réessaie !"})

    @app.post("/api/run_code")
    @login_required
    def run_code():
        code = request.json.get("code")
        old_stdout = sys.stdout
        redirected_output = sys.stdout = StringIO()
    
        try:
            exec(code)
            result = redirected_output.getvalue()
        except Exception as e:
            result = str(e)
        finally:
            sys.stdout = old_stdout
        
        return jsonify({"output": result})

    # ---------- HELPERS ----------
    
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
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            res = cur.fetchone()
            conn.commit()
            return res
        except Exception as e:
            conn.rollback()
            print(f"❌ ERREUR DB_ONE: {e}")
            return None
        finally:
            cur.close()

    def db_all(sql, params=()):
        conn = db_conn()
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            res = cur.fetchall()
            conn.commit()
            return res
        except Exception as e:
            conn.rollback()
            print(f"❌ ERREUR DB_ALL: {e}")
            return []
        finally:
            cur.close()

    def db_execute(sql, params=()):
        conn = db_conn()
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"❌ ERREUR DB_EXECUTE: {e}")
            raise e
        finally:
            cur.close()

    def current_user():
        uid = session.get("user_id")
        if not uid: 
            return None
        return db_one("SELECT * FROM users WHERE id=%s", (uid,))
    
    def create_notification(user_id: int, actor_id: int, ntype: str, post_id):
        if user_id == actor_id:
            return
        db_execute("""INSERT INTO notifications(user_id, actor_id, ntype, post_id, created_at, is_read) 
                     VALUES (%s, %s, %s, %s, %s, FALSE)""",
                  (user_id, actor_id, ntype, post_id, utcnow_iso()))

    def count_unread_notifications() -> int:
        me = current_user()
        if not me:
            return 0
        row = db_one("SELECT COUNT(*) AS c FROM notifications WHERE user_id=%s AND is_read=FALSE", (me["id"],))
        return int(row["c"] or 0)

    def get_feed_posts(user_id):
        query = """
        SELECT 
            p.*, u.username, u.display_name, u.profile_pic,
            (SELECT COUNT(*) FROM likes WHERE post_id = p.id) AS like_count,
            (SELECT COUNT(*) FROM comments WHERE post_id = p.id) AS comment_count,
            COALESCE((SELECT 1 FROM likes WHERE user_id = %s AND post_id = p.id LIMIT 1), 0) AS liked_by_me
        FROM posts p
        JOIN users u ON u.id = p.user_id
        ORDER BY p.created_at DESC 
        LIMIT 50"""
        return db_all(query, (user_id,))

    def get_explore_posts():
        me = current_user()
        my_id = me["id"]
        return db_all("""
            SELECT p.*, u.username, u.display_name, 
            (SELECT COUNT(*) FROM likes WHERE post_id=p.id) AS like_count, 
            (SELECT COUNT(*) FROM comments WHERE post_id=p.id) AS comment_count, 
            (SELECT 1 FROM likes WHERE user_id=%s AND post_id=p.id) AS liked_by_me 
            FROM posts p JOIN users u ON u.id=p.user_id 
            ORDER BY p.created_at DESC LIMIT 80""",
            (my_id,))

    def get_suggestions(user_id):
        query = """
        SELECT id, username, display_name, profile_pic FROM users 
        WHERE id != %s 
        AND id NOT IN (SELECT followed_id FROM follows WHERE follower_id = %s) 
        ORDER BY created_at DESC LIMIT 5"""
        return db_all(query, (user_id, user_id))

    def get_message_threads(user_id):
        query = """
        SELECT 
            u.id, u.username, u.display_name, u.profile_pic,
            m.content as last_msg, m.created_at,
            (SELECT COUNT(*) FROM messages WHERE sender_id = u.id AND recipient_id = %s AND is_read = FALSE) as unread_count
        FROM users u
        JOIN messages m ON (m.sender_id = u.id AND m.recipient_id = %s) 
                        OR (m.sender_id = %s AND m.recipient_id = u.id)
        WHERE u.id != %s
        GROUP BY u.id, m.content, m.created_at
        ORDER BY m.created_at DESC
        """
        return db_all(query, (user_id, user_id, user_id, user_id))

    def seed_demo():
        existing = db_one("SELECT COUNT(*) AS c FROM users")
        if existing and int(existing['c']) > 0:
            return

        demo_users = [
            ("demo1", "demo1@phfire.africa", "Demo 1"),
            ("demo2", "demo2@phfire.africa", "Demo 2"),
        ]

        for username, identifier, display_name in demo_users:
            try:
                db_execute("""INSERT INTO users(username, identifier, display_name, bio, password_hash, created_at) 
                             VALUES (%s, %s, %s, %s, %s, %s)""",
                          (username, identifier, display_name, "Compte démo.", generate_password_hash("demo123"), utcnow_iso()))
            except Exception as e:
                print(f"ℹ️ Info : Le compte {username} existe déjà ou erreur mineure.")
                pass

        u1 = db_one("SELECT * FROM users WHERE username = %s", ('demo1',))
        u2 = db_one("SELECT * FROM users WHERE username = %s", ('demo2',))
        
        if not u1 or not u2:
            return

    @app.before_request
    def _auto_seed_once():
        try:
            c = db_one("SELECT COUNT(*) AS c FROM users", ())["c"]
            if int(c) == 0:
                seed_demo()
        except Exception:
            pass
            
    return app

app = create_app()

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
