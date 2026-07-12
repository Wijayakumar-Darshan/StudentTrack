"""
pdf_report.py
PDF generation using fpdf2 with NotoSansSinhala (supports Latin + Sinhala Unicode).
"""
import os, tempfile
from fpdf import FPDF
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import prediction_ai as pai

FONT_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "NotoSansSinhala.ttf")
FONT_FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def _safe(text):
    """Return a PDF-safe string (str, no trailing None)."""
    if text is None: return ""
    return str(text)

def _save_fig(fig):
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fig.savefig(tmp.name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return tmp.name

def _bar_chart(labels, current, cutoffs, title):
    fig, ax = plt.subplots(figsize=(6, 3.2))
    x = range(len(labels)); w = 0.35
    ax.bar([i-w/2 for i in x], current, w, label="Student Marks",  color="#4C72B0")
    ax.bar([i+w/2 for i in x], cutoffs,  w, label="Minimum Cutoff", color="#DD8452")
    ax.set_xticks(list(x)); ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
    ax.set_ylim(0, 100); ax.set_ylabel("Marks"); ax.set_title(title, fontsize=10)
    ax.legend(fontsize=7); fig.tight_layout()
    return _save_fig(fig)

def _pred_chart(results):
    labels = [f"Gr {r['grade']}" for r in results]
    cur    = [r["current_avg"]   or 0 for r in results]
    pred   = [r["predicted_avg"] or 0 for r in results]
    colors = [pai.RISK_COLORS.get(r["status"], "#aaa") for r in results]
    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(labels)); w = 0.38
    ax.bar(x-w/2, cur,  w, label="Current Avg",   color="#4C72B0", alpha=0.85)
    ax.bar(x+w/2, pred, w, label="Predicted Avg", color=colors,    alpha=0.85)
    for yval, col, ls, lbl in [(75,"#2fa66b","--","Strong(75)"),(60,"#4C72B0",":","OnTrack(60)"),(45,"#f0a500","-.","Warning(45)")]:
        ax.axhline(yval, color=col, linestyle=ls, linewidth=1.2, label=lbl)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylim(0, 100); ax.set_ylabel("Average Marks")
    ax.set_title("Grade-wise Prediction (Grades 6-13)", fontsize=11)
    ax.legend(fontsize=7, loc="lower right"); fig.tight_layout()
    return _save_fig(fig)

def _trend_chart(results):
    with_data = [r for r in results if r["data_points"] > 0]
    if not with_data: return None
    fig, ax = plt.subplots(figsize=(8, 4))
    colors = plt.cm.tab10.colors
    for i, r in enumerate(with_data):
        col = colors[i % len(colors)]
        hy = [h[0] for h in r["historical"]]; hm = [h[1] for h in r["historical"]]
        py = [p[0] for p in r["projection_series"]]; pm = [p[1] for p in r["projection_series"]]
        ax.scatter(hy, hm, color=col, s=30, zorder=3)
        if len(py) > 1:
            ax.plot(py, pm, color=col, linewidth=1.8,
                    linestyle="--" if r["data_points"] == 1 else "-",
                    label=f"Grade {r['grade']}")
    ax.set_ylim(0, 100); ax.set_ylabel("Avg Marks"); ax.set_xlabel("Year")
    ax.set_title("Grade Trend Lines", fontsize=11)
    ax.legend(fontsize=7, ncol=4, loc="lower right"); fig.tight_layout()
    return _save_fig(fig)


