"""Compatibility import for BuddyBot's FCI academic knowledge base.

The generated catalog lives in ``fci_academic_catalog.py``.  This wrapper keeps
the shorter ``fci_knowledge_base`` name available for actions and tests.
"""

from __future__ import annotations

try:
    from actions.fci_academic_catalog import (  # type: ignore
        COURSES,
        DEPARTMENTS,
        find_courses_by_instructor,
        find_courses_by_keyword,
        format_course_answer,
        format_instructor_courses_answer,
        get_course,
        get_courses_by_dept,
        get_courses_by_year_semester,
        get_department,
    )
except ImportError:
    from fci_academic_catalog import (  # type: ignore
        COURSES,
        DEPARTMENTS,
        find_courses_by_instructor,
        find_courses_by_keyword,
        format_course_answer,
        format_instructor_courses_answer,
        get_course,
        get_courses_by_dept,
        get_courses_by_year_semester,
        get_department,
    )

