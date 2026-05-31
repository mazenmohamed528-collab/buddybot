import json
import os
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pyodbc


PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_PATH = PROJECT_ROOT / "models" / "fci_gpa_summary.npz"

DB_DRIVER = os.getenv("BUDDYBOT_DB_DRIVER", "ODBC Driver 17 for SQL Server")
DB_SERVER = os.getenv("BUDDYBOT_DB_SERVER", "localhost")
DB_NAME = os.getenv("BUDDYBOT_DB_NAME", "FCI_UNIVERSITY")


def get_connection():
    return pyodbc.connect(
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        "Trusted_Connection=yes;"
        "Encrypt=no;"
        "TrustServerCertificate=yes;"
    )


def fetch_gpa_rows() -> List[Dict[str, Any]]:
    sql = """
SELECT
    s.student_id AS StudentID,
    s.full_name AS FullName,
    s.group_code AS GroupCode,
    s.dept_code AS DepartmentCode,
    s.current_year AS CurrentYear,
    s.current_semester AS CurrentSemester,
    g.academic_year AS AcademicYear,
    g.semester AS Semester,
    g.semester_gpa AS SemesterGPA,
    cg.third_year_cumulative_gpa AS ThirdYearCumulativeGPA
FROM GPA_Records g
JOIN v_rasa_students s ON s.student_id = g.student_id
LEFT JOIN v_cumulative_gpa cg ON cg.student_id = s.student_id
WHERE g.semester_gpa IS NOT NULL
ORDER BY s.student_id, g.academic_year, g.semester
"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def main():
    rows = fetch_gpa_rows()
    if not rows:
        raise RuntimeError("No GPA rows found in FCI_UNIVERSITY.")

    student_ids = np.array([row["StudentID"] for row in rows], dtype=object)
    semester_gpa = np.array([float(row["SemesterGPA"]) for row in rows], dtype=np.float32)
    groups = np.array([row["GroupCode"] for row in rows], dtype=object)
    departments = np.array([row["DepartmentCode"] for row in rows], dtype=object)

    metrics = {
        "database": DB_NAME,
        "rows": int(len(rows)),
        "students": int(len(set(student_ids))),
        "average_semester_gpa": float(np.mean(semester_gpa)),
        "highest_semester_gpa": float(np.max(semester_gpa)),
        "lowest_semester_gpa": float(np.min(semester_gpa)),
        "purpose": "FCI GPA summary artifact for reporting and quick checks.",
    }

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        MODEL_PATH,
        student_ids=student_ids,
        semester_gpa=semester_gpa,
        groups=groups,
        departments=departments,
        rows_json=json.dumps(rows, default=str),
        metrics_json=json.dumps(metrics),
    )

    print(f"FCI GPA summary saved to {MODEL_PATH}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
