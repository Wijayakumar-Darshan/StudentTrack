"""
app.py – Student Performance & Marks Management System
Professional UI Edition – for schools and academic institutions.
"""

# =============================================================================
# CRITICAL ENVIRONMENT VARIABLES – must be set before any imports
# =============================================================================
import os
os.environ["MPLBACKEND"] = "Agg"
os.environ["PANDAS_USE_PYARROW"] = "0"

# =============================================================================
# Standard imports
# =============================================================================
import datetime
import re
import tempfile
import time
import gc
import io
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")  # suppress conditional formatting warnings

import streamlit as st
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # double‑safe
import matplotlib.pyplot as plt
import numpy as np
import jwt
import datetime as dt
from datetime import timedelta
import database as db
import ai_advisor
import pdf_report
import prediction_ai as pai
import excel_parser
from dotenv import load_dotenv
import urllib.request
import urllib.error
import ssl
import random

# ------------------------------------------------------------------------------
# PDF generation with fpdf2 (pure Python, no segfaults)
# ------------------------------------------------------------------------------
from fpdf import FPDF
from fpdf.enums import XPos, YPos   # for new cell syntax
FPDF_AVAILABLE = True

load_dotenv()

SECRET_KEY = os.getenv(
    "JWT_SECRET",
    "your-super-secret-jwt-key-change-this-in-production-2026"
)
ALGORITHM = "HS256"
TOKEN_EXPIRATION_MINUTES = int(
    os.getenv("TOKEN_EXPIRATION_MINUTES", 1440)
)

st.set_page_config(
    page_title="Student Performance System",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

db.init_db()

# Disable matplotlib interactive mode
plt.ioff()

# =============================================================================
# HELPER: Get Unicode‑capable fonts (robust fallback with caching)
# =============================================================================
class FontNotFoundError(Exception):
    """Raised when no suitable Unicode font can be found."""
    pass

def get_unicode_fonts():
    """
    Returns (regular_font_path, bold_font_path) for a Unicode‑capable font.
    Tries to download DejaVuSans, falls back to system fonts (Arial, Segoe UI, etc.).
    Caches paths in session state only if both files are valid and exist.
    """
    # Check if we have cached valid paths
    cache_valid = (
        "font_regular" in st.session_state and
        "font_bold" in st.session_state and
        st.session_state.font_regular is not None and
        st.session_state.font_bold is not None and
        os.path.exists(st.session_state.font_regular) and
        os.path.exists(st.session_state.font_bold)
    )
    if cache_valid:
        return st.session_state.font_regular, st.session_state.font_bold

    # If cache exists but invalid, clear it
    if "font_regular" in st.session_state:
        del st.session_state.font_regular
    if "font_bold" in st.session_state:
        del st.session_state.font_bold

    font_dir = tempfile.gettempdir()
    regular_path = os.path.join(font_dir, "DejaVuSans.ttf")
    bold_path = os.path.join(font_dir, "DejaVuSans-Bold.ttf")

    # Helper to download a file with retries
    def download_file(url, dest_path, max_retries=3):
        ssl_context = ssl._create_unverified_context() if hasattr(ssl, '_create_unverified_context') else None
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, context=ssl_context, timeout=15) as response:
                    with open(dest_path, 'wb') as f:
                        f.write(response.read())
                return True
            except Exception:
                time.sleep(0.5 * (attempt + 1) + random.uniform(0, 0.5))
        return False

    # Try to download DejaVuSans from multiple mirrors
    regular_urls = [
        "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSans.ttf",
        "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf",
        "https://cdn.jsdelivr.net/gh/dejavu-fonts/dejavu-fonts/ttf/DejaVuSans.ttf",
    ]
    bold_urls = [
        "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSans-Bold.ttf",
        "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans-Bold.ttf",
        "https://cdn.jsdelivr.net/gh/dejavu-fonts/dejavu-fonts/ttf/DejaVuSans-Bold.ttf",
    ]

    downloaded_regular = os.path.exists(regular_path) or any(download_file(url, regular_path) for url in regular_urls)
    downloaded_bold = os.path.exists(bold_path) or any(download_file(url, bold_path) for url in bold_urls)

    if downloaded_regular and downloaded_bold:
        # Cache and return
        st.session_state.font_regular = regular_path
        st.session_state.font_bold = bold_path
        return regular_path, bold_path

    # If download failed, try system fonts
    system_fonts = {
        # Windows
        "C:/Windows/Fonts/arial.ttf": "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeui.ttf": "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/tahoma.ttf": "C:/Windows/Fonts/tahomabd.ttf",
        # Linux
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf": "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf": "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        # Mac
        "/Library/Fonts/Arial.ttf": "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc": None,  # no bold separate file
    }

    for reg, bold in system_fonts.items():
        if os.path.exists(reg):
            # If bold not found, use regular for bold (not ideal but avoids error)
            bold_file = bold if bold and os.path.exists(bold) else reg
            # Ensure both are valid
            if os.path.exists(bold_file):
                st.session_state.font_regular = reg
                st.session_state.font_bold = bold_file
                return reg, bold_file

    # If we still have one of the DejaVu files, use it for both styles
    if os.path.exists(regular_path):
        st.session_state.font_regular = regular_path
        st.session_state.font_bold = regular_path  # same for both
        return regular_path, regular_path
    if os.path.exists(bold_path):
        st.session_state.font_regular = bold_path
        st.session_state.font_bold = bold_path
        return bold_path, bold_path

    # No font found – raise error
    raise FontNotFoundError(
        "Could not obtain a Unicode font (DejaVuSans, Arial, or LiberationSans). "
        "Please install a Unicode font on your system or check your internet connection."
    )

