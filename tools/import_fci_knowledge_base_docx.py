"""Import the curated FCI_Knowledge_Base.docx catalog into BuddyBot.

This parser avoids a python-docx dependency by reading the DOCX XML directly.
It writes the JSON file used by actions/fci_academic_catalog.py and
actions/fci_knowledge_base.py.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(
    r"E:\OneDrive - Sadat Academy for Management Sciences\FinalYear\Grad_Project\FCI_Knowledge_Base.docx"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "actions" / "fci_academic_catalog_data.json"
DEFAULT_RAG_MARKDOWN = Path(r"C:\dev\rag_service\knowledge_base\faculty\courses\fci_course_catalog_2025_2026.md")

LABELS = {
    "Course Code",
    "Course Name",
    "Department",
    "Year / Semester",
    "Credit Hours",
    "Description",
    "Instructors",
    "Keywords",
}
SECTION_BREAKS = {
    "Department Overview",
    "Learning Objectives",
    "Career Pathways",
    "Key Tools & Technologies",
    "Courses",
}

DEPARTMENT_CODE_BY_NAME = {
    "General Studies (Years 1-2)": "GEN",
    "General Studies (Years 1–2)": "GEN",
    "Computer Sciences": "CS",
    "Artificial Intelligence": "AI",
    "Cyber Security": "CSCS",
    "Information Systems & Data Science": "ISDS",
    "Software Engineering": "SE",
}


def docx_lines(path: Path) -> List[str]:
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")
    root = ET.fromstring(document_xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    lines: List[str] = []
    for paragraph in root.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
        if text:
            lines.append(re.sub(r"\s+", " ", text))
    return lines


def normalize_department_name(name: str) -> str:
    return name.replace("–", "-").strip()


def department_code(name: str) -> str:
    normalized = normalize_department_name(name)
    return DEPARTMENT_CODE_BY_NAME.get(name) or DEPARTMENT_CODE_BY_NAME.get(normalized) or normalized.upper()


def collect_section_lines(lines: List[str], start: int, label: str, stop_labels: set[str]) -> List[str]:
    try:
        label_index = lines.index(label, start)
    except ValueError:
        return []
    collected: List[str] = []
    for line in lines[label_index + 1 :]:
        if line in stop_labels or line in LABELS:
            break
        if re.match(r"^[A-Z]{2,5}\d{3}\s+", line):
            break
        if line and line != label:
            collected.append(line)
    return collected


def parse_departments(lines: List[str]) -> Dict[str, dict]:
    departments: Dict[str, dict] = {}
    for index, line in enumerate(lines):
        if line != "Department Overview" or index == 0 or index + 1 >= len(lines):
            continue
        title = re.split(r"\s+[—-]\s+", lines[index - 1], maxsplit=1)[0].strip()
        code = department_code(title)
        objectives = collect_section_lines(lines, index, "Learning Objectives", {"Career Pathways", "Key Tools & Technologies", "Courses"})
        careers = collect_section_lines(lines, index, "Career Pathways", {"Key Tools & Technologies", "Courses"})
        tools = collect_section_lines(lines, index, "Key Tools & Technologies", {"Courses"})
        departments[code] = {
            "name": normalize_department_name(title),
            "code": code,
            "description": lines[index + 1].strip(),
            "objectives": objectives,
            "careers": careers,
            "tools": tools,
        }
    return departments


def value_after(lines: List[str], start: int, label: str) -> str:
    try:
        label_index = lines.index(label, start)
    except ValueError:
        return ""
    value_lines: List[str] = []
    for absolute_index, line in enumerate(lines[label_index + 1 :], start=label_index + 1):
        next_line = lines[absolute_index + 1] if absolute_index + 1 < len(lines) else ""
        if (
            line in LABELS
            or line in SECTION_BREAKS
            or next_line == "Department Overview"
            or (label != "Year / Semester" and re.match(r"^Year\s+\d+\s+[·\u00b7]\s+Semester\s+\d+", line))
            or re.match(r"^[A-Z]{2,5}\d{3}\s+[—-]\s+", line)
        ):
            break
        value_lines.append(line)
    return " ".join(value_lines).strip()


def parse_courses(lines: List[str]) -> Dict[str, dict]:
    courses: Dict[str, dict] = {}
    for index, line in enumerate(lines):
        if line != "Course Code" or index + 1 >= len(lines):
            continue
        code = lines[index + 1].strip().upper()
        if not re.fullmatch(r"[A-Z]{2,5}\d{3}", code):
            continue

        name = value_after(lines, index, "Course Name")
        department_name = value_after(lines, index, "Department")
        year_semester = value_after(lines, index, "Year / Semester")
        credit_hours = value_after(lines, index, "Credit Hours")
        description = value_after(lines, index, "Description")
        instructors = value_after(lines, index, "Instructors")
        keywords = value_after(lines, index, "Keywords")
        keywords = re.sub(r"\s+Year\s+\d+\s+[·\u00b7]\s+Semester\s+\d+.*$", "", keywords).strip()

        year_match = re.search(r"Year\s+(\d+)", year_semester, flags=re.I)
        semester_match = re.search(r"Semester\s+(\d+)", year_semester, flags=re.I)
        dept_code = department_code(department_name)

        courses[code] = {
            "name": name,
            "dept": dept_code,
            "year": int(year_match.group(1)) if year_match else None,
            "semester": int(semester_match.group(1)) if semester_match else None,
            "credit_hours": int(credit_hours) if credit_hours.isdigit() else credit_hours,
            "category": "general" if dept_code == "GEN" else "major",
            "description": description,
            "instructors": [item.strip() for item in instructors.split(",") if item.strip()],
            "keywords": [item.strip() for item in keywords.split(",") if item.strip()],
        }
    return courses


def write_markdown_catalog(data: dict, path: Path) -> None:
    departments = data["departments"]
    courses = data["courses"]
    lines = [
        "# FCI Course Catalog 2025-2026",
        "",
        "Source: FCI_Knowledge_Base.docx",
        "Category: course_catalog",
        "",
    ]
    for dept_code, department in departments.items():
        lines.extend(
            [
                f"## {department['name']} ({dept_code})",
                "",
                department.get("description", ""),
                "",
            ]
        )
        if department.get("objectives"):
            lines.extend(["Learning objectives:", *[f"- {item}" for item in department["objectives"]], ""])
        if department.get("careers"):
            lines.extend(["Career pathways:", *[f"- {item}" for item in department["careers"]], ""])
        if department.get("tools"):
            lines.extend(["Key tools and technologies:", *[f"- {item}" for item in department["tools"]], ""])
        dept_courses = [
            (code, course)
            for code, course in courses.items()
            if course.get("dept") == dept_code
        ]
        current_bucket = None
        for code, course in sorted(dept_courses, key=lambda item: (item[1].get("year") or 0, item[1].get("semester") or 0, item[0])):
            bucket = f"Year {course.get('year')} · Semester {course.get('semester')}"
            if bucket != current_bucket:
                lines.extend([f"### {bucket}", ""])
                current_bucket = bucket
            instructors = ", ".join(course.get("instructors") or []) or "TBA"
            keywords = ", ".join(course.get("keywords") or [])
            lines.extend(
                [
                    f"#### {code} — {course.get('name')}",
                    "",
                    f"- Department: {department['name']} ({dept_code})",
                    f"- Credit hours: {course.get('credit_hours')}",
                    f"- Instructors: {instructors}",
                    f"- Keywords: {keywords}",
                    "",
                    str(course.get("description") or ""),
                    "",
                ]
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--rag-markdown", type=Path, default=DEFAULT_RAG_MARKDOWN)
    args = parser.parse_args()

    lines = docx_lines(args.source)
    data = {
        "departments": parse_departments(lines),
        "courses": parse_courses(lines),
        "source": str(args.source),
        "academic_year": "2025-2026",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown_catalog(data, args.rag_markdown)
    print(f"Imported {len(data['departments'])} departments and {len(data['courses'])} courses")
    print(f"Wrote {args.output}")
    print(f"Wrote {args.rag_markdown}")


if __name__ == "__main__":
    main()
