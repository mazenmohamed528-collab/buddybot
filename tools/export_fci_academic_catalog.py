"""Export the FCI 2025-2026 academic catalog for BuddyBot.

The live SQL Server database remains the source for current courses,
departments, and schedule-linked instructors. This script produces:

1. actions/fci_academic_catalog.py
   Importable Python dicts/helpers for Rasa custom actions.

2. actions/fci_academic_catalog_data.json
   Machine-readable catalog snapshot.

3. C:/dev/rag_service/knowledge_base/faculty/courses/fci_course_catalog_2025_2026.md
   Markdown RAG document with metadata, department descriptions, course summaries,
   and instructor names.

Run from C:\\dev\\rasa_project:

    .\\.venv\\Scripts\\python.exe tools\\export_fci_academic_catalog.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQL_ENGINE = Path(r"C:\dev\sql_engine_service")
DEFAULT_RAG_OUTPUT = Path(r"C:\dev\rag_service\knowledge_base\faculty\courses\fci_course_catalog_2025_2026.md")
DEFAULT_ACTION_DATA = PROJECT_ROOT / "actions" / "fci_academic_catalog_data.json"
DEFAULT_ACTION_MODULE = PROJECT_ROOT / "actions" / "fci_academic_catalog.py"


DEPARTMENTS: Dict[str, Dict[str, str]] = {
    "GEN": {
        "name": "General Studies (Years 1-2)",
        "code": "GEN",
        "description": (
            "The General Studies programme covers the foundational two years that all FCI "
            "students share before specialising in a major. It builds mathematical, "
            "programming, and systems-thinking skills through discrete mathematics, physics, "
            "database design, networking, AI fundamentals, and cyber security basics."
        ),
    },
    "CS": {
        "name": "Computer Sciences",
        "code": "CS",
        "description": (
            "The Computer Sciences department dives into the theory and practice of computing: "
            "algorithms, graphics, networks, security, compilers, vision, cloud systems, and "
            "modern application areas such as machine learning and big data."
        ),
    },
    "AI": {
        "name": "Artificial Intelligence",
        "code": "AI",
        "description": (
            "The Artificial Intelligence department focuses on intelligent systems that "
            "perceive, reason, learn, and act. Students study automated reasoning, cognitive "
            "science, deep learning, NLP, robotics, speech processing, virtual reality, and "
            "autonomous agents."
        ),
    },
    "CSCS": {
        "name": "Cyber Security",
        "code": "CSCS",
        "description": (
            "The Cyber Security department trains students to protect systems, networks, data, "
            "and people from digital threats. The curriculum spans cryptography, penetration "
            "testing, digital forensics, risk management, cloud security, IoT threats, and "
            "cyber warfare."
        ),
    },
    "ISDS": {
        "name": "Information Systems & Data Science",
        "code": "ISDS",
        "description": (
            "The Information Systems & Data Science department bridges computer science, "
            "business intelligence, and statistical analysis. Students learn the data pipeline: "
            "acquiring, storing, processing, visualising, and interpreting data for decision "
            "support."
        ),
    },
    "SE": {
        "name": "Software Engineering",
        "code": "SE",
        "description": (
            "The Software Engineering department trains students to build software "
            "professionally and at scale: requirements, architecture, testing, quality, team "
            "coordination, cloud/mobile platforms, IoT applications, and secure development."
        ),
    },
}


COURSE_DESCRIPTION_RULES: List[tuple[Iterable[str], str]] = [
    (["introduction to computer science"], "An entry-level tour of computing, data representation, problem solving, and algorithmic thinking."),
    (["math (1)", "math (2)", "mathematics"], "Mathematical foundations used later in algorithms, AI, graphics, modelling, and data analysis."),
    (["discrete"], "Logic, sets, relations, graphs, combinatorics, and proof techniques that support core computer science theory."),
    (["english"], "Academic and technical English for reading, writing, documentation, and presentations."),
    (["physics"], "Physical principles that support understanding hardware, signals, electronics, and computing systems."),
    (["programming"], "Programming fundamentals, debugging, structured problem solving, and practical code implementation."),
    (["data structures"], "Core data structures such as lists, stacks, queues, trees, hash tables, heaps, and graphs."),
    (["database"], "Database modelling, SQL, storage, retrieval, transactions, and data management concepts."),
    (["network"], "Networking models, routing, protocols, security, wireless/mobile networking, and network administration concepts."),
    (["operating"], "Processes, memory, scheduling, files, I/O, concurrency, and operating-system internals."),
    (["statistics", "probability"], "Probability, statistical inference, distributions, regression, and data analysis foundations."),
    (["artificial intelligence"], "AI foundations including search, knowledge representation, reasoning, and machine learning concepts."),
    (["cyber security", "security", "cryptology", "forensics", "hacker"], "Security concepts, threat modelling, defensive controls, offensive techniques, and incident response."),
    (["software engineering", "requirements", "testing", "quality", "configuration", "maintenance"], "Professional software development practices across requirements, design, testing, quality, maintenance, and delivery."),
    (["data science", "data mining", "visualization", "big data", "time series", "categorical"], "Data acquisition, analysis, modelling, visualisation, mining, and communicating data-driven insights."),
    (["machine", "deep learning"], "Machine learning and deep learning methods, model training, evaluation, and applied intelligent systems."),
    (["natural language", "speech"], "Language and speech processing, text/speech representation, and modern NLP or ASR techniques."),
    (["robot", "agent"], "Autonomous systems, agents, robotics, control, planning, coordination, and intelligent behaviour."),
    (["vision", "image"], "Image processing, computer vision, object recognition, segmentation, and perception systems."),
    (["cloud", "mobile"], "Cloud platforms, mobile computing, distributed deployment, containers, and scalable application architectures."),
    (["iot"], "IoT devices, sensors, communication protocols, edge/cloud integration, and security risks."),
    (["graphics"], "2D/3D graphics, rendering pipelines, transformations, shading, and interactive visual systems."),
    (["human rights", "law"], "Legal, ethical, human-rights, privacy, and professional responsibility topics for computing students."),
    (["economics", "feasibility"], "Economic analysis, feasibility studies, cost-benefit thinking, and technology business decisions."),
    (["marketing"], "Digital marketing, analytics, online growth, SEO, campaigns, and data-driven communication."),
    (["project management"], "Planning, risk management, agile/traditional project management, and team coordination for IT projects."),
    (["report writing", "communication"], "Technical writing, reporting, presentation, documentation, and professional communication skills."),
    (["analytic and creative"], "Structured problem solving, creativity, design thinking, and analytical decision-making."),
]


KEYWORD_RULES: List[tuple[Iterable[str], List[str]]] = [
    (["data science"], ["data science", "analytics", "python", "statistics", "machine learning"]),
    (["machine", "deep learning"], ["machine learning", "deep learning", "neural networks", "model training"]),
    (["database"], ["database", "SQL", "data modelling", "storage", "retrieval"]),
    (["network"], ["networking", "TCP/IP", "routing", "security"]),
    (["security", "cyber", "cryptology"], ["security", "cyber security", "cryptography", "risk"]),
    (["software"], ["software engineering", "SDLC", "requirements", "testing"]),
    (["ai", "artificial intelligence"], ["AI", "reasoning", "learning", "intelligent systems"]),
    (["graphics", "vision", "image"], ["computer graphics", "vision", "image processing"]),
    (["law", "human rights"], ["law", "ethics", "human rights", "privacy"]),
]


def safe_code(value: Any) -> str:
    return str(value or "").strip().upper()


def dept_code(row: Dict[str, Any]) -> str:
    return safe_code(row.get("DepartmentCode")) or "GEN"


def describe_course(name: str) -> str:
    lowered = name.lower()
    for terms, description in COURSE_DESCRIPTION_RULES:
        if any(term in lowered for term in terms):
            return description
    return "A course in the FCI 2025-2026 academic catalog. Use the live SQL schedule for current class times and assignments."


def course_keywords(code: str, name: str, dept: str) -> List[str]:
    lowered = f"{code} {name} {dept}".lower()
    keywords = {code.lower(), name.lower(), dept.lower()}
    for terms, values in KEYWORD_RULES:
        if any(term in lowered for term in terms):
            keywords.update(value.lower() for value in values)
    return sorted(keywords)


def add_sql_engine_to_path(sql_engine_path: Path) -> None:
    if str(sql_engine_path) not in sys.path:
        sys.path.insert(0, str(sql_engine_path))


def fetch_catalog_rows(sql_engine_path: Path) -> List[Dict[str, Any]]:
    add_sql_engine_to_path(sql_engine_path)
    from sql_engine.database import SqlServerClient
    from sql_engine.models import SqlQuery

    client = SqlServerClient()
    return client.fetch_all(
        SqlQuery(
            """
