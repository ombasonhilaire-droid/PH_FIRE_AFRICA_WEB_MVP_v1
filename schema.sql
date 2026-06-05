-- ============================================
-- PH FIRE AFRICA - SCHEMA POSTGRESQL
-- Conçu pour supporter MILLIONS de bâtisseurs
-- ============================================

-- Extensions PostgreSQL
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- TABLE: USERS (Bâtisseurs)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    identifier VARCHAR(255) UNIQUE NOT NULL,  -- Email ou téléphone
    display_name VARCHAR(255) NOT NULL,
    bio TEXT DEFAULT '',
    profile_pic VARCHAR(255),
    cover_pic VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    language VARCHAR(10) DEFAULT 'fr',
    privacy_level VARCHAR(20) DEFAULT 'public',
    video_pref VARCHAR(20) DEFAULT 'HD',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_identifier ON users(identifier);
CREATE INDEX idx_users_created_at ON users(created_at);

-- ============================================
-- TABLE: FOLLOWS (Relations)
-- ============================================
CREATE TABLE IF NOT EXISTS follows (
    follower_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    followed_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, followed_id),
    CHECK (follower_id != followed_id)
);

CREATE INDEX idx_follows_followed_id ON follows(followed_id);

-- ============================================
-- TABLE: POSTS (Publications)
-- ============================================
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    image_filename VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_created_at ON posts(created_at DESC);

-- ============================================
-- TABLE: LIKES (Réactions)
-- ============================================
CREATE TABLE IF NOT EXISTS likes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, post_id)
);

CREATE INDEX idx_likes_post_id ON likes(post_id);

-- ============================================
-- TABLE: COMMENTS (Commentaires)
-- ============================================
CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_comments_post_id ON comments(post_id);
CREATE INDEX idx_comments_user_id ON comments(user_id);

-- ============================================
-- TABLE: MESSAGES (Messagerie instantanée)
-- ============================================
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_messages_recipient_id ON messages(recipient_id);
CREATE INDEX idx_messages_sender_id ON messages(sender_id);
CREATE INDEX idx_messages_is_read ON messages(recipient_id, is_read);

-- ============================================
-- TABLE: NOTIFICATIONS (Notifications)
-- ============================================
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    actor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ntype VARCHAR(50) NOT NULL,  -- 'like', 'comment', 'follow', etc.
    post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notifications_user ON notifications(user_id, is_read, created_at DESC);
CREATE INDEX idx_notifications_actor ON notifications(actor_id);

-- ============================================
-- TABLE: ACADÉMIE - DOMAINS (Domaines)
-- ============================================
CREATE TABLE IF NOT EXISTS domains (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- TABLE: ACADÉMIE - CURRICULUMS (Branches)
-- ============================================
CREATE TABLE IF NOT EXISTS curriculums (
    id SERIAL PRIMARY KEY,
    domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    titre VARCHAR(255) NOT NULL,
    niveau VARCHAR(50),  -- 'Débutant', 'Intermédiaire', 'Ingénieur', etc.
    duree INTEGER,  -- Durée en heures
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_curriculums_domain_id ON curriculums(domain_id);

-- ============================================
-- TABLE: ACADÉMIE - MODULES (Modules)
-- ============================================
CREATE TABLE IF NOT EXISTS modules (
    id SERIAL PRIMARY KEY,
    curriculum_id INTEGER NOT NULL REFERENCES curriculums(id) ON DELETE CASCADE,
    ordre INTEGER DEFAULT 1,
    objectif TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_modules_curriculum_id ON modules(curriculum_id);

-- ============================================
-- TABLE: ACADÉMIE - LESSONS (Leçons)
-- ============================================
CREATE TABLE IF NOT EXISTS lessons (
    id SERIAL PRIMARY KEY,
    module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    titre VARCHAR(255) NOT NULL,
    contenu TEXT,
    image_filename VARCHAR(255),
    video_filename VARCHAR(255),
    exercice_obligatoire BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_lessons_module_id ON lessons(module_id);

-- ============================================
-- TABLE: ACADÉMIE - STUDENT PROGRESS (Progression)
-- ============================================
CREATE TABLE IF NOT EXISTS student_progress (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    statut VARCHAR(50) DEFAULT 'EN_COURS',  -- 'EN_COURS', 'VALIDE', 'ECHEC'
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, lesson_id)
);

CREATE INDEX idx_progress_student ON student_progress(student_id);
CREATE INDEX idx_progress_lesson ON student_progress(lesson_id);

-- ============================================
-- TABLE: WALLETS (Portefeuilles - Mine d'Or)
-- ============================================
CREATE TABLE IF NOT EXISTS wallets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    total_earnings DECIMAL(15, 4) DEFAULT 0.0000,
    watch_time INTEGER DEFAULT 0,  -- En secondes
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_wallets_user_id ON wallets(user_id);
CREATE INDEX idx_wallets_total_earnings ON wallets(total_earnings DESC);

-- ============================================
-- TABLE: KNOWLEDGE (Centre de Savoir)
-- ============================================
CREATE TABLE IF NOT EXISTS knowledge (
    id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    titre VARCHAR(255) NOT NULL,
    contenu TEXT,
    category VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_knowledge_author_id ON knowledge(author_id);
CREATE INDEX idx_knowledge_created_at ON knowledge(created_at DESC);

-- ============================================
-- TABLE: PFA REGISTRY (Registre PFA - Transparence)
-- ============================================
CREATE TABLE IF NOT EXISTS pfa_registry (
    id SERIAL PRIMARY KEY,
    transaction_type VARCHAR(50),  -- 'EXTRACTION', 'DISTRIBUTION', etc.
    amount DECIMAL(15, 4),
    category VARCHAR(100),  -- 'PARTAGE_GLOBAL', etc.
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pfa_registry_created_at ON pfa_registry(created_at DESC);
CREATE INDEX idx_pfa_registry_transaction_type ON pfa_registry(transaction_type);

-- ============================================
-- Fonction PostgreSQL pour auto-update timestamp
-- ============================================
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers pour updated_at
CREATE TRIGGER update_users_timestamp BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_posts_timestamp BEFORE UPDATE ON posts
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_lessons_timestamp BEFORE UPDATE ON lessons
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_wallets_timestamp BEFORE UPDATE ON wallets
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_knowledge_timestamp BEFORE UPDATE ON knowledge
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_comments_timestamp BEFORE UPDATE ON comments
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();