class _PDF(FPDF):
    def __init__(self):
        super().__init__()
        font = FONT_PATH if os.path.exists(FONT_PATH) else FONT_FALLBACK
        self.add_font("Main", "", font)
        self.add_font("Main", "B", font)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font("Main", "B", 13)
        self.cell(0, 10, "Student Performance Report",
                  new_x="LMARGIN", new_y="NEXT", align="C")

    def footer(self):
        self.set_y(-15)
        self.set_font("Main", "", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    # ── Helpers ──────────────────────────────────────────────────────────
    def setfont(self, size, bold=False):
        self.set_font("Main", "B" if bold else "", size)

    def row(self, *cells):
        """cells = list of (text, width, align)"""
        for text, w, align in cells:
            self.cell(w, 8, _safe(text), border=1, align=align)
        self.ln()

    def kv(self, label, value, size=11):
        self.setfont(size)
        self.cell(0, 7, f"{label}: {_safe(value)}", new_x="LMARGIN", new_y="NEXT")

    def img(self, path, w=180):
        self.image(path, x=15, w=w)
        os.unlink(path)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_term_report(student, term, year, marks_rows, ai_plan=None, ai_summary=None):
    pdf = _PDF(); pdf.add_page()
    pdf.setfont(12, bold=True)
    pdf.cell(0, 8, f"Term {term} Report - Year {year}", new_x="LMARGIN", new_y="NEXT")
    for lbl, val in [("Registration No", student.get("reg_no","")),
                     ("Name",    student.get("name","")),
                     ("Grade",   student.get("grade","")),
                     ("Class",   student.get("class_section","")),
                     ("Stream",  student.get("stream_name","")),
                     ("Career",  student.get("career_name",""))]:
        pdf.kv(lbl, val)
    pdf.ln(3)

    pdf.setfont(11, bold=True)
    pdf.row(("Subject",90,"L"),("Marks",40,"C"))
    pdf.setfont(11)
    total = 0
    for r in marks_rows:
        pdf.row((_safe(r["subject_name"]),90,"L"),(str(r["marks"]),40,"C"))
        total += r["marks"]
    if marks_rows:
        pdf.setfont(11, bold=True)
        pdf.row(("Average",90,"L"),(str(round(total/len(marks_rows),2)),40,"C"))

    if ai_plan:
        pdf.ln(5); pdf.setfont(12, bold=True)
        pdf.cell(0, 8, "AI Career-Readiness Insight", new_x="LMARGIN", new_y="NEXT")
        pdf.setfont(10)
        if ai_summary:
            pdf.multi_cell(0, 6, _safe(ai_summary))
        pdf.ln(2)
        path = _bar_chart([p["subject"] for p in ai_plan],
                          [p["current"] for p in ai_plan],
                          [p["cutoff"]  for p in ai_plan],
                          "Marks vs Career Minimum Cutoff")
        pdf.img(path)
        pdf.ln(2)
        pdf.setfont(10, bold=True)
        pdf.row(("Subject",70,"L"),("Current",30,"C"),("Target",30,"C"),("Status",30,"C"))
        pdf.setfont(9)
        for p in ai_plan:
            pdf.row((_safe(p["subject"]),70,"L"),(str(p["current"]),30,"C"),
                    (str(p["cutoff"]),30,"C"),(_safe(p["status"]),30,"C"))

    return bytes(pdf.output())


def generate_year_summary_report(student, year, subject_term_avgs, overall_avg,
                                  ai_plan=None, ai_summary=None):
    pdf = _PDF(); pdf.add_page()
    pdf.setfont(12, bold=True)
    pdf.cell(0, 8, f"End-of-Year Summary - {year}", new_x="LMARGIN", new_y="NEXT")
    for lbl, val in [("Registration No", student.get("reg_no","")),
                     ("Name",   student.get("name","")),
                     ("Grade",  student.get("grade","")),
                     ("Class",  student.get("class_section","")),
                     ("Stream", student.get("stream_name","")),
                     ("Career", student.get("career_name",""))]:
        pdf.kv(lbl, val)
    pdf.ln(3)

    pdf.setfont(10, bold=True)
    pdf.row(("Subject",60,"L"),("Term 1",30,"C"),("Term 2",30,"C"),("Term 3",30,"C"),("Average",30,"C"))
    pdf.setfont(10)
    for row in subject_term_avgs:
        pdf.row((_safe(row["subject_name"]),60,"L"),
                (str(row.get("term1","-")),30,"C"),
                (str(row.get("term2","-")),30,"C"),
                (str(row.get("term3","-")),30,"C"),
                (str(row["average"]),30,"C"))
    pdf.ln(3); pdf.setfont(11, bold=True)
    pdf.cell(0, 8, f"Overall Yearly Average: {overall_avg}", new_x="LMARGIN", new_y="NEXT")

    if ai_plan:
        pdf.ln(5); pdf.setfont(12, bold=True)
        pdf.cell(0, 8, "AI Career-Readiness (Yearly)", new_x="LMARGIN", new_y="NEXT")
        pdf.setfont(10)
        if ai_summary: pdf.multi_cell(0, 6, _safe(ai_summary))
        pdf.ln(2)
        path = _bar_chart([p["subject"] for p in ai_plan],
                          [p["current"] for p in ai_plan],
                          [p["cutoff"]  for p in ai_plan],
                          "Yearly Average vs Career Minimum Cutoff")
        pdf.img(path)

    return bytes(pdf.output())


def generate_class_report(grade, class_section, year, class_avg, subject_rows):
    """Class-wide performance PDF report."""
    pdf = _PDF(); pdf.add_page()
    pdf.setfont(13, bold=True)
    pdf.cell(0, 10, f"Class Performance Report - Grade {grade}{class_section} ({year})",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4); pdf.setfont(11)
    pdf.kv("Grade", f"{grade}{class_section}")
    pdf.kv("Year", year)
    pdf.kv("Class Average", round(class_avg, 2))
    pdf.kv("Students", len(subject_rows))
    pdf.ln(4)

    if subject_rows:
        fig, ax = plt.subplots(figsize=(7, 4))
        names = [r["subject_name"] for r in subject_rows]
        avgs  = [round(r["avg_marks"], 2) for r in subject_rows]
        ax.barh(names, avgs, color="#4C72B0")
        ax.set_xlim(0, 100); ax.set_xlabel("Average Marks")
        ax.set_title(f"Grade {grade}{class_section} Subject Averages ({year})")
        fig.tight_layout()
        path = _save_fig(fig)
        pdf.img(path)

        pdf.setfont(10, bold=True)
        pdf.row(("Subject", 100, "L"), ("Avg Marks", 40, "C"), ("Count", 30, "C"))
        pdf.setfont(10)
        for r in subject_rows:
            pdf.row((_safe(r["subject_name"]),100,"L"),
                    (str(round(r["avg_marks"],2)),40,"C"),
                    (str(r["n"]),30,"C"))

    return bytes(pdf.output())


def generate_prediction_report(prediction_results, ol_summary, generated_date):
    pdf = _PDF(); pdf.add_page()
    pdf.setfont(14, bold=True)
    pdf.cell(0, 10, "AI Grade Performance Prediction Report",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.setfont(10)
    pdf.cell(0, 7, f"Generated: {generated_date}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(3)

    pdf.setfont(12, bold=True)
    pdf.cell(0, 8, "O/L Risk Summary (Grade 10 & 11)", new_x="LMARGIN", new_y="NEXT")
    pdf.setfont(10)
    pdf.multi_cell(0, 6, _safe(ol_summary))
    pdf.ln(4)

    p1 = _pred_chart(prediction_results)
    pdf.img(p1); pdf.ln(3)

    p2 = _trend_chart(prediction_results)
    if p2:
        pdf.add_page()
        pdf.setfont(12, bold=True)
        pdf.cell(0, 8, "Grade Trend Lines (Historical + Projected)", new_x="LMARGIN", new_y="NEXT")
        pdf.img(p2); pdf.ln(3)

    pdf.add_page()
    pdf.setfont(12, bold=True)
    pdf.cell(0, 8, "Grade-by-Grade Prediction Details", new_x="LMARGIN", new_y="NEXT")
    pdf.setfont(9, bold=True)
    pdf.row(("Grade",18,"C"),("Yrs",18,"C"),("Current",25,"C"),
            ("Predicted",28,"C"),("Trend/yr",25,"C"),("Status",28,"C"),("Confidence",28,"C"))
    pdf.setfont(9)
    for r in prediction_results:
        pdf.row((str(r["grade"]),18,"C"),
                (str(r["data_points"]),18,"C"),
                (str(r["current_avg"]   or "-"),25,"C"),
                (str(r["predicted_avg"] or "-"),28,"C"),
                (str(r["trend_slope"]   or "-"),25,"C"),
                (_safe(r["status"]),28,"C"),
                (_safe(r["confidence"]),28,"C"))
    pdf.ln(4)
    pdf.setfont(10, bold=True)
    pdf.cell(0, 7, "AI Grade Insights", new_x="LMARGIN", new_y="NEXT")
    pdf.setfont(9)
    for r in prediction_results:
        if r["data_points"] > 0:
            pdf.multi_cell(0, 6, _safe(f"  Grade {r['grade']}: {r['message']}"))
            pdf.ln(1)

    return bytes(pdf.output())