SELECT
    c.course_code AS CourseCode,
    c.course_name AS CourseName,
    c.credit_hours AS CreditHours,
    c.total_marks AS TotalMarks,
    c.course_year AS CourseYear,
    c.course_semester AS CourseSemester,
    c.category AS Category,
    COALESCE(d.dept_code, 'GEN') AS DepartmentCode,
    COALESCE(d.dept_name, 'General Studies (Years 1-2)') AS DepartmentName,
    STRING_AGG(CONCAT(sch.instructor_title, ' ', sch.instructor_name), '||') AS InstructorNames
FROM Courses c
LEFT JOIN Departments d ON d.dept_id = c.dept_id
LEFT JOIN v_rasa_schedule sch ON sch.course_code = c.course_code
GROUP BY
    c.course_code,
    c.course_name,
    c.credit_hours,
    c.total_marks,
    c.course_year,
    c.course_semester,
    c.category,
    d.dept_code,
    d.dept_name
ORDER BY c.course_year, c.course_semester, COALESCE(d.dept_code, 'GEN'), c.course_code
""",
            [],
        )
    )


def normalize_instructors(raw: Optional[str]) -> List[str]:
    names: List[str] = []
    seen = set()
    for part in str(raw or "").split("||"):
        cleaned = re.sub(r"\s+", " ", part).strip()
        if not cleaned or cleaned.lower() in {"none", "null"}:
            continue
        if cleaned.lower() not in seen:
            names.append(cleaned)
            seen.add(cleaned.lower())
    return names


def build_catalog(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    courses: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        code = safe_code(row.get("CourseCode"))
        if not code:
            continue
        name = str(row.get("CourseName") or "").strip()
        dept = dept_code(row)
        courses[code] = {
            "name": name,
            "dept": dept,
            "year": int(row.get("CourseYear") or 0),
            "semester": int(row.get("CourseSemester") or 0),
            "credit_hours": int(row.get("CreditHours") or 0),
            "category": str(row.get("Category") or "major"),
            "description": describe_course(name),
            "instructors": normalize_instructors(row.get("InstructorNames")),
            "keywords": course_keywords(code, name, dept),
        }
    return {"departments": DEPARTMENTS, "courses": courses}


def markdown_for_catalog(catalog: Dict[str, Any]) -> str:
    departments = catalog["departments"]
    courses = catalog["courses"]
    lines = [
        "---",
        "id: fci-course-catalog-2025-2026",
        "title: FCI Course Catalog 2025-2026",
        "category: course_catalog",
        "department: all",
        "audience: student",
        "source_type: structured_database_export",
        "official: true",
        "official_source: true",
        "document_type: course_catalog",
        "source_document: FCI_DB.sql",
        "source_file_name: FCI_DB.sql",
        "section_title: Courses, Departments, and Instructors",
        "academic_topic: study_plan",
        "regulation_type: course_catalog",
        "policy_version: 2025-2026",
        "language: en",
        "tags: courses, departments, instructors, curriculum, FCI, 2025-2026",
        "---",
        "",
        "# FCI Course Catalog 2025-2026",
        "",
        "This catalog is generated from the FCI SQL database and schedule-linked instructor data. Use it for course, department, instructor, and curriculum explanation questions. Use live SQL for current student records, schedules, GPA, grades, rooms, and enrollments.",
        "",
        "## Departments",
        "",
    ]
    for code, department in departments.items():
        lines.extend(
            [
                f"### {department['name']} ({code})",
                "",
                department["description"],
                "",
            ]
        )

    by_dept: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for code, course in courses.items():
        by_dept[course["dept"]].append({"code": code, **course})
    for dept, dept_courses in by_dept.items():
        dept_courses.sort(key=lambda item: (item["year"], item["semester"], item["code"]))

    lines.extend(["## Courses", ""])
    for dept in ["GEN", "CS", "AI", "CSCS", "ISDS", "SE"]:
        dept_courses = by_dept.get(dept, [])
        if not dept_courses:
            continue
        lines.extend([f"### {departments.get(dept, {'name': dept})['name']} ({dept})", ""])
        current_group = None
        for course in dept_courses:
            group = (course["year"], course["semester"])
            if group != current_group:
                current_group = group
                lines.extend([f"#### Year {group[0]}, Semester {group[1]}", ""])
            instructors = ", ".join(course["instructors"]) if course["instructors"] else "TBA"
            lines.extend(
                [
                    f"##### {course['code']} {course['name']}",
                    "",
                    f"- Department: {departments.get(course['dept'], {'name': course['dept']})['name']} ({course['dept']})",
                    f"- Credit hours: {course['credit_hours']}",
                    f"- Category: {course['category']}",
                    f"- Instructors: {instructors}",
                    f"- Keywords: {', '.join(course['keywords'])}",
                    "",
                    course["description"],
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


ACTION_MODULE = '''"""Importable FCI academic catalog snapshot for BuddyBot actions.

