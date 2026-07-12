"""
database.py – SQLite data layer
Grades 6-13, class sections (A-H), 3 terms per year.
"""
import sqlite3
import hashlib
import os
import re
import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "school.db")

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
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def run_query(query, params=(), fetch=False, fetchone=False):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        if fetchone:
            row = cur.fetchone()
            return dict(row) if row else None
        if fetch:
            return [dict(r) for r in cur.fetchall()]
        return cur.lastrowid


def init_db():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                full_name     TEXT,
                role          TEXT    NOT NULL CHECK(role IN ('admin','teacher')),
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS streams (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS subjects (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT    NOT NULL,
                stream_id INTEGER NOT NULL,
                UNIQUE(name, stream_id),
                FOREIGN KEY(stream_id) REFERENCES streams(id)
            );
            CREATE TABLE IF NOT EXISTS careers (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT    NOT NULL,
                stream_id INTEGER NOT NULL,
                UNIQUE(name, stream_id),
                FOREIGN KEY(stream_id) REFERENCES streams(id)
            );
            CREATE TABLE IF NOT EXISTS career_cutoffs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                career_id  INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                min_marks  REAL    NOT NULL,
                UNIQUE(career_id, subject_id),
                FOREIGN KEY(career_id)  REFERENCES careers(id),
                FOREIGN KEY(subject_id) REFERENCES subjects(id)
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
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                reg_no     TEXT    NOT NULL,
                subject_id INTEGER NOT NULL,
                term       INTEGER NOT NULL CHECK(term IN (1,2,3)),
                year       INTEGER NOT NULL,
                grade      INTEGER NOT NULL DEFAULT 10,
                marks      REAL    NOT NULL CHECK(marks >= 0 AND marks <= 100),
                UNIQUE(reg_no, subject_id, term, year),
                FOREIGN KEY(reg_no)     REFERENCES students(reg_no),
                FOREIGN KEY(subject_id) REFERENCES subjects(id)
            );
        """)

        # Seeds
        for s in STREAMS:
            cur.execute("INSERT OR IGNORE INTO streams (name) VALUES (?)", (s,))
        sid_map = {r["name"]: r["id"]
                   for r in cur.execute("SELECT id,name FROM streams").fetchall()}

        for sn, subs in DEFAULT_SUBJECTS.items():
            for sub in subs:
                cur.execute("INSERT OR IGNORE INTO subjects (name,stream_id) VALUES (?,?)", (sub, sid_map[sn]))

        for sn, careers in DEFAULT_CAREERS.items():
            sid = sid_map[sn]
            for cn, cutoffs in careers.items():
                cur.execute("INSERT OR IGNORE INTO careers (name,stream_id) VALUES (?,?)", (cn, sid))
                cid_row = cur.execute("SELECT id FROM careers WHERE name=? AND stream_id=?", (cn, sid)).fetchone()
                cid = cid_row["id"]
                for subname, mm in cutoffs.items():
                    sr = cur.execute("SELECT id FROM subjects WHERE name=? AND stream_id=?", (subname, sid)).fetchone()
                    if sr:
                        cur.execute("INSERT OR IGNORE INTO career_cutoffs (career_id,subject_id,min_marks) VALUES (?,?,?)",
                                    (cid, sr["id"], mm))

        # Default users
        cur.execute("INSERT OR IGNORE INTO users (username,password_hash,full_name,role) VALUES (?,?,?,?)",
                    ("admin", hash_password("admin123"), "System Administrator", "admin"))
        cur.execute("INSERT OR IGNORE INTO users (username,password_hash,full_name,role) VALUES (?,?,?,?)",
                    ("teacher", hash_password("teacher123"), "Counselling Teacher", "teacher"))
        conn.commit()


# ── Subject & Stream helpers ─────────────────────────────────────────────────
def get_or_create_subject(name, stream_id=None):
    if stream_id:
        r = run_query("SELECT id FROM subjects WHERE name=? AND stream_id=?", (name, stream_id), fetchone=True)
        if r: return r["id"]
    r = run_query("SELECT id FROM subjects WHERE name=?", (name,), fetchone=True)
    if r: return r["id"]
    sid = stream_id or 1
    run_query("INSERT OR IGNORE INTO subjects (name,stream_id) VALUES (?,?)", (name, sid))
    return run_query("SELECT id FROM subjects WHERE name=? AND stream_id=?", (name, sid), fetchone=True)["id"]


def get_streams():
    return run_query("SELECT * FROM streams ORDER BY name", fetch=True)

def get_stream_id(name):
    r = run_query("SELECT id FROM streams WHERE name=?", (name,), fetchone=True)
    return r["id"] if r else None

def get_subjects_by_stream(stream_id):
    return run_query("SELECT * FROM subjects WHERE stream_id=? ORDER BY name", (stream_id,), fetch=True)

def get_all_subjects():
    return run_query("SELECT s.*, st.name as stream_name FROM subjects s JOIN streams st ON s.stream_id=st.id ORDER BY st.name,s.name", fetch=True)

def get_careers_by_stream(stream_id):
    return run_query("SELECT * FROM careers WHERE stream_id=? ORDER BY name", (stream_id,), fetch=True)

def get_all_careers():
    return run_query("""SELECT c.id, c.name, str.name as stream_name,
                  (SELECT COUNT(*) FROM career_cutoffs cc WHERE cc.career_id=c.id) as cutoff_count,
                  (SELECT COUNT(*) FROM students st WHERE st.career_id=c.id)  as student_count
           FROM careers c JOIN streams str ON c.stream_id=str.id ORDER BY str.name, c.name""", fetch=True)

def get_career_cutoffs(career_id):
    return run_query("""SELECT cc.*, s.name as subject_name FROM career_cutoffs cc
           JOIN subjects s ON cc.subject_id=s.id WHERE cc.career_id=?""", (career_id,), fetch=True)

# ── Student helpers ──────────────────────────────────────────────────────────
def get_student(reg_no):
    return run_query("SELECT * FROM students WHERE reg_no=?", (reg_no,), fetchone=True)

def get_student_by_name_grade_class(name, grade, class_section):
    name_clean = name.strip().lower()
    rows = run_query("SELECT * FROM students WHERE grade=? AND class_section=?", (grade, class_section), fetch=True)
    for r in rows:
        if r["name"].strip().lower() == name_clean:
            return r
    return None

def _next_reg_no(grade, class_section, year):
    prefix = f"{year}-G{grade}{class_section}-"
    existing = run_query("SELECT reg_no FROM students WHERE reg_no LIKE ?", (prefix + "%",), fetch=True)
    nums = []
    for r in existing:
        m = re.search(r'-(\d+)$', r["reg_no"])
        if m: nums.append(int(m.group(1)))
    next_n = max(nums, default=0) + 1
    return f"{prefix}{next_n:03d}"

def upsert_student_bulk(name, grade, class_section, year):
    existing = get_student_by_name_grade_class(name, grade, class_section)
    if existing:
        return existing["reg_no"]
    reg_no = _next_reg_no(grade, class_section, year or 2026)
    run_query("INSERT OR IGNORE INTO students (reg_no,name,grade,class_section) VALUES (?,?,?,?)",
              (reg_no, name, grade, class_section))
    return reg_no

def upsert_student(reg_no, name, grade, class_section, stream_id, career_id):
    if get_student(reg_no):
        run_query("UPDATE students SET name=?,grade=?,class_section=?,stream_id=?,career_id=? WHERE reg_no=?",
                  (name, grade, class_section, stream_id, career_id, reg_no))
    else:
        run_query("INSERT INTO students (reg_no,name,grade,class_section,stream_id,career_id) VALUES (?,?,?,?,?,?)",
                  (reg_no, name, grade, class_section, stream_id, career_id))

def get_all_students(stream_id=None, grade=None, class_section=None):
    filters, params = [], []
    if stream_id: 
        filters.append("st.stream_id=?"); params.append(stream_id)
    if grade: 
        filters.append("st.grade=?"); params.append(grade)
    if class_section: 
        filters.append("st.class_section=?"); params.append(class_section)
    where = (" WHERE " + " AND ".join(filters)) if filters else ""
    return run_query(
        f"""SELECT st.*, c.name as career_name, str.name as stream_name
            FROM students st
            LEFT JOIN careers c ON st.career_id=c.id
            LEFT JOIN streams str ON st.stream_id=str.id
            {where} ORDER BY st.grade, st.class_section, st.name""",
        tuple(params), fetch=True)

# ── Marks helpers ────────────────────────────────────────────────────────────
def save_mark(reg_no, subject_id, term, year, grade, marks):
    run_query("""INSERT INTO marks (reg_no,subject_id,term,year,grade,marks)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(reg_no,subject_id,term,year)
           DO UPDATE SET marks=excluded.marks, grade=excluded.grade""",
        (reg_no, subject_id, term, year, grade, marks))

def get_marks_for_student(reg_no, year=None):
    if year:
        return run_query("""SELECT m.*, s.name as subject_name FROM marks m
               JOIN subjects s ON m.subject_id=s.id
               WHERE m.reg_no=? AND m.year=? ORDER BY s.name, m.term""",
            (reg_no, year), fetch=True)
    return run_query("""SELECT m.*, s.name as subject_name FROM marks m
           JOIN subjects s ON m.subject_id=s.id
           WHERE m.reg_no=? ORDER BY m.year, s.name, m.term""",
        (reg_no,), fetch=True)

def get_grade_year_averages():
    return run_query("""SELECT m.grade, m.year, AVG(m.marks) as avg_marks, COUNT(*) as sample_size
           FROM marks m GROUP BY m.grade, m.year ORDER BY m.grade, m.year""", fetch=True)

def get_grade_class_averages(year=None):
    if year:
        return run_query("""SELECT m.grade, st.class_section,
                  AVG(m.marks) as avg_marks, COUNT(DISTINCT m.reg_no) as student_count
           FROM marks m JOIN students st ON m.reg_no=st.reg_no
           WHERE m.year=? GROUP BY m.grade, st.class_section ORDER BY m.grade, st.class_section""",
            (year,), fetch=True)
    return run_query("""SELECT m.grade, st.class_section,
              AVG(m.marks) as avg_marks, COUNT(DISTINCT m.reg_no) as student_count
       FROM marks m JOIN students st ON m.reg_no=st.reg_no
       GROUP BY m.grade, st.class_section ORDER BY m.grade, st.class_section""", fetch=True)

def get_class_subject_averages(grade, class_section, year=None):
    params = [grade, class_section]
    year_clause = ""
    if year:
        year_clause = "AND m.year=?"
        params.append(year)
    return run_query(f"""SELECT s.name as subject_name, AVG(m.marks) as avg_marks,
              COUNT(DISTINCT m.reg_no) as n
           FROM marks m
           JOIN subjects s  ON m.subject_id=s.id
           JOIN students st ON m.reg_no=st.reg_no
           WHERE st.grade=? AND st.class_section=? {year_clause}
           GROUP BY m.subject_id ORDER BY s.name""",
        tuple(params), fetch=True)

# ── CRUD for Subjects & Careers (keep as is) ────────────────────────────────
def add_subject(name, stream_id):
    run_query("INSERT OR IGNORE INTO subjects (name,stream_id) VALUES (?,?)", (name, stream_id))

def update_subject(subject_id, new_name):
    run_query("UPDATE subjects SET name=? WHERE id=?", (new_name, subject_id))

def subject_usage_counts(subject_id):
    mc = run_query("SELECT COUNT(*) as c FROM marks WHERE subject_id=?", (subject_id,), fetchone=True)["c"]
    cc = run_query("SELECT COUNT(*) as c FROM career_cutoffs WHERE subject_id=?", (subject_id,), fetchone=True)["c"]
    return mc, cc

def delete_subject(subject_id, cascade=False):
    if not cascade:
        mc, cc = subject_usage_counts(subject_id)
        if mc or cc:
            raise ValueError(f"Subject is used in {mc} marks and {cc} cutoffs.")
    if cascade:
        run_query("DELETE FROM marks WHERE subject_id=?", (subject_id,))
        run_query("DELETE FROM career_cutoffs WHERE subject_id=?", (subject_id,))
    run_query("DELETE FROM subjects WHERE id=?", (subject_id,))

# Career CRUD (keep original)
def add_career(name, stream_id, cutoffs):
    run_query("INSERT OR IGNORE INTO careers (name,stream_id) VALUES (?,?)", (name, stream_id))
    row = run_query("SELECT id FROM careers WHERE name=? AND stream_id=?", (name, stream_id), fetchone=True)
    cid = row["id"]
    for sid, mm in cutoffs.items():
        run_query("INSERT INTO career_cutoffs (career_id,subject_id,min_marks) VALUES (?,?,?) "
                  "ON CONFLICT(career_id,subject_id) DO UPDATE SET min_marks=excluded.min_marks",
                  (cid, sid, mm))
    return cid

def career_usage_counts(career_id):
    return run_query("SELECT COUNT(*) as c FROM students WHERE career_id=?", (career_id,), fetchone=True)["c"]

def delete_career(career_id, cascade=False):
    n = career_usage_counts(career_id)
    if n and not cascade:
        raise ValueError(f"Career assigned to {n} student(s).")
    if cascade:
        run_query("UPDATE students SET career_id=NULL WHERE career_id=?", (career_id,))
    run_query("DELETE FROM career_cutoffs WHERE career_id=?", (career_id,))
    run_query("DELETE FROM careers WHERE id=?", (career_id,))

# ── Login ────────────────────────────────────────────────────────────────────
def verify_login(username, password):
    u = run_query("SELECT * FROM users WHERE username=?", (username,), fetchone=True)
    return u if (u and u["password_hash"] == hash_password(password)) else None

# ── User Management CRUD ─────────────────────────────────────────────────────
def get_all_users():
    query = """
        SELECT id, username, full_name, role, 
               COALESCE(created_at, '2026-01-01') as created_at
        FROM users 
        ORDER BY id DESC
    """
    return run_query(query, fetch=True)


def add_user(username, password, full_name, role="teacher"):
    existing = run_query("SELECT id FROM users WHERE username = ?", (username,), fetch=True)
    if existing:
        return False
    hashed_pw = hash_password(password)
    query = """
        INSERT INTO users (username, password_hash, full_name, role)
        VALUES (?, ?, ?, ?)
    """
    try:
        run_query(query, (username, hashed_pw, full_name, role))
        return True
    except Exception as e:
        print(f"Error adding user: {e}")
        return False


def update_user(user_id, full_name, role):
    query = "UPDATE users SET full_name = ?, role = ? WHERE id = ?"
    try:
        run_query(query, (full_name, role, user_id))
        return True
    except:
        return False


def delete_user(identifier):
    try:
        run_query("DELETE FROM users WHERE username = ?", (identifier,))
        return True
    except:
        try:
            run_query("DELETE FROM users WHERE id = ?", (int(identifier),))
            return True
        except:
            return False