"""
prediction_ai.py
Grade-level performance prediction using linear regression (numpy only).

How it works
------------
1.  For each grade (6-13), collect all historical (year → avg_marks) data
    points stored in the `marks` table.
2.  If ≥ 2 data points exist for a grade, fit a least-squares line
    (numpy.polyfit degree=1) to project the trend N years ahead.
3.  Classify each grade's projected trajectory:
      Strong   ≥ 75
      On Track 60-74
      Warning  45-59
      Critical  < 45
4.  Return structured results that the UI can display as a bar chart and
    include in a downloadable PDF.

Accuracy improves automatically as more years of data are fed into the
system - more data points = tighter regression line.
"""

import numpy as np
from statistics import mean


RISK_THRESHOLDS = {
    "Strong":   75,
    "On Track": 60,
    "Warning":  45,
    "Critical": 0,
}

RISK_COLORS = {
    "Strong":   "#2fa66b",
    "On Track": "#4C72B0",
    "Warning":  "#f0a500",
    "Critical": "#e03c3c",
}


def _classify(mark):
    if mark >= 75:  return "Strong"
    if mark >= 60:  return "On Track"
    if mark >= 45:  return "Warning"
    return "Critical"


def predict_grade_performance(grade_year_rows, predict_years=2):
    """
    grade_year_rows : list of dicts  { grade, year, avg_marks, sample_size }
                      (from db.get_grade_year_averages())
    predict_years   : how many future years to project

    Returns a list of dicts, one per grade:
    {
      grade, data_points, years_seen, historical,  ← past records
      current_avg,                                 ← latest known average
      predicted_avg,                               ← projected average (next year)
      trend_slope,                                 ← marks/year improvement rate
      status,                                      ← risk label
      confidence,                                  ← "Low" / "Medium" / "High"
      message,
      projection_series,   ← [(year, marks), ...] for chart
    }
    """
    # Group by grade
    by_grade: dict[int, list[dict]] = {}
    for row in grade_year_rows:
        by_grade.setdefault(row["grade"], []).append(row)

    results = []
    for grade in range(6, 14):
        rows = sorted(by_grade.get(grade, []), key=lambda r: r["year"])
        data_points = len(rows)
        years_seen  = [r["year"] for r in rows]
        marks_seen  = [r["avg_marks"] for r in rows]

        if data_points == 0:
            results.append({
                "grade": grade,
                "data_points": 0,
                "years_seen": [],
                "historical": [],
                "current_avg": None,
                "predicted_avg": None,
                "trend_slope": None,
                "status": "No Data",
                "confidence": "None",
                "message": "No marks data entered yet for this grade.",
                "projection_series": [],
            })
            continue

        current_avg = round(marks_seen[-1], 2)

        if data_points == 1:
            # Can't fit a line - use flat projection
            predicted_avg = current_avg
            slope = 0.0
            confidence = "Low"
            projection_series = [(years_seen[-1], current_avg),
                                 (years_seen[-1] + 1, current_avg)]
        else:
            # Fit degree-1 polynomial (linear regression)
            coeffs = np.polyfit(years_seen, marks_seen, 1)
            slope  = round(float(coeffs[0]), 3)
            next_year = years_seen[-1] + 1

            # Confidence based on how many years of data we have
            if data_points >= 5:
                confidence = "High"
            elif data_points >= 3:
                confidence = "Medium"
            else:
                confidence = "Low"

            # Build projection series: fill historical fitted + future projected
            min_y, max_y = min(years_seen), years_seen[-1] + predict_years
            projection_series = [
                (y, round(float(np.polyval(coeffs, y)), 2))
                for y in range(min_y, max_y + 1)
            ]
            predicted_avg = round(float(np.polyval(coeffs, next_year)), 2)
            predicted_avg = max(0.0, min(100.0, predicted_avg))

        status = _classify(predicted_avg)

        # Build human-readable message
        if slope is not None and data_points > 1:
            trend_word = "improving" if slope > 0.5 else ("declining" if slope < -0.5 else "stable")
            arrow = "+" if slope >= 0 else "-"
            message = (
                f"Grade {grade} is {trend_word} "
                f"({arrow}{abs(slope):.1f} marks/year). "
                f"Projected average: {predicted_avg}. "
            )
        else:
            message = (f"Grade {grade} current average: {current_avg}. "
                       f"Only one year of data - prediction is a flat projection.")

        if status == "Critical":
            message += "[CRITICAL] Urgent intervention recommended."
        elif status == "Warning":
            message += "[WARNING] Needs attention before O/L exams."
        elif status == "On Track":
            message += "[ON TRACK] Performing adequately."
        else:
            message += "[STRONG] Performing well."

        results.append({
            "grade":             grade,
            "data_points":       data_points,
            "years_seen":        years_seen,
            "historical":        list(zip(years_seen, [round(m, 2) for m in marks_seen])),
            "current_avg":       current_avg,
            "predicted_avg":     predicted_avg,
            "trend_slope":       round(float(slope), 3) if slope is not None else None,
            "status":            status,
            "confidence":        confidence,
            "message":           message,
            "projection_series": projection_series,
        })

    return results


def ol_risk_summary(prediction_results):
    """Highlight grades 10 & 11 (O/L critical years) specifically."""
    ol_grades = [r for r in prediction_results if r["grade"] in (10, 11)]
    risky = [r for r in ol_grades if r["status"] in ("Critical", "Warning")]
    strong = [r for r in ol_grades if r["status"] in ("Strong", "On Track")]

    if not ol_grades or all(r["data_points"] == 0 for r in ol_grades):
        return "No O/L grade data (Grade 10 & 11) available yet. Enter marks for these grades to see O/L predictions."

    parts = []
    for r in ol_grades:
        if r["data_points"] == 0:
            parts.append(f"Grade {r['grade']}: No data.")
        else:
            parts.append(
                f"Grade {r['grade']}: predicted avg {r['predicted_avg']} - {r['status']} "
                f"(confidence: {r['confidence']}, {r['data_points']} year(s) of data)."
            )

    # Use ASCII-safe separator (em-dash breaks fpdf latin-1 encoding)
    safe_parts = [p.replace("\u2014", "-").replace("\u2013", "-") for p in parts]
    summary = "O/L Performance Outlook | " + "  |  ".join(safe_parts)
    if risky:
        summary += f"  WARNING: {len(risky)} O/L grade(s) at risk - immediate support recommended."
    return summary