Generated by tools/export_fci_academic_catalog.py.
Do not edit the generated JSON manually; rerun the exporter after DB updates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

DATA_PATH = Path(__file__).with_name("fci_academic_catalog_data.json")


def _load() -> dict:
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


_DATA = _load()
DEPARTMENTS: Dict[str, dict] = _DATA["departments"]
COURSES: Dict[str, dict] = _DATA["courses"]


def get_course(code: str) -> Optional[dict]:
    """Return a course dict by exact code (case-insensitive)."""
    return COURSES.get(str(code or "").upper())


def get_department(code: str) -> Optional[dict]:
    """Return a department dict by dept_code (case-insensitive)."""
    return DEPARTMENTS.get(str(code or "").upper())


def find_courses_by_instructor(name: str) -> List[dict]:
    """Return all courses taught by an instructor (partial name match)."""
    query = str(name or "").lower().strip()
    if not query:
        return []
    results = []
    for code, course in COURSES.items():
        if any(query in instructor.lower() for instructor in course.get("instructors", [])):
            results.append({"code": code, **course})
    return sorted(results, key=lambda item: (item["year"], item["semester"], item["code"]))


def find_courses_by_keyword(query: str) -> List[dict]:
    """Search across course code, name, description, and keywords."""
    q = str(query or "").lower().strip()
    if not q:
        return []
    results = []
    for code, course in COURSES.items():
        searchable = " ".join(
            [
                code,
                course.get("name", ""),
                course.get("description", ""),
                " ".join(course.get("keywords", [])),
            ]
        ).lower()
        if q in searchable:
            results.append({"code": code, **course})
    return sorted(results, key=lambda item: (item["year"], item["semester"], item["code"]))


