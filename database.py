"""
database.py – PostgreSQL data layer (Supabase compatible)
Grades 6-13, class sections (A-H), 3 terms per year.
Uses psycopg2 and environment variable DATABASE_URL.
"""

import os
import re
import hashlib
import datetime
from contextlib import contextmanager
from urllib.parse import urlparse
import psycopg2
from psycopg2.extras import RealDictCursor

# Read database URL from environment (Supabase provides this)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback for local development (you can set a local PostgreSQL URL)
    DATABASE_URL = "postgresql://user:pass@localhost:5432/school_db"

STREAMS = ["Art", "Commerce", "Maths", "Bio", "Technology", "Vocational"]
GRADES  = list(range(6, 14))

DEFAULT_SUBJECTS = {
    "Art":        ["History", "Geography", "Languages", "Logic & Reasoning"],
    "Commerce":   ["Accounting", "Business Studies", "Economics", "Mathematics"],
    "Maths":      ["Pure Mathematics", "Physics", "Chemistry", "Combined Maths"],
    "Bio":        ["Biology", "Chemistry", "Physics", "Agriculture"],
    "Technology": ["Engineering Technology", "Science for Technology", "ICT", "Mathematics"],
    "Vocational": ["Practical Skills", "ICT", "Communication", "Entrepreneurship"],
}

DEFAULT_CAREERS = {
    "Art":        {"Lawyer": {"History":75,"Geography":60,"Languages":70,"Logic & Reasoning":65},
                   "Journalist": {"History":65,"Geography":55,"Languages":75,"Logic & Reasoning":55}},
    "Commerce":   {"Accountant": {"Accounting":80,"Business Studies":65,"Economics":65,"Mathematics":60},
                   "Business Manager": {"Accounting":60,"Business Studies":75,"Economics":65,"Mathematics":55}},
    "Maths":      {"Engineer": {"Pure Mathematics":80,"Physics":75,"Chemistry":60,"Combined Maths":80},
                   "Data Scientist": {"Pure Mathematics":85,"Physics":60,"Chemistry":55,"Combined Maths":85}},
    "Bio":        {"Doctor": {"Biology":85,"Chemistry":80,"Physics":70,"Agriculture":50},
                   "Pharmacist": {"Biology":75,"Chemistry":80,"Physics":60,"Agriculture":50}},
    "Technology": {"Software Engineer": {"Engineering Technology":70,"Science for Technology":65,"ICT":85,"Mathematics":70},
                   "Network Technician": {"Engineering Technology":65,"Science for Technology":55,"ICT":75,"Mathematics":55}},
    "Vocational": {"Entrepreneur": {"Practical Skills":75,"ICT":60,"Communication":70,"Entrepreneurship":80},
                   "Technician": {"Practical Skills":85,"ICT":65,"Communication":55,"Entrepreneurship":50}},
}


def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()


@contextmanager
def get_conn():
    """
    Return a PostgreSQL connection using DATABASE_URL from environment.
    Uses explicit connection parameters (bypasses query-string issues).
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL environment variable not set.")
    
    # Strip any surrounding whitespace or quotes
    url = url.strip().strip('"').strip("'")
    
    # Parse the URL into components
    parsed = urlparse(url)
    dbname = parsed.path.lstrip('/')
    
    # Connect using explicit parameters – ignores ?pgbouncer=true etc.
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        user=parsed.username,
        password=parsed.password,
        dbname=dbname,
        sslmode='require'  # Supabase requires SSL
    )
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_query(query, params=(), fetch=False, fetchone=False):
    """Execute a query and optionally return results as list of dicts or one dict."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetchone:
                row = cur.fetchone()
                return dict(row) if row else None
            if fetch:
                return [dict(r) for r in cur.fetchall()]
            # For INSERT/UPDATE with RETURNING, we might want the id
            try:
                return cur.fetchone()[0] if cur.description else None
            except:
                return None