# =============================================================================
# PROFESSIONAL UI – ENHANCED CSS (School‑grade design)
# =============================================================================
st.markdown("""
<style>
/* ----- Google Fonts ----- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Poppins:wght@600;700&display=swap');

/* ----- Base & body ----- */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.stApp {
    background: #f3f6fc;
    background-image: radial-gradient(ellipse at 10% 20%, rgba(79,126,179,0.03) 0%, transparent 50%),
                      radial-gradient(ellipse at 90% 80%, rgba(79,126,179,0.03) 0%, transparent 50%);
}

/* ----- Hide default Streamlit elements ----- */
#MainMenu, header[data-testid="stHeader"] { background: transparent; }
footer { visibility: hidden; }

/* ----- Sidebar – dark professional ----- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f1a2f 0%, #1a2a47 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}
section[data-testid="stSidebar"] * {
    color: #e8edf5 !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.10);
    margin: 1rem 0;
}
section[data-testid="stSidebar"] .stButton button {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 10px;
    padding: 0.4rem 1rem;
    font-weight: 500;
    transition: all 0.2s;
    color: #e8edf5 !important;
}
section[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(255,255,255,0.14);
    border-color: rgba(255,255,255,0.25);
    transform: translateY(-1px);
}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stRadio label {
    color: #b0c4e8 !important;
    font-weight: 500;
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
    padding: 0.3rem 0.6rem;
    border-radius: 8px;
    transition: background 0.15s;
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover {
    background: rgba(255,255,255,0.06);
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label[data-selected="true"] {
    background: rgba(79,126,179,0.30);
    border-left: 3px solid #4f7eb3;
}

/* ----- User profile in sidebar ----- */
.sidebar-profile {
    text-align: center;
    padding: 1.2rem 0 0.6rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.sidebar-profile .avatar {
    font-size: 3rem;
    margin-bottom: 0.2rem;
}
.sidebar-profile .name {
    font-weight: 700;
    font-size: 1.1rem;
    color: #ffffff;
}
.sidebar-profile .role {
    font-size: 0.8rem;
    background: rgba(79,126,179,0.35);
    padding: 0.15rem 1rem;
    border-radius: 20px;
    display: inline-block;
    color: #b8d0f0;
    margin-top: 0.2rem;
}

/* ----- Headings & typography ----- */
h1, h2, h3, h4 {
    font-family: 'Poppins', sans-serif;
    font-weight: 700;
    color: #0f1a2f;
    letter-spacing: -0.02em;
}
h1 { font-size: 2rem; }
h2 { font-size: 1.6rem; }
h3 { font-size: 1.3rem; }

/* ----- Cards and containers ----- */
div[data-testid="stForm"] {
    background: rgba(255,255,255,0.85);
    backdrop-filter: blur(8px);
    padding: 1.8rem 2.2rem;
    border-radius: 24px;
    box-shadow: 0 10px 40px rgba(15,26,47,0.06);
    border: 1px solid rgba(255,255,255,0.70);
    transition: box-shadow 0.25s;
}
div[data-testid="stForm"]:hover {
    box-shadow: 0 14px 50px rgba(15,26,47,0.10);
}

div[data-testid="stExpander"] {
    background: rgba(255,255,255,0.80);
    backdrop-filter: blur(4px);
    border-radius: 18px;
    border: 1px solid rgba(255,255,255,0.60);
    box-shadow: 0 4px 20px rgba(15,26,47,0.04);
    margin-bottom: 0.8rem;
}

/* ----- Buttons – full width inside forms (via CSS) ----- */
div.stForm button[data-testid="baseButton-secondary"],
div.stForm button[data-testid="baseButton-primary"] {
    width: 100%;
    background: linear-gradient(135deg, #4f7eb3 0%, #2c4e7a 100%);
    color: white;
    border: none;
    border-radius: 14px;
    padding: 0.65rem 0;
    font-weight: 600;
    font-size: 1rem;
    transition: all 0.2s ease;
    box-shadow: 0 6px 18px rgba(79,126,179,0.25);
}
div.stForm button[data-testid="baseButton-secondary"]:hover,
div.stForm button[data-testid="baseButton-primary"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 28px rgba(79,126,179,0.35);
    background: linear-gradient(135deg, #5a8ec9 0%, #2c4e7a 100%);
}

/* Normal buttons outside forms */
.stButton > button {
    background: linear-gradient(135deg, #4f7eb3 0%, #2c4e7a 100%);
    color: white;
    border: none;
    border-radius: 14px;
    padding: 0.5rem 1.6rem;
    font-weight: 600;
    transition: all 0.2s ease;
    box-shadow: 0 4px 14px rgba(79,126,179,0.20);
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(79,126,179,0.35);
}

/* Danger buttons (delete) */
.stButton button[data-testid="baseButton-primary"]:has(svg[data-testid="icon-delete"]) {
    background: linear-gradient(135deg, #c0392b 0%, #922b21 100%);
    box-shadow: 0 4px 14px rgba(192,57,43,0.30);
}
.stButton button[data-testid="baseButton-primary"]:has(svg[data-testid="icon-delete"]):hover {
    background: linear-gradient(135deg, #e74c3c 0%, #a93226 100%);
    box-shadow: 0 8px 24px rgba(192,57,43,0.40);
}

/* Download buttons */
.stDownloadButton > button {
    background: linear-gradient(135deg, #27ae60 0%, #1e8449 100%);
    color: white;
    border: none;
    border-radius: 14px;
    font-weight: 600;
    box-shadow: 0 4px 14px rgba(39,174,96,0.25);
}
.stDownloadButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(39,174,96,0.35);
}

/* ----- Metrics ----- */
div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.70);
    backdrop-filter: blur(4px);
    border-radius: 18px;
    padding: 1.2rem 1.2rem;
    border: 1px solid rgba(255,255,255,0.50);
    box-shadow: 0 2px 14px rgba(15,26,47,0.04);
}
div[data-testid="stMetric"] label {
    font-weight: 600;
    color: #1f2a44;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-weight: 700;
    color: #0f1a2f;
}

/* ----- DataFrames and tables ----- */
div[data-testid="stDataFrame"], div[data-testid="stTable"] {
    border-radius: 18px;
    overflow: hidden;
    border: 1px solid #e2e8f0;
    box-shadow: 0 2px 12px rgba(0,0,0,0.03);
}

/* ----- Alerts ----- */
div[data-testid="stAlert"] {
    border-radius: 16px;
    border-left: 6px solid;
    background: rgba(255,255,255,0.70);
    backdrop-filter: blur(4px);
}

/* ----- Banner (hero) ----- */
.app-banner {
    background: linear-gradient(135deg, #1a2a47 0%, #2c4e7a 100%);
    padding: 1.8rem 2.4rem;
    border-radius: 28px;
    color: white;
    margin-bottom: 2rem;
    box-shadow: 0 12px 40px rgba(26,42,71,0.15);
    position: relative;
    overflow: hidden;
}
.app-banner::after {
    content: '';
    position: absolute;
    top: -60%;
    right: -10%;
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(255,255,255,0.06) 0%, transparent 70%);
    border-radius: 50%;
}
.app-banner h1 {
    color: white !important;
    margin: 0;
    font-size: 1.8rem;
    font-weight: 700;
    position: relative;
    z-index: 1;
}
.app-banner p {
    color: #b8d0f0;
    margin: 0.3rem 0 0 0;
    opacity: 0.9;
    position: relative;
    z-index: 1;
    font-weight: 400;
}

/* ----- Login card (centered) ----- */
.login-card {
    background: rgba(255,255,255,0.92);
    backdrop-filter: blur(12px);
    border-radius: 32px;
    padding: 2.8rem 3.2rem;
    box-shadow: 0 24px 60px rgba(15,26,47,0.10);
    border: 1px solid rgba(255,255,255,0.70);
}

/* ----- Risk cards (AI) ----- */
.risk-card {
    border-radius: 16px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.6rem;
    font-weight: 500;
    border-left: 6px solid;
    background: rgba(255,255,255,0.60);
    backdrop-filter: blur(4px);
    box-shadow: 0 2px 10px rgba(0,0,0,0.02);
}

/* ----- Upload box ----- */
.upload-box {
    background: rgba(255,255,255,0.60);
    backdrop-filter: blur(4px);
    border-radius: 20px;
    padding: 2rem;
    border: 2px dashed #4f7eb3;
    margin-bottom: 1.5rem;
}

/* ----- Tabs ----- */
.stTabs [data-baseweb="tab-list"] button {
    font-weight: 600;
    color: #2c3e50;
    padding: 0.5rem 1.2rem;
    border-radius: 12px 12px 0 0;
}
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
    color: #1a2a47;
    border-bottom: 3px solid #4f7eb3;
    background: rgba(79,126,179,0.05);
}

/* ----- Footer (custom) ----- */
.custom-footer {
    margin-top: 3rem;
    padding: 1rem 0;
    text-align: center;
    font-size: 0.8rem;
    color: #6b7a8f;
    border-top: 1px solid rgba(15,26,47,0.06);
}

/* ----- Miscellaneous improvements ----- */
.metric-card {
    background: rgba(255,255,255,0.70);
    backdrop-filter: blur(4px);
    border-radius: 18px;
    padding: 1.2rem;
    border: 1px solid rgba(255,255,255,0.50);
    box-shadow: 0 2px 14px rgba(15,26,47,0.04);
}
.stSpinner > div {
    border-top-color: #4f7eb3 !important;
}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# SESSION STATE
# =============================================================================
if "user" not in st.session_state:
    st.session_state.user = None
if "jwt_token" not in st.session_state:
    st.session_state.jwt_token = None
if "form_key" not in st.session_state:
    st.session_state.form_key = 0
if "refresh_delete" not in st.session_state:
    st.session_state.refresh_delete = False
if "reset_student_select" not in st.session_state:
    st.session_state.reset_student_select = False
# Font cache – will be set by get_unicode_fonts()
if "font_regular" not in st.session_state:
    st.session_state.font_regular = None
if "font_bold" not in st.session_state:
    st.session_state.font_bold = None

# Upload page persistence
if "uploaded_file_bytes" not in st.session_state:
    st.session_state.uploaded_file_bytes = None
if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None
if "parsed_classes" not in st.session_state:
    st.session_state.parsed_classes = None
if "upload_fmt" not in st.session_state:
    st.session_state.upload_fmt = None
if "upload_imported_classes" not in st.session_state:
    st.session_state.upload_imported_classes = set()

def reset_form():
    st.session_state.form_key += 1

def generate_jwt(user):
    payload = {
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "exp": dt.datetime.now(dt.timezone.utc) + timedelta(minutes=TOKEN_EXPIRATION_MINUTES)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_jwt(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        st.error("Session expired. Please login again.")
        return None
    except jwt.InvalidTokenError:
        st.error("Invalid session.")
        return None

def logout():
    st.session_state.user = None
    st.session_state.jwt_token = None
    st.rerun()

def _banner(icon, title, sub):
    st.markdown(f'<div class="app-banner"><h1>{icon} {title}</h1><p>{sub}</p></div>',
                unsafe_allow_html=True)

def _sidebar_user(icon, role):
    st.sidebar.markdown(
        f"""
        <div class="sidebar-profile">
            <div class="avatar">{icon}</div>
            <div class="name">{st.session_state.user['full_name']}</div>
            <div class="role">{role.upper()}</div>
        </div>
        <hr/>
        """,
        unsafe_allow_html=True
    )

# =============================================================================
# HELPER: clean DataFrame (safe, NumPy engine)
# =============================================================================
def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str)
    for col in df.columns:
        if df[col].dtype == 'object':
            numeric = pd.to_numeric(df[col], errors='coerce', downcast='float')
            if numeric.notna().mean() > 0.3:
                df[col] = numeric
            else:
                df[col] = df[col].astype(str).replace(['nan', 'None'], '')
    return df

# =============================================================================
# CACHED DATABASE QUERIES (reduce memory pressure)
# =============================================================================
@st.cache_data(ttl=600)
def cached_get_all_students(grade=None, stream_id=None, class_section=None):
    return db.get_all_students(grade=grade, stream_id=stream_id, class_section=class_section)

@st.cache_data(ttl=600)
def cached_get_marks_for_student(reg_no, year=None):
    return db.get_marks_for_student(reg_no, year=year)

@st.cache_data(ttl=600)
def cached_get_career_cutoffs(career_id):
    return db.get_career_cutoffs(career_id)

@st.cache_data(ttl=600)
def cached_get_grade_year_averages():
    return db.get_grade_year_averages()

@st.cache_data(ttl=600)
def cached_get_class_subject_averages(grade, class_section, year):
    return db.get_class_subject_averages(grade, class_section, year)

# =============================================================================
# LOGIN SCREEN
# =============================================================================
def login_screen():
    _banner("🏫", "Student Performance & Marks System", "Login as Admin or Counselling Teacher")
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        with st.form(f"login_form_{st.session_state.form_key}"):
            st.markdown("#### 🔐 Sign in")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                user = db.verify_login(username.strip(), password)
                if user:
                    st.session_state.user = dict(user)
                    st.session_state.jwt_token = generate_jwt(dict(user))
                    st.success("✅ Login successful!")
                    reset_form()
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password.")
        st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# PDF GENERATION FUNCTIONS (for student report and marks report)
# =============================================================================
def generate_student_pdf(student, avg_marks, ai_plan, ai_summary, fig1, fig2=None):
    """Generate a PDF report using fpdf2 with Unicode support (DejaVuSans or fallback)."""
    regular_path, bold_path = get_unicode_fonts()
    if not os.path.exists(regular_path) or not os.path.exists(bold_path):
        raise FontNotFoundError(f"Font files missing: reg={regular_path}, bold={bold_path}")

    pdf = FPDF()
    try:
        pdf.add_font('UniFont', '', regular_path)
        pdf.add_font('UniFont', 'B', bold_path)
    except Exception as e:
        raise FontNotFoundError(f"Failed to add font: {e}") from e

    pdf.set_font('UniFont', size=12)
    pdf.add_page()

    # Title – bold
    pdf.set_font('UniFont', 'B', 16)
    pdf.cell(0, 10, "Student Performance Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.set_font('UniFont', size=12)
    pdf.ln(5)

    # Student info
    info = (f"Registration: {student['reg_no']}\n"
            f"Name: {student['name']}\n"
            f"Grade: {student['grade']} {student['class_section']}\n"
            f"Stream: {student.get('stream_name', 'N/A')}\n"
            f"Career Dream: {student.get('career_name', 'None')}")
    pdf.multi_cell(0, 6, info)
    pdf.ln(5)

    # Average marks table
    pdf.set_font('UniFont', 'B', 12)
    pdf.cell(0, 8, "Average Marks by Subject", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font('UniFont', size=10)
    if avg_marks:
        pdf.cell(80, 6, "Subject", border=1)
        pdf.cell(40, 6, "Average Marks", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        for subj, mark in sorted(avg_marks.items(), key=lambda x: -x[1]):
            pdf.cell(80, 6, subj, border=1)
            pdf.cell(40, 6, f"{mark:.1f}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)

    # Insert figure 1 if available
    if fig1:
        img_path = tempfile.mktemp(suffix=".png")
        fig1.savefig(img_path, format='png', dpi=150, bbox_inches='tight')
        pdf.image(img_path, x=10, w=190)
        try:
            os.unlink(img_path)
        except:
            pass
        pdf.add_page()

    # AI plan
    if ai_plan:
        pdf.set_font('UniFont', 'B', 12)
        pdf.cell(0, 8, f"AI Career-Readiness — {student.get('career_name', '')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font('UniFont', size=10)
        pdf.multi_cell(0, 5, ai_summary)
        pdf.ln(4)
        pdf.cell(40, 6, "Subject", border=1)
        pdf.cell(30, 6, "Your Marks", border=1)
        pdf.cell(30, 6, "Cutoff", border=1)
        pdf.cell(30, 6, "Status", border=1)
        pdf.cell(50, 6, "Recommendation", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        for p in ai_plan:
            pdf.cell(40, 6, p['subject'], border=1)
            pdf.cell(30, 6, f"{p['current']:.1f}", border=1)
            pdf.cell(30, 6, f"{p['cutoff']:.1f}", border=1)
            pdf.cell(30, 6, p['status'], border=1)
            pdf.cell(50, 6, p['message'], border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output(dest='S'))

def generate_marks_pdf(student, marks_df, title):
    """
    Generate a PDF with a marks table for a student.
    marks_df is a DataFrame with columns: subject_name, marks (and optionally term, year)
    """
    regular_path, bold_path = get_unicode_fonts()
    if not os.path.exists(regular_path) or not os.path.exists(bold_path):
        raise FontNotFoundError(f"Font files missing: reg={regular_path}, bold={bold_path}")

    pdf = FPDF()
    pdf.add_font('UniFont', '', regular_path)
    pdf.add_font('UniFont', 'B', bold_path)
    pdf.set_font('UniFont', size=12)
    pdf.add_page()

    # Title
    pdf.set_font('UniFont', 'B', 16)
    pdf.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.set_font('UniFont', size=12)
    pdf.ln(5)

    # Student info
    info = (f"Name: {student['name']}\n"
            f"Registration: {student['reg_no']}\n"
            f"Grade: {student['grade']} {student['class_section']}")
    pdf.multi_cell(0, 6, info)
    pdf.ln(5)

    # Table header
    pdf.set_font('UniFont', 'B', 10)
    pdf.cell(80, 6, "Subject", border=1)
    pdf.cell(40, 6, "Marks", border=1)
    # If available, add term/year columns
    if 'term' in marks_df.columns:
        pdf.cell(30, 6, "Term", border=1)
    if 'year' in marks_df.columns:
        pdf.cell(30, 6, "Year", border=1)
    pdf.ln()

    # Table rows
    pdf.set_font('UniFont', size=10)
    for _, row in marks_df.iterrows():
        pdf.cell(80, 6, str(row['subject_name']), border=1)
        pdf.cell(40, 6, f"{row['marks']:.1f}" if isinstance(row['marks'], (int, float)) else str(row['marks']), border=1)
        if 'term' in marks_df.columns:
            pdf.cell(30, 6, str(row['term']), border=1)
        if 'year' in marks_df.columns:
            pdf.cell(30, 6, str(row['year']), border=1)
        pdf.ln()

    return bytes(pdf.output(dest='S'))

# =============================================================================
# AI INSIGHT (shared) – IMPROVED VISUALISATION + PDF DOWNLOAD
# =============================================================================
def render_student_chart_and_ai(student, year_filter=None):
    marks_rows = cached_get_marks_for_student(student["reg_no"], year=year_filter)
    if not marks_rows:
        st.info("No marks recorded yet.")
        return None, None
    avg = ai_advisor.average_marks_by_subject(marks_rows)

    # ---- 1. Show a table with averages ----
    st.subheader("Average Marks by Subject")
    avg_df = pd.DataFrame(list(avg.items()), columns=["Subject", "Average Marks"])
    st.dataframe(avg_df, use_container_width=True, hide_index=True)

    # ---- 2. Horizontal bar chart ----
    fig1, ax1 = plt.subplots(figsize=(8, max(4, len(avg) * 0.5)))
    subjects = list(avg.keys())
    values = list(avg.values())
    sorted_pairs = sorted(zip(values, subjects), reverse=True)
    values, subjects = zip(*sorted_pairs) if sorted_pairs else ([], [])
    bars = ax1.barh(subjects, values, color="#4C72B0")
    ax1.set_xlim(0, 100)
    ax1.set_xlabel("Average Marks")
    for bar, val in zip(bars, values):
        ax1.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
                f"{val:.1f}", va='center', fontsize=9)
    fig1.tight_layout()
    st.pyplot(fig1)

    # ---- 3. AI Career readiness ----
    ai_plan = ai_summary = None
    fig2 = None
    if student.get("career_id"):
        cuts = cached_get_career_cutoffs(student["career_id"])
        if cuts:
            ai_plan = ai_advisor.build_improvement_plan(avg, cuts)
            ai_summary = ai_advisor.overall_summary(ai_plan)
            st.subheader(f"AI Career-Readiness — {student.get('career_name', '')}")
            st.info(ai_summary)

            # Horizontal bar chart for plan
            fig2, ax2 = plt.subplots(figsize=(8, max(4, len(ai_plan) * 0.5)))
            labels = [p["subject"] for p in ai_plan]
            current = [p["current"] for p in ai_plan]
            cutoffs = [p["cutoff"] for p in ai_plan]
            y_pos = range(len(labels))
            bar_width = 0.35
            ax2.barh([i - bar_width/2 for i in y_pos], current, height=bar_width,
                     label="Student", color="#4C72B0")
            ax2.barh([i + bar_width/2 for i in y_pos], cutoffs, height=bar_width,
                     label="Cutoff", color="#DD8452")
            ax2.set_yticks(y_pos)
            ax2.set_yticklabels(labels)
            ax2.set_xlim(0, 100)
            ax2.legend()
            fig2.tight_layout()
            st.pyplot(fig2)

            # Status messages
            for p in ai_plan:
                icon = {"On Track": "✅", "Almost There": "🟡", "Needs Improvement": "🟠", "Critical": "🔴"}[p["status"]]
                st.write(f"{icon} **{p['subject']}** — {p['message']}")

    # ---- 4. PDF Download Button (fpdf2) ----
    if st.button("📄 Download Performance Report (PDF)", key="pdf_btn"):
        with st.spinner("Generating PDF..."):
            try:
                pdf_bytes = generate_student_pdf(student, avg, ai_plan, ai_summary, fig1, fig2)
                st.download_button(
                    label="⬇️ Click to download",
                    data=pdf_bytes,
                    file_name=f"{student['reg_no']}_performance_report.pdf",
                    mime="application/pdf",
                    key="pdf_download"
                )
                st.success("PDF ready for download!")
            except FontNotFoundError as e:
                st.error(f"❌ Could not generate PDF: {e}")
            except Exception as e:
                st.error(f"❌ Could not generate PDF: {e}")

    # Close figures to free memory
    plt.close(fig1)
    if fig2:
        plt.close(fig2)
    gc.collect()

    return ai_plan, ai_summary

# =============================================================================
# AI PREDICTION PAGE (shared)
# =============================================================================
def render_prediction_page():
    st.header("AI Grade Performance Prediction")
    st.caption("Linear-regression model trained on all marks data. More years = better accuracy. Grades 10 & 11 are O/L critical.")
    rows = cached_get_grade_year_averages()
    if not rows:
        st.warning("No marks data yet.")
        return
    results = pai.predict_grade_performance(rows, 2)
    ol_summary = pai.ol_risk_summary(results)
    st.info(f"O/L Outlook: {ol_summary}")
    st.markdown("---")
    with_data = [r for r in results if r["data_points"] > 0]
    cols = st.columns(min(len(with_data), 4))
    for i, r in enumerate(with_data[:4]):
        col = pai.RISK_COLORS[r["status"]]
        with cols[i]:
            st.markdown(
                f"<div class='risk-card' style='border-color:{col};background:{col}18;'>"
                f"<b>Grade {r['grade']}</b><br/>"
                f"<span style='font-size:1.4rem;color:{col};'>{r['predicted_avg']}</span><br/>"
                f"<small>{r['status']} | {r['confidence']} confidence</small></div>",
                unsafe_allow_html=True
            )
    if len(with_data) > 4:
        cols2 = st.columns(min(len(with_data) - 4, 4))
        for i, r in enumerate(with_data[4:8]):
            col = pai.RISK_COLORS[r["status"]]
            with cols2[i]:
                st.markdown(
                    f"<div class='risk-card' style='border-color:{col};background:{col}18;'>"
                    f"<b>Grade {r['grade']}</b><br/>"
                    f"<span style='font-size:1.4rem;color:{col};'>{r['predicted_avg']}</span><br/>"
                    f"<small>{r['status']} | {r['confidence']} confidence</small></div>",
                    unsafe_allow_html=True
                )
    st.subheader("Current vs Predicted Average by Grade")
    fig, ax = plt.subplots(figsize=(10, 4))
    x = np.arange(8)
    w = 0.38
    cur = [r["current_avg"] or 0 for r in results]
    pred = [r["predicted_avg"] or 0 for r in results]
    bcol = [pai.RISK_COLORS.get(r["status"], "#aaa") for r in results]
    ax.bar(x - w/2, cur, w, label="Current Avg", color="#4C72B0", alpha=0.85)
    ax.bar(x + w/2, pred, w, label="Predicted Avg", color=bcol, alpha=0.85)
    ax.axhline(75, color="#2fa66b", linestyle="--", linewidth=1.2, label="Strong (75)")
    ax.axhline(60, color="#4C72B0", linestyle=":", linewidth=1.2, label="On Track (60)")
    ax.axhline(45, color="#f0a500", linestyle="-.", linewidth=1.2, label="Warning (45)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"Gr {r['grade']}" for r in results])
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)
    gc.collect()

    st.subheader("Grade Trend Lines (Historical + Projected)")
    fig2, ax2 = plt.subplots(figsize=(10, 4))
    colors = plt.cm.tab10.colors
    for i, r in enumerate(with_data):
        col = colors[i % len(colors)]
        py = [p[0] for p in r["projection_series"]]
        pm = [p[1] for p in r["projection_series"]]
        hy = [h[0] for h in r["historical"]]
        hm = [h[1] for h in r["historical"]]
        ax2.scatter(hy, hm, color=col, s=40, zorder=3)
        if len(py) > 1:
            ax2.plot(py, pm, color=col, linewidth=2,
                     linestyle="--" if r["data_points"] == 1 else "-",
                     label=f"Grade {r['grade']}")
    ax2.set_ylim(0, 100)
    ax2.set_xlabel("Year")
    ax2.set_ylabel("Avg Marks")
    ax2.legend(fontsize=8, ncol=4, loc="lower right")
    fig2.tight_layout()
    st.pyplot(fig2)
    plt.close(fig2)
    gc.collect()

    st.subheader("Grade Details")
    table_data = [{
        "Grade": r["grade"],
        "Data Years": r["data_points"],
        "Current Avg": r["current_avg"] or "-",
        "Predicted": r["predicted_avg"] or "-",
        "Trend/yr": r["trend_slope"] or "-",
        "Status": r["status"],
        "Confidence": r["confidence"]
    } for r in results]
    df_table = clean_dataframe(pd.DataFrame(table_data))
    st.dataframe(df_table, use_container_width=True, hide_index=True)

    for r in with_data:
        col = pai.RISK_COLORS[r["status"]]
        st.markdown(
            f"<div class='risk-card' style='border-color:{col};background:{col}12;'>{r['message']}</div>",
            unsafe_allow_html=True
        )
    today = datetime.date.today().strftime("%d %B %Y")
    pdf_b = pdf_report.generate_prediction_report(results, ol_summary, today)
    st.download_button("Download AI Prediction Report (PDF)", pdf_b,
                       f"grade_prediction_{datetime.date.today()}.pdf", "application/pdf")

# =============================================================================
# CLASS‑WISE PERFORMANCE (shared)
# =============================================================================
def render_class_performance():
    st.header("Class-wise Performance")
    years = sorted({m["year"] for m in db.run_query("SELECT DISTINCT year FROM marks", fetch=True)}, reverse=True)
    if not years:
        st.info("No marks data yet.")
        return
    sel_year = st.selectbox("Year", years, key="cwp_year")
    rows = db.get_grade_class_averages(sel_year)
    if not rows:
        st.info("No data for this year.")
        return
    df = pd.DataFrame(rows)
    df["avg_marks"] = df["avg_marks"].round(2)
    df.rename(columns={
        "grade": "Grade",
        "class_section": "Class",
        "avg_marks": "Avg Marks",
        "student_count": "Students"
    }, inplace=True)
    df = clean_dataframe(df)
    st.dataframe(df, use_container_width=True, hide_index=True)

    for grade in sorted(df["Grade"].unique()):
        gdf = df[df["Grade"] == grade].sort_values("Class")
        if gdf.empty:
            continue
        fig, ax = plt.subplots(figsize=(max(4, len(gdf) * 0.8), 3))
        bars = ax.bar(gdf["Class"], gdf["Avg Marks"], color="#4C72B0", width=0.5)
        ax.set_ylim(0, 100)
        ax.set_title(f"Grade {grade} — Class Average ({sel_year})")
        ax.set_ylabel("Avg Marks")
        for bar, val in zip(bars, gdf["Avg Marks"]):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f"{val:.1f}", ha="center", va="bottom", fontsize=9)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
        gc.collect()

    st.markdown("---")
    st.subheader("Drill Into a Class")
    grade_opts = [f"Grade {g}" for g in sorted(df["Grade"].unique())]
    sel_grade_str = st.selectbox("Grade", grade_opts, key="cwp_grade")
    sel_grade_int = int(sel_grade_str.split()[1])
    gdf2 = df[df["Grade"] == sel_grade_int]
    sel_class = st.selectbox("Class Section", gdf2["Class"].tolist(), key="cwp_class")
    row2 = next((r for r in rows if r.get("grade") == sel_grade_int and r.get("class_section") == sel_class), None)

    subj_rows = cached_get_class_subject_averages(sel_grade_int, sel_class, sel_year)
    if subj_rows:
        sdf = pd.DataFrame(subj_rows)
        sdf["avg_marks"] = sdf["avg_marks"].round(2)
        fig3, ax3 = plt.subplots(figsize=(max(5, len(sdf) * 0.8), 3.5))
        ax3.barh(sdf["subject_name"], sdf["avg_marks"], color="#4C72B0")
        ax3.set_xlim(0, 100)
        ax3.set_xlabel("Average Marks")
        ax3.set_title(f"Grade {sel_grade_int}{sel_class} Subject Averages ({sel_year})")
        fig3.tight_layout()
        st.pyplot(fig3)
        plt.close(fig3)
        gc.collect()
        sdf_clean = clean_dataframe(sdf[["subject_name", "avg_marks", "n"]].rename(
            columns={"subject_name": "Subject", "avg_marks": "Avg Marks", "n": "Count"}))
        st.dataframe(sdf_clean, use_container_width=True, hide_index=True)
        ca = row2["avg_marks"] if row2 else 0
        pdf_cl = pdf_report.generate_class_report(
            sel_grade_int, sel_class, sel_year, ca,
            db.get_class_subject_averages(sel_grade_int, sel_class, sel_year)
        )
        st.download_button(
            f"Download Grade {sel_grade_int}{sel_class} Report (PDF)",
            data=pdf_cl,
            file_name=f"grade{sel_grade_int}{sel_class}_{sel_year}_class_report.pdf",
            mime="application/pdf",
        )

# =============================================================================
# SAFE TEMP FILE DELETION
# =============================================================================
def safe_delete_temp_file(path, max_retries=5):
    gc.collect()
    for attempt in range(max_retries):
        try:
            if os.path.exists(path):
                os.unlink(path)
            return True
        except PermissionError:
            time.sleep(0.15 * (attempt + 1))
            gc.collect()
    st.warning(f"Could not delete temporary file: {path}")
    return False

# =============================================================================
# EXCEL UPLOAD (shared) – WITH PERSISTENCE
# =============================================================================
def render_upload_page():
    st.header("Bulk Upload Marks from Excel")
    st.markdown("""
    <div class="upload-box">
    <b>Supported formats:</b><br>
    - <b>Grades 6-9</b> — Junior class sheets (e.g. <code>First__team__Test_8D_2026.xlsm</code>)<br>
    - <b>Grades 10-11</b> — O/L senior class sheets (e.g. <code>2026__grade_11_First_Term___S1.xlsm</code>)<br>
    </div>
    """, unsafe_allow_html=True)

    # --- File upload widget ---
    uploaded = st.file_uploader("Upload Excel file (.xlsx or .xlsm)",
                                type=["xlsx", "xlsm"], key="ul_file_widget")

    # If new file uploaded, store its bytes and clear previous parsed data
    if uploaded is not None:
        if st.session_state.uploaded_file_bytes != uploaded.getvalue() or st.session_state.uploaded_file_name != uploaded.name:
            st.session_state.uploaded_file_bytes = uploaded.getvalue()
            st.session_state.uploaded_file_name = uploaded.name
            st.session_state.parsed_classes = None
            st.session_state.upload_fmt = None
            st.session_state.upload_imported_classes = set()
            st.rerun()

    # --- Override controls (stored in session state for persistence) ---
    col1, col2, col3 = st.columns(3)
    with col1:
        hint_grade = st.number_input("Grade hint (optional)", 6, 13, 8, step=1, key="ul_grade_hint")
    with col2:
        override_term = st.selectbox("Term override", ["Auto-detect", 1, 2, 3], key="ul_term_override")
    with col3:
        override_year = st.number_input("Year override", 2020, 2035, 2026, step=1, key="ul_year_override")

    # --- If we have a stored file, parse and display ---
    if st.session_state.uploaded_file_bytes is not None:
        file_name = st.session_state.uploaded_file_name
        suffix = ".xlsm" if file_name.lower().endswith(".xlsm") else ".xlsx"

        # Parse only once
        if st.session_state.parsed_classes is None:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(st.session_state.uploaded_file_bytes)
                    tmp_path = tmp.name
                fmt, classes = excel_parser.detect_and_parse(tmp_path, hint_grade or None)
                safe_delete_temp_file(tmp_path)
                st.session_state.parsed_classes = classes
                st.session_state.upload_fmt = fmt
            except Exception as e:
                st.error(f"Parse error: {e}")
                st.session_state.parsed_classes = []
                st.session_state.upload_fmt = None

        classes = st.session_state.parsed_classes
        fmt = st.session_state.upload_fmt

        if not classes:
            st.warning("No class sheets found in file.")
        else:
            st.success(f"Detected format: **{fmt.upper()}** | {len(classes)} class(es) found")

            # Display each class with import button
            for idx, cls_data in enumerate(classes):
                grade = cls_data.get("grade") or hint_grade
                cls = cls_data.get("class_section", "A")
                term_val = cls_data.get("term") or 1
                if override_term != "Auto-detect":
                    term_val = int(override_term)
                year = cls_data.get("year") or override_year
                stus = cls_data.get("students", [])
                term_val = int(term_val)

                # Create a unique key for this class
                class_key = f"{grade}_{cls}_{term_val}_{year}"

                with st.expander(f"Grade {grade}{cls} | Term {term_val} {year} | {len(stus)} students", expanded=False):
                    if not stus:
                        st.info("No student rows found.")
                        continue
                    preview_df = pd.DataFrame([
                        {"Name": s["name"], "Subjects": len(s["marks"]), "Sample Marks": str(list(s["marks"].items())[:3])}
                        for s in stus[:10]
                    ])
                    st.dataframe(clean_dataframe(preview_df), use_container_width=True, hide_index=True)
                    if len(stus) > 10:
                        st.caption(f"... and {len(stus)-10} more students")

                    # Check if this class has already been imported
                    already_imported = class_key in st.session_state.upload_imported_classes
                    if already_imported:
                        st.success("✅ Already imported")
                    else:
                        if st.button(f"Import Grade {grade}{cls}", key=f"imp_{class_key}"):
                            imported = skipped = 0
                            with st.spinner("Importing..."):
                                for stu in stus:
                                    try:
                                        reg_no = db.upsert_student_bulk(stu["name"], grade, cls, year)
                                        for subj_name, mark_val in stu["marks"].items():
                                            subj_id = db.get_or_create_subject(subj_name)
                                            db.save_mark(reg_no, subj_id, term_val, year, grade, mark_val)
                                        imported += 1
                                    except Exception as ex:
                                        st.warning(f"Skipped {stu['name']}: {ex}")
                                        skipped += 1
                            st.success(f"✅ Imported {imported} students, skipped {skipped}.")
                            st.session_state.upload_imported_classes.add(class_key)
                            st.cache_data.clear()
                            st.rerun()

            # Option to clear the file
            if st.button("🗑️ Clear uploaded file", key="clear_upload"):
                st.session_state.uploaded_file_bytes = None
                st.session_state.uploaded_file_name = None
                st.session_state.parsed_classes = None
                st.session_state.upload_fmt = None
                st.session_state.upload_imported_classes = set()
                st.rerun()

# =============================================================================
# ADMIN: DELETE MARKS BY GRADE & YEAR
# =============================================================================
def render_delete_marks():
    st.header("🗑️ Delete Marks by Grade & Year")
    st.caption("Permanently remove all marks for a specific grade and academic year. This action cannot be undone.")
    col1, col2 = st.columns(2)
    with col1:
        grade = st.selectbox("Select Grade", db.GRADES, key="del_grade")
    with col2:
        years = [row["year"] for row in db.run_query("SELECT DISTINCT year FROM marks ORDER BY year DESC", fetch=True)]
        if not years:
            st.info("No marks found in the database.")
            return
        year = st.selectbox("Select Year", years, key="del_year")

    count_query = """
        SELECT COUNT(*) as cnt FROM marks m
        JOIN students s ON m.reg_no = s.reg_no
        WHERE s.grade = ? AND m.year = ?
    """
    count_result = db.run_query(count_query, (grade, year), fetch=True)
    count = count_result[0]["cnt"] if count_result else 0
    st.metric("Marks to be deleted", count)

    if count == 0:
        st.info("No marks found for this grade and year.")
        return

    st.warning(f"⚠️ You are about to delete **{count}** mark entries for Grade {grade} in {year}.")
    confirm = st.checkbox("I understand this action is permanent and cannot be undone.")
    if confirm:
        if st.button("🗑️ Delete All Marks", type="primary"):
            delete_query = """
                DELETE FROM marks
                WHERE reg_no IN (SELECT reg_no FROM students WHERE grade = ?)
                AND year = ?
            """
            try:
                db.run_query(delete_query, (grade, year))
                st.success(f"✅ Successfully deleted all marks for Grade {grade} in {year}.")
                st.session_state.refresh_delete = True
            except Exception as e:
                st.error(f"❌ Error during deletion: {e}")
    else:
        st.info("Please confirm the deletion checkbox above to enable the delete button.")

# =============================================================================
# ADMIN: DELETE SINGLE STUDENT
# =============================================================================
def render_delete_student():
    st.header("🗑️ Delete Student (Permanent)")
    st.caption("Select a student to permanently delete their record and all associated marks. This action cannot be undone.")

    students = cached_get_all_students()
    if not students:
        st.info("No students found in the database.")
        return

    student_options = {}
    for s in students:
        label = f"{s['reg_no']} - {s['name']} (Grade {s['grade']}{s['class_section']})"
        student_options[label] = s['reg_no']

    selected_label = st.selectbox("Select Student", list(student_options.keys()))
    reg_no = student_options[selected_label]
    student_data = next((s for s in students if s['reg_no'] == reg_no), None)
    if not student_data:
        st.error("Student not found.")
        return

    st.subheader("Student Details")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Registration No:** {student_data['reg_no']}")
        st.write(f"**Name:** {student_data['name']}")
    with col2:
        st.write(f"**Grade:** {student_data['grade']}")
        st.write(f"**Class:** {student_data['class_section']}")
        st.write(f"**Stream:** {student_data.get('stream_name', 'N/A')}")
        st.write(f"**Career:** {student_data.get('career_name', 'None')}")

    marks = cached_get_marks_for_student(reg_no)
    if marks:
        st.subheader(f"Marks ({len(marks)} entries)")
        marks_df = clean_dataframe(pd.DataFrame(marks))
        st.dataframe(marks_df, use_container_width=True, hide_index=True)
    else:
        st.info("No marks recorded for this student.")

    st.warning(f"⚠️ You are about to permanently delete **{student_data['name']}** (Reg: {reg_no}) and all their {len(marks)} mark entries.")
    confirm = st.checkbox("I understand this action is permanent and cannot be undone.")

    if confirm:
        if st.button("🗑️ Delete Student Permanently", type="primary"):
            try:
                db.run_query("DELETE FROM marks WHERE reg_no = ?", (reg_no,))
                db.run_query("DELETE FROM students WHERE reg_no = ?", (reg_no,))
                st.success(f"✅ Successfully deleted student {student_data['name']} and all their marks.")
                st.session_state.refresh_delete = True
            except Exception as e:
                st.error(f"❌ Error during deletion: {e}")
    else:
        st.info("Please confirm the deletion checkbox above to enable the delete button.")

# =============================================================================
# ADMIN: BULK DELETE STUDENTS BY GRADE & YEAR
# =============================================================================
def render_bulk_delete_students():
    st.header("🗑️ Delete Students (Bulk) by Grade & Year")
    st.caption("Permanently delete all students who have marks in the selected grade and year. This also removes all their marks.")

    grades = db.GRADES
    years = [row["year"] for row in db.run_query("SELECT DISTINCT year FROM marks ORDER BY year DESC", fetch=True)]
    if not years:
        st.info("No marks data found. Cannot perform bulk deletion.")
        return

    col1, col2 = st.columns(2)
    with col1:
        grade = st.selectbox("Select Grade", grades, key="bulk_grade")
    with col2:
        year = st.selectbox("Select Year", years, key="bulk_year")

    count_query = """
        SELECT COUNT(DISTINCT s.reg_no) as student_count, COUNT(m.id) as mark_count
        FROM students s
        JOIN marks m ON s.reg_no = m.reg_no
        WHERE s.grade = ? AND m.year = ?
    """
    result = db.run_query(count_query, (grade, year), fetch=True)
    student_count = result[0]["student_count"] if result else 0
    mark_count = result[0]["mark_count"] if result else 0

    st.metric("Students to delete", student_count)
    st.metric("Marks to delete", mark_count)

    if student_count == 0:
        st.info(f"No students found with marks in Grade {grade} for year {year}.")
        return

    sample_query = """
        SELECT DISTINCT s.reg_no, s.name, s.grade, s.class_section
        FROM students s
        JOIN marks m ON s.reg_no = m.reg_no
        WHERE s.grade = ? AND m.year = ?
        LIMIT 10
    """
    sample = db.run_query(sample_query, (grade, year), fetch=True)
    if sample:
        st.subheader("Sample students to be deleted (up to 10)")
        sample_df = clean_dataframe(pd.DataFrame(sample))
        st.dataframe(sample_df, use_container_width=True, hide_index=True)

    st.warning(f"⚠️ You are about to permanently delete **{student_count} students** and **{mark_count} marks** for Grade {grade} in {year}.")
    confirm = st.checkbox("I understand this action is permanent and cannot be undone.")

    if confirm:
        if st.button("🗑️ Delete All Students and Marks", type="primary"):
            try:
                regs_query = """
                    SELECT DISTINCT s.reg_no
                    FROM students s
                    JOIN marks m ON s.reg_no = m.reg_no
                    WHERE s.grade = ? AND m.year = ?
                """
                regs = db.run_query(regs_query, (grade, year), fetch=True)
                reg_list = [r["reg_no"] for r in regs]
                if not reg_list:
                    st.info("No students found.")
                    return
                placeholders = ','.join(['?'] * len(reg_list))
                delete_marks_query = f"DELETE FROM marks WHERE reg_no IN ({placeholders})"
                db.run_query(delete_marks_query, reg_list)
                delete_students_query = f"DELETE FROM students WHERE reg_no IN ({placeholders})"
                db.run_query(delete_students_query, reg_list)
                st.success(f"✅ Successfully deleted {student_count} students and {mark_count} marks for Grade {grade} in {year}.")
                st.session_state.refresh_delete = True
            except Exception as e:
                st.error(f"❌ Error during deletion: {e}")
    else:
        st.info("Please confirm the deletion checkbox above to enable the delete button.")

# =============================================================================
# ADMIN: USER MANAGEMENT
# =============================================================================
def render_user_management():
    st.header("👥 User Management")
    st.caption("Create, view, edit and delete Admin / Teacher accounts")
    tabs = st.tabs(["View Users", "Add New User", "Edit User", "Delete User"])

    with tabs[0]:
        users = db.get_all_users()
        if users:
            df = clean_dataframe(pd.DataFrame(users))
            st.dataframe(df[["username", "full_name", "role", "created_at"]],
                         use_container_width=True, hide_index=True)
        else:
            st.info("No users found.")
    with tabs[1]:
        with st.form(f"add_user_form_{st.session_state.form_key}"):
            st.subheader("Add New User")
            un = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            fn = st.text_input("Full Name")
            role = st.selectbox("Role", ["teacher", "admin"])
            if st.form_submit_button("Create User"):
                if un and pw and fn:
                    if db.add_user(un.strip(), pw, fn.strip(), role):
                        st.success("✅ User created successfully!")
                        reset_form()
                        st.rerun()
                    else:
                        st.error("❌ Failed to create user (username may exist).")
                else:
                    st.error("❌ All fields required.")
    with tabs[2]:
        users = db.get_all_users()
        if users:
            user_dict = {u["username"]: u for u in users}
            sel = st.selectbox("Select user to edit", list(user_dict.keys()))
            u = user_dict[sel]
            with st.form(f"edit_user_form_{st.session_state.form_key}"):
                new_fn = st.text_input("Full Name", value=u["full_name"])
                new_role = st.selectbox("Role", ["teacher", "admin"],
                                      index=0 if u["role"] == "teacher" else 1)
                if st.form_submit_button("Update User"):
                    if db.update_user(u["id"], new_fn, new_role):
                        st.success("✅ User updated successfully!")
                        reset_form()
                        st.rerun()
                    else:
                        st.error("❌ Update failed.")
    with tabs[3]:
        users = db.get_all_users()
        if users:
            del_sel = st.selectbox("Select user to delete", [u["username"] for u in users])
            if st.checkbox("Confirm permanent deletion", key="del_user_confirm"):
                if st.button("Delete User", type="primary"):
                    if db.delete_user(del_sel):
                        st.success("✅ User deleted successfully.")
                        reset_form()
                        st.rerun()
                    else:
                        st.error("❌ Could not delete user.")

# =============================================================================
# ADD / UPDATE STUDENT (shared for Admin & Teacher) – FIXED
# =============================================================================
def render_add_update_student():
    st.header("➕ Add / Update Student")
    st.caption("Select an existing student to edit, or choose 'Add new student' to create a new record.")

    # If we just saved, reset the selectbox to "Add new student"
    if st.session_state.reset_student_select:
        st.session_state.reset_student_select = False
        if "student_select" in st.session_state:
            del st.session_state["student_select"]
        st.rerun()

    # Get all required data
    streams = db.get_streams()
    stream_names = [s["name"] for s in streams]
    all_students = cached_get_all_students()  # this is cached; after save we clear cache

    # Build options for selectbox
    student_options = ["Add new student"]
    student_options.extend([f"{s['reg_no']} - {s['name']}" for s in all_students])

    selected_label = st.selectbox("Select student", student_options, key="student_select")

    # Determine if we are editing an existing student
    selected_student = None
    if selected_label != "Add new student":
        reg_no = selected_label.split(" - ")[0]
        selected_student = next((s for s in all_students if s['reg_no'] == reg_no), None)

    # Get default values
    default_reg = selected_student['reg_no'] if selected_student else ""
    default_name = selected_student['name'] if selected_student else ""
    default_grade = selected_student['grade'] if selected_student else db.GRADES[0]
    default_class = selected_student['class_section'] if selected_student else "A"
    default_stream = selected_student.get('stream_name') if selected_student else stream_names[0] if stream_names else ""
    default_career = selected_student.get('career_name') if selected_student else "-- none --"

    # Stream selection (set to default_stream)
    if stream_names:
        # Ensure default_stream is in list
        stream_index = stream_names.index(default_stream) if default_stream in stream_names else 0
        stream_choice = st.selectbox("Stream", stream_names, index=stream_index)
        stream_id = db.get_stream_id(stream_choice)
        careers = db.get_careers_by_stream(stream_id)
        career_names = ["-- none --"] + [c["name"] for c in careers]
    else:
        stream_choice = None
        stream_id = None
        careers = []
        career_names = ["-- none --"]

    # Grade and Class
    grade_choice = st.selectbox("Grade", [f"Grade {g}" for g in db.GRADES],
                                index=db.GRADES.index(default_grade) if default_grade in db.GRADES else 0)
    class_choice = st.selectbox("Class Section", list("ABCDEFGH"),
                                index=list("ABCDEFGH").index(default_class) if default_class in "ABCDEFGH" else 0)
    grade_val = int(grade_choice.split()[1])

    # Career selection - ensure default_career is in the list
    career_index = career_names.index(default_career) if default_career in career_names else 0
    career_choice = st.selectbox("Career Dream", career_names, index=career_index)

    # Registration No and Name (editable)
    reg_no = st.text_input("Registration Number", value=default_reg)
    name = st.text_input("Student Name", value=default_name)

    # Save button
    if st.button("💾 Save Student", type="primary"):
        if reg_no.strip() and name.strip():
            cid = None
            if career_choice != "-- none --":
                career_obj = next((c for c in careers if c["name"] == career_choice), None)
                if career_obj:
                    cid = career_obj["id"]
            # Upsert student
            db.upsert_student(reg_no.strip(), name.strip(), grade_val, class_choice, stream_id, cid)
            st.success(f"✅ Student {reg_no} saved successfully!")
            # Clear cache so that the select box and other pages see the updated data
            st.cache_data.clear()
            # Set flag to reset the select box to "Add new student"
            st.session_state.reset_student_select = True
            st.rerun()
        else:
            st.error("❌ Registration Number and Name are required.")

# =============================================================================
# ADMIN DASHBOARD
# =============================================================================
def admin_dashboard():
    if st.session_state.get("refresh_delete", False):
        st.session_state.refresh_delete = False
        st.rerun()

    _sidebar_user("🛡️", "Admin")
    page = st.sidebar.radio("Navigate", [
        "📚 Manage Subjects",
        "🎯 Manage Careers & Cutoffs",
        "👥 User Management",
        "📤 Bulk Upload Marks",
        "📊 Student Performance",
        "📈 Class-wise Performance",
        "👥 All Students",
        "🤖 AI Grade Predictions",
        "🗑️ Delete Marks",
        "🗑️ Delete Student",
        "🗑️ Delete Students Bulk",
    ])
    st.sidebar.markdown("<br/>", unsafe_allow_html=True)
    if st.sidebar.button("🚪 Logout"):
        logout()

    _banner("🛡️", "Admin Dashboard", "Manage subjects, careers, uploads and view performance")
    streams = db.get_streams()
    stream_names = [s["name"] for s in streams]

    if page == "👥 User Management":
        render_user_management()
    elif page == "📚 Manage Subjects":
        st.header("Manage Subjects")
        chosen_stream = st.selectbox("Stream", stream_names)
        stream_id = db.get_stream_id(chosen_stream)
        with st.form(f"add_sub_f_{st.session_state.form_key}"):
            ns = st.text_input("New subject name")
            if st.form_submit_button("Add Subject"):
                if ns.strip():
                    db.add_subject(ns.strip(), stream_id)
                    st.success("✅ Subject added!")
                    reset_form()
                    st.rerun()
        subs = db.get_subjects_by_stream(stream_id)
        st.subheader(f"Subjects in {chosen_stream}")
        if not subs:
            st.info("No subjects yet.")
        else:
            for sub in subs:
                with st.expander(f"✏️ {sub['name']}"):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        with st.form(f"es_{sub['id']}"):
                            en = st.text_input("Name", value=sub["name"])
                            if st.form_submit_button("Save"):
                                if en.strip():
                                    db.update_subject(sub["id"], en.strip())
                                    st.success("✅ Updated.")
                                    st.rerun()
                    with c2:
                        mc, cc = db.subject_usage_counts(sub["id"])
                        if mc or cc:
                            st.caption(f"⚠️ {mc} marks, {cc} cutoffs")
                        if st.checkbox("Confirm delete", key=f"cd_{sub['id']}"):
                            if st.button("Delete", key=f"ds_{sub['id']}"):
                                db.delete_subject(sub["id"], cascade=True)
                                st.success("✅ Deleted.")
                                st.rerun()
    elif page == "🎯 Manage Careers & Cutoffs":
        st.header("Manage Career Dreams & Minimum Cutoffs")
        t_view, t_add, t_upd, t_del = st.tabs(["View", "Add", "Update", "Delete"])
        with t_view:
            all_c = db.get_all_careers()
            if all_c:
                df_c = clean_dataframe(pd.DataFrame(all_c).rename(columns={"name": "Career", "stream_name": "Stream", "cutoff_count": "Subjects w/ Cutoffs", "student_count": "Students"}))
                st.dataframe(df_c[["Career", "Stream", "Subjects w/ Cutoffs", "Students"]], use_container_width=True, hide_index=True)
                opts = {f"{c['name']} ({c['stream_name']})": c for c in all_c}
                sel = st.selectbox("Drill into", list(opts.keys()), key="vc")
                rows = cached_get_career_cutoffs(opts[sel]["id"])
                if rows:
                    df_cutoffs = clean_dataframe(pd.DataFrame(rows)[["subject_name", "min_marks"]].rename(columns={"subject_name": "Subject", "min_marks": "Cutoff"}))
                    st.dataframe(df_cutoffs, use_container_width=True, hide_index=True)
            else:
                st.info("No careers yet.")
        with t_add:
            with st.form(f"add_career_form_{st.session_state.form_key}"):
                c_name = st.text_input("Career Name")
                c_stream = st.selectbox("Stream", stream_names)
                if st.form_submit_button("Create Career"):
                    if c_name.strip():
                        stream_id = db.get_stream_id(c_stream)
                        if db.add_career(c_name.strip(), stream_id):
                            st.success("✅ Career created successfully!")
                            reset_form()
                            st.rerun()
                        else:
                            st.error("❌ Failed to create career.")
        with t_upd:
            all_c = db.get_all_careers()
            if all_c:
                opts_upd = {f"{c['name']} ({c['stream_name']})": c for c in all_c}
                sel_upd = st.selectbox("Select career to update", list(opts_upd.keys()), key="upd_career")
                c = opts_upd[sel_upd]
                with st.form(f"upd_career_form_{st.session_state.form_key}"):
                    new_name = st.text_input("New Career Name", value=c["name"])
                    if st.form_submit_button("Update Career"):
                        if db.update_career(c["id"], new_name.strip()):
                            st.success("✅ Career updated!")
                            reset_form()
                            st.rerun()
        with t_del:
            all_c = db.get_all_careers()
            if all_c:
                del_opts = [f"{c['name']} ({c['stream_name']})" for c in all_c]
                del_sel = st.selectbox("Select career to delete", del_opts, key="del_career")
                if st.checkbox("Confirm permanent deletion of career and its cutoffs"):
                    if st.button("Delete Career", type="primary"):
                        c_id = next((c["id"] for c in all_c if f"{c['name']} ({c['stream_name']})" == del_sel), None)
                        if c_id and db.delete_career(c_id):
                            st.success("✅ Career deleted.")
                            reset_form()
                            st.rerun()
                        else:
                            st.error("❌ Could not delete career.")
    elif page == "📤 Bulk Upload Marks":
        render_upload_page()
    elif page == "📊 Student Performance":
        st.header("Student Performance Charts")
        stus = cached_get_all_students()
        if not stus:
            st.info("No students yet.")
            return
        opts = {f"Gr{s['grade']}{s['class_section']} | {s['reg_no']} - {s['name']}": s for s in stus}
        ch = st.selectbox("Student", list(opts.keys()))
        render_student_chart_and_ai(opts[ch])
    elif page == "📈 Class-wise Performance":
        render_class_performance()
    elif page == "👥 All Students":
        st.header("All Students")
        gf = st.selectbox("Grade", ["All"] + [f"Grade {g}" for g in db.GRADES], key="asf_g")
        sf = st.selectbox("Stream", ["All"] + [s["name"] for s in streams], key="asf_s")
        cf = st.selectbox("Class", ["All"] + list("ABCDEFGH"), key="asf_c")
        g = int(gf.split()[1]) if gf != "All" else None
        s = db.get_stream_id(sf) if sf != "All" else None
        c = cf if cf != "All" else None
        stus = cached_get_all_students(grade=g, stream_id=s, class_section=c)
        if stus:
            st.metric("Total", len(stus))
            df_all = clean_dataframe(pd.DataFrame(stus)[["reg_no", "name", "grade", "class_section", "stream_name", "career_name"]].rename(
                columns={"reg_no": "Reg No", "name": "Name", "grade": "Grade", "class_section": "Class",
                         "stream_name": "Stream", "career_name": "Career"}))
            st.dataframe(df_all, use_container_width=True, hide_index=True)
        else:
            st.info("No students found.")
    elif page == "🤖 AI Grade Predictions":
        render_prediction_page()
    elif page == "🗑️ Delete Marks":
        render_delete_marks()
    elif page == "🗑️ Delete Student":
        render_delete_student()
    elif page == "🗑️ Delete Students Bulk":
        render_bulk_delete_students()
    else:
        st.error("Unknown page")

# =============================================================================
# TEACHER DASHBOARD
# =============================================================================
def teacher_dashboard():
    _sidebar_user("🧑‍🏫", "Counselling Teacher")
    page = st.sidebar.radio("Navigate", [
        "➕ Add / Update Student",
        "📤 Bulk Upload Marks",
        "📝 Enter Marks",
        "📊 Performance & AI Insight",
        "📈 Class-wise Performance",
        "⬇️ Downloadable Reports",
        "🤖 AI Grade Predictions",
    ])
    st.sidebar.markdown("<br/>", unsafe_allow_html=True)
    if st.sidebar.button("🚪 Logout"):
        logout()

    _banner("🧑‍🏫", "Teacher Dashboard", "Add students, upload marks and view career-readiness insights")
    streams = db.get_streams()
    stream_names = [s["name"] for s in streams]

    if page == "➕ Add / Update Student":
        render_add_update_student()
    elif page == "📤 Bulk Upload Marks":
        render_upload_page()
    elif page == "📝 Enter Marks":
        st.header("Enter Marks (per Term)")
        gf2 = st.selectbox("Filter by Grade", ["All"] + [f"Grade {g}" for g in db.GRADES], key="em_gf")
        g2 = int(gf2.split()[1]) if gf2 != "All" else None
        stus = cached_get_all_students(grade=g2)
        if not stus:
            st.info("No students found.")
            return
        opts = {f"Gr{s['grade']}{s['class_section']} | {s['reg_no']} - {s['name']}": s for s in stus}
        ch = st.selectbox("Student", list(opts.keys()))
        student = opts[ch]
        c1, c2, c3 = st.columns(3)
        term = c1.selectbox("Term", [1, 2, 3])
        year = c2.number_input("Year", 2000, 2100, 2026, step=1)
        gfm = c3.selectbox("Grade this year", [f"Grade {g}" for g in db.GRADES],
                          index=db.GRADES.index(student["grade"]) if student["grade"] in db.GRADES else 4)
        gint = int(gfm.split()[1])
        subs = db.get_subjects_by_stream(student["stream_id"]) if student.get("stream_id") else []
        if not subs:
            subs = db.get_all_subjects()
        if not subs:
            st.warning("No subjects found.")
            return
        ex = {m["subject_id"]: m["marks"] for m in cached_get_marks_for_student(student["reg_no"], year=year) if m["term"] == term}
        with st.form(f"marks_f_{st.session_state.form_key}"):
            entries = {}
            cols = st.columns(2)
            for i, sub in enumerate(subs):
                with cols[i % 2]:
                    entries[sub["id"]] = st.number_input(sub["name"], 0.0, 100.0,
                                                         float(ex.get(sub["id"], 0.0)),
                                                         step=1.0, key=f"mk_{sub['id']}_{term}_{year}")
            if st.form_submit_button(f"Save Term {term} Marks"):
                for sid2, mv in entries.items():
                    db.save_mark(student["reg_no"], sid2, term, year, gint, mv)
                st.success(f"✅ Term {term} marks saved for {student['name']}!")
                reset_form()
                st.rerun()
    elif page == "📊 Performance & AI Insight":
        st.header("Performance & AI Career-Readiness")
        stus = cached_get_all_students()
        if not stus:
            st.info("No students.")
            return
        opts = {f"Gr{s['grade']}{s['class_section']} | {s['reg_no']} - {s['name']}": s for s in stus}
        ch = st.selectbox("Student", list(opts.keys()))
        render_student_chart_and_ai(opts[ch])
    elif page == "📈 Class-wise Performance":
        render_class_performance()
    elif page == "⬇️ Downloadable Reports":
        st.header("Downloadable Reports")
        stus = cached_get_all_students()
        if not stus:
            st.info("No students.")
            return
        opts = {f"Gr{s['grade']}{s['class_section']} | {s['reg_no']} - {s['name']}": s for s in stus}
        ch = st.selectbox("Student", list(opts.keys()))
        student = opts[ch]
        t1, t2 = st.tabs(["Single Term", "Year Summary"])
        with t1:
            cc1, cc2 = st.columns(2)
            term = cc1.selectbox("Term", [1, 2, 3], key="rt")
            year = cc2.number_input("Year", 2000, 2100, 2026, step=1, key="ry")
            mrows = [m for m in cached_get_marks_for_student(student["reg_no"], year=year) if m["term"] == term]
            if not mrows:
                st.info("No marks for this term/year.")
            else:
                df = clean_dataframe(pd.DataFrame(mrows)[["subject_name", "marks"]])
                # Show table
                st.dataframe(df, use_container_width=True, hide_index=True)


                # PDF download (new)
                if st.button(f"📄 Download Term {term} Marks (PDF)", key="pdf_term"):
                    try:
                        pdf_bytes = generate_marks_pdf(student, df, f"Term {term} Marks - {student['name']}")
                        st.download_button(
                            label="⬇️ Click to download PDF",
                            data=pdf_bytes,
                            file_name=f"{student['reg_no']}_term{term}_{year}.pdf",
                            mime="application/pdf",
                            key="pdf_term_download"
                        )
                        st.success("PDF ready for download!")
                    except FontNotFoundError as e:
                        st.error(f"❌ Could not generate PDF: {e}")
                    except Exception as e:
                        st.error(f"❌ Could not generate PDF: {e}")
        with t2:
            all_marks = cached_get_marks_for_student(student["reg_no"])
            if all_marks:
                year_df = clean_dataframe(pd.DataFrame(all_marks))
                st.dataframe(year_df, use_container_width=True, hide_index=True)

                # CSV download
                csv_all = year_df.to_csv(index=False)
                st.download_button(
                    "📥 Download All Marks (CSV)",
                    data=csv_all,
                    file_name=f"{student['reg_no']}_all_marks.csv",
                    mime="text/csv"
                )

                # PDF download (new)
                if st.button("📄 Download All Marks (PDF)", key="pdf_all"):
                    try:
                        # For all marks we include term and year columns if available
                        pdf_bytes = generate_marks_pdf(student, year_df, f"All Marks - {student['name']}")
                        st.download_button(
                            label="⬇️ Click to download PDF",
                            data=pdf_bytes,
                            file_name=f"{student['reg_no']}_all_marks.pdf",
                            mime="application/pdf",
                            key="pdf_all_download"
                        )
                        st.success("PDF ready for download!")
                    except FontNotFoundError as e:
                        st.error(f"❌ Could not generate PDF: {e}")
                    except Exception as e:
                        st.error(f"❌ Could not generate PDF: {e}")
            else:
                st.info("No marks found for this student.")
    elif page == "🤖 AI Grade Predictions":
        render_prediction_page()

# =============================================================================
# FOOTER (custom)
# =============================================================================
def render_footer():
    st.markdown("""
    <div class="custom-footer">
        <p>© 2026 School Performance System — Built with Streamlit & ❤️ for education</p>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# MAIN
# =============================================================================
def main():
    if st.session_state.get("jwt_token"):
        if not verify_jwt(st.session_state.jwt_token):
            logout()
    if not st.session_state.user:
        login_screen()
    else:
        if st.session_state.user["role"] == "admin":
            admin_dashboard()
        else:
            teacher_dashboard()
        render_footer()

if __name__ == "__main__":
    main()