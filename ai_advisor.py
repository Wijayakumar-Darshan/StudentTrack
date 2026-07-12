"""
ai_advisor.py
A small, transparent rule-based "AI" advisor that estimates how much a
student needs to improve their marks in each subject to reach the minimum
cutoff required for their chosen career dream.

This is intentionally simple (no external API key required) so the whole
project runs offline. The same interface could later be swapped for a call
to a real ML/LLM model without changing the rest of the app.
"""

from statistics import mean


def average_marks_by_subject(marks_rows):
    """marks_rows: list of dicts with subject_name, marks, term, year.
    Returns {subject_name: average_marks} across all available terms/years."""
    buckets = {}
    for r in marks_rows:
        buckets.setdefault(r["subject_name"], []).append(r["marks"])
    return {subj: round(mean(vals), 2) for subj, vals in buckets.items()}


def build_improvement_plan(avg_marks: dict, cutoffs: list):
    """
    avg_marks: {subject_name: avg_marks}
    cutoffs: list of dicts [{subject_name, min_marks}, ...]

    Returns a list of dicts:
      subject, current, cutoff, gap, improvement_pct, status, message
    """
    plan = []
    for c in cutoffs:
        subject = c["subject_name"]
        cutoff = c["min_marks"]
        current = avg_marks.get(subject, 0.0)
        gap = round(cutoff - current, 2)

        if cutoff > 0:
            improvement_pct = round(max(gap, 0) / cutoff * 100, 1)
        else:
            improvement_pct = 0.0

        if gap <= 0:
            status = "On Track"
            message = f"Already meeting the {subject} requirement ({current}/{cutoff})."
        elif gap <= 5:
            status = "Almost There"
            message = f"Just {gap} marks away in {subject}. A little extra revision should close the gap."
        elif gap <= 15:
            status = "Needs Improvement"
            message = (
                f"Needs about {improvement_pct}% improvement in {subject} "
                f"(currently {current}, target {cutoff})."
            )
        else:
            status = "Critical"
            message = (
                f"Significant gap in {subject}: needs roughly {improvement_pct}% improvement "
                f"to reach the {cutoff} mark target. Consider focused tutoring/extra classes."
            )

        plan.append({
            "subject": subject,
            "current": current,
            "cutoff": cutoff,
            "gap": gap,
            "improvement_pct": improvement_pct,
            "status": status,
            "message": message,
        })
    return plan


def overall_summary(plan):
    """Produce one overall sentence describing the student's readiness for their career dream."""
    if not plan:
        return "No cutoff data available for this career yet."

    critical = [p for p in plan if p["status"] == "Critical"]
    needs_improve = [p for p in plan if p["status"] == "Needs Improvement"]
    on_track = [p for p in plan if p["status"] in ("On Track", "Almost There")]

    total_subjects = len(plan)
    avg_gap_pct = round(mean([p["improvement_pct"] for p in plan]), 1)

    if not critical and not needs_improve:
        return (
            f"Great progress! The student is on track in all {total_subjects} subjects "
            f"required for this career path."
        )

    weakest = max(plan, key=lambda p: p["improvement_pct"])
    return (
        f"On average, the student needs about {avg_gap_pct}% overall improvement to meet "
        f"the requirements for this career. The weakest area is {weakest['subject']} "
        f"(needs ~{weakest['improvement_pct']}% improvement). "
        f"{len(on_track)}/{total_subjects} subjects are already on track."
    )
