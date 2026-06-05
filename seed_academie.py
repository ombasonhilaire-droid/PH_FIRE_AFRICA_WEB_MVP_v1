import psycopg2
from psycopg2.extras import RealDictCursor
import os

# Configuration PostgreSQL
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "ph_fire_db"),
    "user": os.getenv("DB_USER", "ph_admin"),
    "password": os.getenv("DB_PASSWORD", "hilaire2026"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

try:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("🔗 Connexion PostgreSQL établie ✅")

    # 1. Créer le Domaine
    cur.execute(
        "INSERT INTO domains (nom, description) VALUES (%s, %s) RETURNING id",
        ("Programmation Pure", "L'art de construire des systèmes robustes.")
    )
    domaine_id = cur.fetchone()['id']
    print(f"✅ Domaine créé: {domaine_id}")

    # 2. Créer le Curriculum
    cur.execute(
        "INSERT INTO curriculums (domain_id, titre, niveau, duree) VALUES (%s, %s, %s, %s) RETURNING id",
        (domaine_id, "Maîtrise de Python Flask", "Ingénieur", 40)
    )
    cursus_id = cur.fetchone()['id']
    print(f"✅ Curriculum créé: {cursus_id}")

    # 3. Créer le Module 1
    cur.execute(
        "INSERT INTO modules (curriculum_id, ordre, objectif) VALUES (%s, %s, %s) RETURNING id",
        (cursus_id, 1, "Comprendre l'architecture Web")
    )
    module_id = cur.fetchone()['id']
    print(f"✅ Module créé: {module_id}")

    # 4. Créer la Leçon 1
    cur.execute(
        "INSERT INTO lessons (module_id, titre, contenu) VALUES (%s, %s, %s) RETURNING id",
        (module_id, "Introduction à la Souveraineté Numérique", 
         "Ici commence ton voyage de Bâtisseur...")
    )
    lesson_id = cur.fetchone()['id']
    print(f"✅ Leçon créée: {lesson_id}")

    conn.commit()
    print("\n✅ Académie initialisée avec succès pour PostgreSQL!")

except psycopg2.Error as e:
    print(f"❌ Erreur PostgreSQL: {e}")
    conn.rollback()
except Exception as e:
    print(f"❌ Erreur: {e}")
finally:
    if conn:
        cur.close()
        conn.close()
        print("🔌 Connexion fermée")
