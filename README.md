# Student Performance & Marks Management System

## Quick Start
```bash
pip install -r requirements.txt
streamlit run app.py
```
Open http://localhost:8501

## Login
| Role    | Username | Password    |
|---------|----------|-------------|
| Admin   | admin    | admin123    |
| Teacher | teacher  | teacher123  |

## Features

### Bulk Excel Upload (NEW)
- **Grades 6-9**: Upload class-wise sheets (e.g. `First__team__Test_8D_2026.xlsm`)
  - Auto-detects grade and class section (A-H) from each sheet header
  - Imports all students with their marks per subject
- **Grades 10-11 O/L**: Upload O/L format sheets (e.g. `2026__grade_11_First_Term___S1.xlsm`)
  - Handles dual-student-per-row format automatically
  - Imports core + optional subjects
- Students auto-registered: `{year}-G{grade}{class}-{seq}` (e.g. `2026-G8D-001`)
- Sinhala Unicode names fully supported in all PDFs

### Class-wise Performance
- Grade/class average bar charts
- Drill into any class for subject-level breakdown
- Downloadable class PDF report

### Individual Student Reports
- Term report (marks + AI career insight + cutoff chart)
- End-of-year summary (3 terms + overall average)
- Both downloadable as PDF

### AI Grade Prediction
- Linear regression trained on all imported marks data
- Predicts next year's average per grade (6-13)
- Risk levels: Strong / On Track / Warning / Critical
- O/L grades (10 & 11) highlighted for intervention
- Confidence increases as more years of data are added
- Downloadable prediction PDF

### Career Dreams & Cutoffs
- Admin sets subject-specific minimum cutoffs per career
- AI compares student averages against cutoffs
- Per-subject improvement % and status shown in charts

## Database Schema
See `schema.prisma` for the full Prisma schema.
To use with Prisma CLI:
```bash
npx prisma db push --schema schema.prisma
```

## Font Support
`NotoSansSinhala.ttf` is bundled for PDF rendering of Sinhala Unicode names.

## File Structure
```
school-performance-app/
├── app.py              # Streamlit UI
├── database.py         # SQLite data layer
├── excel_parser.py     # Excel bulk-import (junior + senior formats)
├── ai_advisor.py       # Career-readiness AI engine
├── prediction_ai.py    # Grade prediction (linear regression)
├── pdf_report.py       # PDF generation (Unicode font)
├── schema.prisma       # Prisma schema for DB migrations
├── NotoSansSinhala.ttf # Unicode font (Sinhala + Latin)
├── requirements.txt
└── data/               # SQLite database (auto-created)
```
