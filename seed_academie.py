import sqlite3

conn = sqlite3.connect("instance/ph_fire_africa.db")
cur = conn.cursor()

# 1. Créer le Domaine
cur.execute("INSERT INTO domains (nom, description) VALUES (?, ?)", 
           ("Programmation Pure", "L'art de construire des systèmes robustes."))
domaine_id = cur.lastrowid

# 2. Créer le Curriculum
cur.execute("INSERT INTO curriculums (domain_id, titre, niveau, duree) VALUES (?, ?, ?, ?)",
           (domaine_id, "Maîtrise de Python Flask", "Ingénieur", 40))
cursus_id = cur.lastrowid

# 3. Créer le Module 1
cur.execute("INSERT INTO modules (curriculum_id, ordre, objectif) VALUES (?, ?, ?)",
           (cursus_id, 1, "Comprendre l'architecture Web"))
module_id = cur.lastrowid

# 4. Créer la Leçon 1
cur.execute("INSERT INTO lessons (module_id, titre, contenu) VALUES (?, ?, ?)",
           (module_id, "Introduction à la Souveraineté Numérique", 
            "Ici commence ton voyage de Bâtisseur..."))

conn.commit()
conn.close()
print("✅ Académie initialisée avec succès !")