def get_courses_by_dept(dept_code: str) -> List[dict]:
    """Return all courses for a department, sorted by year then semester."""
    dept = str(dept_code or "").upper()
    return sorted(
        [{"code": code, **course} for code, course in COURSES.items() if course.get("dept") == dept],
        key=lambda item: (item["year"], item["semester"], item["code"]),
    )


def get_courses_by_year_semester(year: int, semester: int, dept_code: str | None = None) -> List[dict]:
    """Return courses for a year/semester, optionally filtered by department."""
    dept = str(dept_code or "").upper() if dept_code else None
    results = []
    for code, course in COURSES.items():
        if course.get("year") == year and course.get("semester") == semester:
            if dept is None or course.get("dept") == dept:
                results.append({"code": code, **course})
    return sorted(results, key=lambda item: (item["dept"], item["code"]))


def format_course_answer(code: str) -> str:
    """Return a natural-language summary for a course."""
    course = get_course(code)
    if not course:
        return f"I couldn't find a course with code {code}."
    department = DEPARTMENTS.get(course.get("dept"), {"name": course.get("dept", "Unknown")})
    instructors = ", ".join(course.get("instructors") or []) or "TBA"
    return (
        f"**{course['name']}** ({str(code).upper()}) - {course['credit_hours']} credit hours\\n"
        f"Department: {department['name']} | Year {course['year']}, Semester {course['semester']}\\n"
        f"{course['description']}\\n"
        f"Taught by: {instructors}"
    )


def format_instructor_courses_answer(name: str) -> str:
    """Return a natural-language summary of all courses an instructor teaches."""
    courses = find_courses_by_instructor(name)
    if not courses:
        return f"I couldn't find any courses taught by '{name}'."
    lines = [f"Courses taught by {name}:"]
    for course in courses:
        department = DEPARTMENTS.get(course.get("dept"), {"name": course.get("dept", "Unknown")})
        lines.append(
            f"- {course['code']} - {course['name']} "
            f"(Year {course['year']}, Semester {course['semester']}, {department['name']})"
        )
    return "\\n".join(lines)
'''


def write_outputs(catalog: Dict[str, Any], action_data: Path, action_module: Path, rag_output: Path) -> None:
    action_data.parent.mkdir(parents=True, exist_ok=True)
    rag_output.parent.mkdir(parents=True, exist_ok=True)
    with action_data.open("w", encoding="utf-8") as handle:
        json.dump(catalog, handle, ensure_ascii=False, indent=2)
    action_module.write_text(ACTION_MODULE, encoding="utf-8")
    rag_output.write_text(markdown_for_catalog(catalog), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export FCI academic catalog from SQL Server.")
    parser.add_argument("--sql-engine-path", type=Path, default=DEFAULT_SQL_ENGINE)
    parser.add_argument("--action-data", type=Path, default=DEFAULT_ACTION_DATA)
    parser.add_argument("--action-module", type=Path, default=DEFAULT_ACTION_MODULE)
    parser.add_argument("--rag-output", type=Path, default=DEFAULT_RAG_OUTPUT)
    args = parser.parse_args()

    rows = fetch_catalog_rows(args.sql_engine_path)
    catalog = build_catalog(rows)
    write_outputs(catalog, args.action_data, args.action_module, args.rag_output)

    print(f"Exported {len(catalog['departments'])} departments")
    print(f"Exported {len(catalog['courses'])} courses")
    print(f"Action data: {args.action_data}")
    print(f"Action module: {args.action_module}")
    print(f"RAG markdown: {args.rag_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