def init_db():
    """Create tables and seed default data if not exists."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Create tables using PostgreSQL syntax
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            SERIAL PRIMARY KEY,
                    username      TEXT    UNIQUE NOT NULL,
                    password_hash TEXT    NOT NULL,
                    full_name     TEXT,
                    role          TEXT    NOT NULL CHECK(role IN ('admin','teacher')),
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS streams (
                    id   SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL
                );
                CREATE TABLE IF NOT EXISTS subjects (
                    id        SERIAL PRIMARY KEY,
                    name      TEXT    NOT NULL,
                    stream_id INTEGER NOT NULL,
                    UNIQUE(name, stream_id),
                    FOREIGN KEY(stream_id) REFERENCES streams(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS careers (
                    id        SERIAL PRIMARY KEY,
                    name      TEXT    NOT NULL,
                    stream_id INTEGER NOT NULL,
                    UNIQUE(name, stream_id),
                    FOREIGN KEY(stream_id) REFERENCES streams(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS career_cutoffs (
                    id         SERIAL PRIMARY KEY,
                    career_id  INTEGER NOT NULL,
                    subject_id INTEGER NOT NULL,
                    min_marks  REAL    NOT NULL,
                    UNIQUE(career_id, subject_id),
                    FOREIGN KEY(career_id)  REFERENCES careers(id) ON DELETE CASCADE,
                    FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS students (
                    reg_no        TEXT    PRIMARY KEY,
                    name          TEXT    NOT NULL,
                    grade         INTEGER NOT NULL DEFAULT 10,
                    class_section TEXT    NOT NULL DEFAULT 'A',
                    stream_id     INTEGER,
                    career_id     INTEGER,
                    FOREIGN KEY(stream_id) REFERENCES streams(id),
                    FOREIGN KEY(career_id) REFERENCES careers(id)
                );
                CREATE TABLE IF NOT EXISTS marks (
                    id         SERIAL PRIMARY KEY,
                    reg_no     TEXT    NOT NULL,
                    subject_id INTEGER NOT NULL,
                    term       INTEGER NOT NULL CHECK(term IN (1,2,3)),
                    year       INTEGER NOT NULL,
                    grade      INTEGER NOT NULL DEFAULT 10,
                    marks      REAL    NOT NULL CHECK(marks >= 0 AND marks <= 100),
                    UNIQUE(reg_no, subject_id, term, year),
                    FOREIGN KEY(reg_no)     REFERENCES students(reg_no) ON DELETE CASCADE,
                    FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
                );
            """)
            conn.commit()

            # Seed streams
            for s in STREAMS:
                cur.execute("INSERT INTO streams (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (s,))
            conn.commit()

            # Get stream ids
            cur.execute("SELECT id, name FROM streams")
            sid_map = {r[1]: r[0] for r in cur.fetchall()}

            # Seed subjects
            for sn, subs in DEFAULT_SUBJECTS.items():
                for sub in subs:
                    cur.execute(
                        "INSERT INTO subjects (name, stream_id) VALUES (%s, %s) ON CONFLICT (name, stream_id) DO NOTHING",
                        (sub, sid_map[sn])
                    )

            # Seed careers and cutoffs
            for sn, careers in DEFAULT_CAREERS.items():
                sid = sid_map[sn]
                for cn, cutoffs in careers.items():
                    # Insert career
                    cur.execute(
                        "INSERT INTO careers (name, stream_id) VALUES (%s, %s) ON CONFLICT (name, stream_id) DO NOTHING",
                        (cn, sid)
                    )
                    # Get career id
                    cur.execute("SELECT id FROM careers WHERE name=%s AND stream_id=%s", (cn, sid))
                    row = cur.fetchone()
                    if row:
                        cid = row[0]
                        for subname, mm in cutoffs.items():
                            # Get subject id
                            cur.execute("SELECT id FROM subjects WHERE name=%s AND stream_id=%s", (subname, sid))
                            sub_row = cur.fetchone()
                            if sub_row:
                                sid2 = sub_row[0]
                                cur.execute(
                                    """INSERT INTO career_cutoffs (career_id, subject_id, min_marks)
                                       VALUES (%s, %s, %s)
                                       ON CONFLICT (career_id, subject_id) DO UPDATE SET min_marks = EXCLUDED.min_marks""",
                                    (cid, sid2, mm)
                                )
            conn.commit()

            # Default users
            cur.execute(
                "INSERT INTO users (username, password_hash, full_name, role) VALUES (%s, %s, %s, %s) ON CONFLICT (username) DO NOTHING",
                ("admin", hash_password("admin123"), "System Administrator", "admin")
            )
            cur.execute(
                "INSERT INTO users (username, password_hash, full_name, role) VALUES (%s, %s, %s, %s) ON CONFLICT (username) DO NOTHING",
                ("teacher", hash_password("teacher123"), "Counselling Teacher", "teacher")
            )
            conn.commit()


# ── Subject & Stream helpers ─────────────────────────────────────────────────
def get_or_create_subject(name, stream_id=None):
    if stream_id:
        r = run_query("SELECT id FROM subjects WHERE name=%s AND stream_id=%s", (name, stream_id), fetchone=True)
        if r:
            return r["id"]
    r = run_query("SELECT id FROM subjects WHERE name=%s", (name,), fetchone=True)
    if r:
        return r["id"]
    sid = stream_id or 1
    run_query("INSERT INTO subjects (name, stream_id) VALUES (%s, %s) ON CONFLICT (name, stream_id) DO NOTHING", (name, sid))
    r = run_query("SELECT id FROM subjects WHERE name=%s AND stream_id=%s", (name, sid), fetchone=True)
    return r["id"] if r else None


def get_streams():
    return run_query("SELECT * FROM streams ORDER BY name", fetch=True)


def get_stream_id(name):
    r = run_query("SELECT id FROM streams WHERE name=%s", (name,), fetchone=True)
    return r["id"] if r else None


def get_subjects_by_stream(stream_id):
    return run_query("SELECT * FROM subjects WHERE stream_id=%s ORDER BY name", (stream_id,), fetch=True)


def get_all_subjects():
    return run_query("""
        SELECT s.*, st.name as stream_name
        FROM subjects s
        JOIN streams st ON s.stream_id=st.id
        ORDER BY st.name, s.name
    """, fetch=True)


def get_careers_by_stream(stream_id):
    return run_query("SELECT * FROM careers WHERE stream_id=%s ORDER BY name", (stream_id,), fetch=True)


def get_all_careers():
    return run_query("""
        SELECT c.id, c.name, str.name as stream_name,
               (SELECT COUNT(*) FROM career_cutoffs cc WHERE cc.career_id=c.id) as cutoff_count,
               (SELECT COUNT(*) FROM students st WHERE st.career_id=c.id)  as student_count
        FROM careers c
        JOIN streams str ON c.stream_id=str.id
        ORDER BY str.name, c.name
    """, fetch=True)


def get_career_cutoffs(career_id):
    return run_query("""
        SELECT cc.*, s.name as subject_name
        FROM career_cutoffs cc
        JOIN subjects s ON cc.subject_id=s.id
        WHERE cc.career_id=%s
    """, (career_id,), fetch=True)


# ── Student helpers ──────────────────────────────────────────────────────────
def get_student(reg_no):
    return run_query("SELECT * FROM students WHERE reg_no=%s", (reg_no,), fetchone=True)


def get_student_by_name_grade_class(name, grade, class_section):
    name_clean = name.strip().lower()
    rows = run_query(
        "SELECT * FROM students WHERE grade=%s AND class_section=%s",
        (grade, class_section), fetch=True
    )
    for r in rows:
        if r["name"].strip().lower() == name_clean:
            return r
    return None


def _next_reg_no(grade, class_section, year):
    prefix = f"{year}-G{grade}{class_section}-"
    existing = run_query("SELECT reg_no FROM students WHERE reg_no LIKE %s", (prefix + '%',), fetch=True)
    nums = []
    for r in existing:
        m = re.search(r'-(\d+)$', r["reg_no"])
        if m:
            nums.append(int(m.group(1)))
    next_n = max(nums, default=0) + 1
    return f"{prefix}{next_n:03d}"


def upsert_student_bulk(name, grade, class_section, year):
    existing = get_student_by_name_grade_class(name, grade, class_section)
    if existing:
        return existing["reg_no"]
    reg_no = _next_reg_no(grade, class_section, year or 2026)
    run_query(
        "INSERT INTO students (reg_no, name, grade, class_section) VALUES (%s, %s, %s, %s) ON CONFLICT (reg_no) DO NOTHING",
        (reg_no, name, grade, class_section)
    )
    return reg_no


def upsert_student(reg_no, name, grade, class_section, stream_id, career_id):
    existing = get_student(reg_no)
    if existing:
        run_query(
            "UPDATE students SET name=%s, grade=%s, class_section=%s, stream_id=%s, career_id=%s WHERE reg_no=%s",
            (name, grade, class_section, stream_id, career_id, reg_no)
        )
    else:
        run_query(
            "INSERT INTO students (reg_no, name, grade, class_section, stream_id, career_id) VALUES (%s, %s, %s, %s, %s, %s)",
            (reg_no, name, grade, class_section, stream_id, career_id)
        )


def get_all_students(stream_id=None, grade=None, class_section=None):
    filters, params = [], []
    if stream_id:
        filters.append("st.stream_id=%s")
        params.append(stream_id)
    if grade:
        filters.append("st.grade=%s")
        params.append(grade)
    if class_section:
        filters.append("st.class_section=%s")
        params.append(class_section)
    where = (" WHERE " + " AND ".join(filters)) if filters else ""
    query = f"""
        SELECT st.*, c.name as career_name, str.name as stream_name
        FROM students st
        LEFT JOIN careers c ON st.career_id=c.id
        LEFT JOIN streams str ON st.stream_id=str.id
        {where}
        ORDER BY st.grade, st.class_section, st.name
    """
    return run_query(query, tuple(params), fetch=True)


# ── Marks helpers ────────────────────────────────────────────────────────────
def save_mark(reg_no, subject_id, term, year, grade, marks):
    run_query("""
        INSERT INTO marks (reg_no, subject_id, term, year, grade, marks)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (reg_no, subject_id, term, year)
        DO UPDATE SET marks = EXCLUDED.marks, grade = EXCLUDED.grade
    """, (reg_no, subject_id, term, year, grade, marks))


def get_marks_for_student(reg_no, year=None):
    if year:
        return run_query("""
            SELECT m.*, s.name as subject_name
            FROM marks m
            JOIN subjects s ON m.subject_id=s.id
            WHERE m.reg_no=%s AND m.year=%s
            ORDER BY s.name, m.term
        """, (reg_no, year), fetch=True)
    return run_query("""
        SELECT m.*, s.name as subject_name
        FROM marks m
        JOIN subjects s ON m.subject_id=s.id
        WHERE m.reg_no=%s
        ORDER BY m.year, s.name, m.term
    """, (reg_no,), fetch=True)


def get_grade_year_averages():
    return run_query("""
        SELECT m.grade, m.year, AVG(m.marks) as avg_marks, COUNT(*) as sample_size
        FROM marks m
        GROUP BY m.grade, m.year
        ORDER BY m.grade, m.year
    """, fetch=True)


def get_grade_class_averages(year=None):
    if year:
        return run_query("""
            SELECT m.grade, st.class_section,
                   AVG(m.marks) as avg_marks, COUNT(DISTINCT m.reg_no) as student_count
            FROM marks m
            JOIN students st ON m.reg_no=st.reg_no
            WHERE m.year=%s
            GROUP BY m.grade, st.class_section
            ORDER BY m.grade, st.class_section
        """, (year,), fetch=True)
    return run_query("""
        SELECT m.grade, st.class_section,
               AVG(m.marks) as avg_marks, COUNT(DISTINCT m.reg_no) as student_count
        FROM marks m
        JOIN students st ON m.reg_no=st.reg_no
        GROUP BY m.grade, st.class_section
        ORDER BY m.grade, st.class_section
    """, fetch=True)


def get_class_subject_averages(grade, class_section, year=None):
    params = [grade, class_section]
    year_clause = ""
    if year:
        year_clause = "AND m.year=%s"
        params.append(year)
    return run_query(f"""
        SELECT s.name as subject_name, AVG(m.marks) as avg_marks,
               COUNT(DISTINCT m.reg_no) as n
        FROM marks m
        JOIN subjects s  ON m.subject_id=s.id
        JOIN students st ON m.reg_no=st.reg_no
        WHERE st.grade=%s AND st.class_section=%s {year_clause}
        GROUP BY m.subject_id
        ORDER BY s.name
    """, tuple(params), fetch=True)


# ── CRUD for Subjects & Careers ─────────────────────────────────────────────
def add_subject(name, stream_id):
    run_query(
        "INSERT INTO subjects (name, stream_id) VALUES (%s, %s) ON CONFLICT (name, stream_id) DO NOTHING",
        (name, stream_id)
    )


def update_subject(subject_id, new_name):
    run_query("UPDATE subjects SET name=%s WHERE id=%s", (new_name, subject_id))


def subject_usage_counts(subject_id):
    mc = run_query("SELECT COUNT(*) as c FROM marks WHERE subject_id=%s", (subject_id,), fetchone=True)["c"]
    cc = run_query("SELECT COUNT(*) as c FROM career_cutoffs WHERE subject_id=%s", (subject_id,), fetchone=True)["c"]
    return mc, cc


def delete_subject(subject_id, cascade=False):
    if not cascade:
        mc, cc = subject_usage_counts(subject_id)
        if mc or cc:
            raise ValueError(f"Subject is used in {mc} marks and {cc} cutoffs.")
    # Foreign keys with ON DELETE CASCADE will automatically delete related marks and cutoffs
    run_query("DELETE FROM subjects WHERE id=%s", (subject_id,))


# Career CRUD (fixed)
def add_career(name, stream_id):
    """Insert a new career without cutoffs."""
    run_query(
        "INSERT INTO careers (name, stream_id) VALUES (%s, %s) ON CONFLICT (name, stream_id) DO NOTHING",
        (name, stream_id)
    )


def update_career(career_id, new_name):
    run_query("UPDATE careers SET name=%s WHERE id=%s", (new_name, career_id))


def career_usage_counts(career_id):
    r = run_query("SELECT COUNT(*) as c FROM students WHERE career_id=%s", (career_id,), fetchone=True)
    return r["c"] if r else 0


def delete_career(career_id, cascade=False):
    n = career_usage_counts(career_id)
    if n and not cascade:
        raise ValueError(f"Career assigned to {n} student(s).")
    if cascade:
        run_query("UPDATE students SET career_id=NULL WHERE career_id=%s", (career_id,))
    run_query("DELETE FROM careers WHERE id=%s", (career_id,))


# ── Login ────────────────────────────────────────────────────────────────────
def verify_login(username, password):
    u = run_query("SELECT * FROM users WHERE username=%s", (username,), fetchone=True)
    if u and u["password_hash"] == hash_password(password):
        return u
    return None


# ── User Management CRUD ─────────────────────────────────────────────────────
def get_all_users():
    return run_query("""
        SELECT id, username, full_name, role,
               COALESCE(created_at, '2026-01-01') as created_at
        FROM users
        ORDER BY id DESC
    """, fetch=True)


def add_user(username, password, full_name, role="teacher"):
    existing = run_query("SELECT id FROM users WHERE username=%s", (username,), fetchone=True)
    if existing:
        return False
    hashed = hash_password(password)
    try:
        run_query(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (%s, %s, %s, %s)",
            (username, hashed, full_name, role)
        )
        return True
    except Exception:
        return False


def update_user(user_id, full_name, role):
    try:
        run_query("UPDATE users SET full_name=%s, role=%s WHERE id=%s", (full_name, role, user_id))
        return True
    except Exception:
        return False


def delete_user(identifier):
    try:
        run_query("DELETE FROM users WHERE username=%s", (identifier,))
        return True
    except Exception:
        try:
            run_query("DELETE FROM users WHERE id=%s", (int(identifier),))
            return True
        except Exception:
            return False