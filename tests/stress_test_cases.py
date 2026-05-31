"""Stress-test dataset for BuddyBot.

Each case includes:
- user_message
- expected_intent
- expected_entities
- expected_route: SQL, RAG, SQL+RAG, or clarification
- expected_behavior
- pass_fail: filled by the runner

The list is built with explicit realistic utterances so it stays readable while
still being easy to export as JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


TEST_CASES: List[Dict[str, Any]] = []


def add(
    message: str,
    intent: str,
    route: str,
    behavior: str,
    entities: Optional[Dict[str, List[str]]] = None,
    session_id: Optional[str] = None,
    contains: Optional[List[str]] = None,
) -> None:
    TEST_CASES.append(
        {
            "id": f"TC{len(TEST_CASES) + 1:03d}",
            "user_message": message,
            "expected_intent": intent,
            "expected_entities": entities or {},
            "expected_route": route,
            "expected_behavior": behavior,
            "expected_response_contains": contains or [],
            "session_id": session_id,
            "pass_fail": None,
        }
    )


def bulk(rows: Iterable[tuple]) -> None:
    for row in rows:
        add(*row)


bulk(
    [
        ("show my GPA", "student_gpa_query", "SQL", "Use selected/current student and return GPA.", {"metric": ["GPA"]}, "ctx_student", ["GPA"]),
        ("what is my CGPA", "student_gpa_query", "SQL", "Use selected/current student and return cumulative GPA.", {"metric": ["GPA"]}, "ctx_student", ["GPA"]),
        ("show GPA for student 2122209", "student_gpa_query", "SQL", "Return GPA for StudentID 2122209.", {"student_id": ["2122209"], "metric": ["GPA"]}, None, ["2122209"]),
        ("what is the GPA of student 2122136", "student_gpa_query", "SQL", "Return GPA for the given student ID.", {"student_id": ["2122136"], "metric": ["GPA"]}),
        ("calculate GPA for 2122248", "student_gpa_query", "SQL", "Return GPA for the given student ID.", {"student_id": ["2122248"], "metric": ["GPA"]}),
        ("what is Mazen GPA", "student_gpa_query", "clarification", "Detect multiple Mazen students and ask which one.", {"student_name": ["Mazen"], "metric": ["GPA"]}, "amb_mazen", ["Which one"]),
        ("show Mazen Mohamed GPA", "student_gpa_query", "clarification", "Clarify if more than one Mazen Mohamed exists.", {"student_name": ["Mazen Mohamed"], "metric": ["GPA"]}),
        ("gpa for Sama", "student_gpa_query", "clarification", "Clarify which Sama because several students match.", {"student_name": ["Sama"], "metric": ["GPA"]}),
        ("and the gpa", "student_gpa_query", "SQL", "Use prior selected student context.", {"metric": ["GPA"]}, "ctx_student"),
        ("what about his cgpa", "student_gpa_query", "SQL", "Resolve pronoun to selected student.", {"metric": ["GPA"]}, "ctx_student"),
        ("average GPA", "student_gpa_query", "SQL", "Return aggregate average GPA.", {"metric": ["GPA"]}),
        ("highest GPA", "student_gpa_query", "SQL", "Return highest GPA students.", {"metric": ["GPA"], "sort_order": ["highest"]}),
        ("lowest GPA", "student_gpa_query", "SQL", "Return lowest GPA students.", {"metric": ["GPA"], "sort_order": ["lowest"]}),
        ("show top GPA students", "student_gpa_query", "SQL", "Return top students by GPA.", {"metric": ["GPA"], "sort_order": ["top"]}),
        ("average gpa by department", "student_gpa_query", "SQL", "Group GPA by department.", {"metric": ["GPA", "department"]}),
        ("average gpa by group", "student_gpa_query", "SQL", "Group GPA by group.", {"metric": ["GPA", "group"]}),
        ("can u show my gpa", "student_gpa_query", "SQL", "Slang version of current student GPA.", {"metric": ["GPA"]}, "ctx_student"),
        ("cgpa?", "student_gpa_query", "SQL", "Incomplete GPA follow-up should use context.", {"metric": ["GPA"]}, "ctx_student"),
    ]
)

bulk(
    [
        ("grades for 2122209", "student_grades_query", "SQL", "Return grades for StudentID 2122209.", {"student_id": ["2122209"]}, None, ["2122209"]),
        ("show grades for student 2122136", "student_grades_query", "SQL", "Return grade rows for the student.", {"student_id": ["2122136"]}),
        ("marks of student 2122136", "student_grades_query", "SQL", "Return marks for the student.", {"student_id": ["2122136"]}),
        ("show marks for Mazen", "student_grades_query", "clarification", "Clarify which Mazen before returning marks.", {"student_name": ["Mazen"]}, "amb_grades", ["Which one"]),
        ("what are Mazen grades", "student_grades_query", "clarification", "Clarify which Mazen before returning grades.", {"student_name": ["Mazen"]}),
        ("show my grades", "student_grades_query", "SQL", "Use current student context.", {}, "ctx_student"),
        ("what about his grades", "student_grades_query", "SQL", "Resolve pronoun to selected student.", {}, "ctx_student"),
        ("what marks did he get", "student_grades_query", "SQL", "Resolve pronoun and return marks.", {}, "ctx_student"),
        ("result for student 2122209", "student_grades_query", "SQL", "Return grade result summary.", {"student_id": ["2122209"]}),
        ("score for AI301 for student 2122209", "student_grades_query", "SQL", "Return one course score.", {"student_id": ["2122209"], "course_code": ["AI301"]}),
        ("what did student 2122136 get in AI301", "student_grades_query", "SQL", "Return course mark for the given student/course.", {"student_id": ["2122136"], "course_code": ["AI301"]}),
        ("show course marks for 2122209", "student_grades_query", "SQL", "Return all course marks.", {"student_id": ["2122209"]}),
        ("grades?", "student_grades_query", "SQL", "Incomplete follow-up should use selected student.", {}, "ctx_student"),
        ("marks plz", "student_grades_query", "SQL", "Slang request should use selected student.", {}, "ctx_student"),
        ("show his AI301 mark", "student_grades_query", "SQL", "Resolve pronoun and course code.", {"course_code": ["AI301"]}, "ctx_student"),
        ("did she get A in database", "student_grades_query", "SQL", "Resolve pronoun and course phrase.", {"course_name": ["database"]}, "ctx_student"),
    ]
)

bulk(
    [
        ("what courses did Mazen fail", "student_failed_courses_query", "clarification", "Clarify which Mazen before listing failed courses.", {"student_name": ["Mazen"]}, "amb_fail"),
        ("failed courses for Mazen", "student_failed_courses_query", "clarification", "Clarify ambiguous student name.", {"student_name": ["Mazen"]}),
        ("show failed subjects for student 2122209", "student_failed_courses_query", "SQL", "Return failed courses for student.", {"student_id": ["2122209"]}),
        ("did student 2122136 fail anything", "student_failed_courses_query", "SQL", "Return failed/passed status for student.", {"student_id": ["2122136"]}),
        ("who failed Database", "student_failed_courses_query", "SQL", "Return students who failed course phrase Database.", {"course_name": ["Database"]}),
        ("students who failed AI301", "student_failed_courses_query", "SQL", "Return failed rows for AI301.", {"course_code": ["AI301"]}),
        ("list failing students", "student_failed_courses_query", "SQL", "Return all failing student records.", {}),
        ("show all failed courses", "student_failed_courses_query", "SQL", "Return failed course records.", {}),
        ("what subjects did he fail", "student_failed_courses_query", "SQL", "Resolve selected student context.", {}, "ctx_student"),
        ("show his failed courses", "student_failed_courses_query", "SQL", "Resolve selected student context.", {}, "ctx_student"),
        ("failed marks for 2122209", "student_failed_courses_query", "SQL", "Return failed marks for student.", {"student_id": ["2122209"]}),
        ("courses below pass for Mazen Mohamed", "student_failed_courses_query", "clarification", "Clarify among matching Mazen Mohamed students.", {"student_name": ["Mazen Mohamed"]}),
        ("any fails?", "student_failed_courses_query", "SQL", "Incomplete follow-up should use selected student.", {}, "ctx_student"),
        ("did Mazen drop below pass", "student_failed_courses_query", "clarification", "Clarify ambiguous Mazen name.", {"student_name": ["Mazen"]}),
    ]
)

bulk(
    [
        ("show my schedule", "student_schedule_query", "SQL", "Use selected/current student and return timetable.", {}, "ctx_student"),
        ("what classes do I have tomorrow", "student_schedule_query", "SQL", "Use selected student and tomorrow day filter.", {"day": ["tomorrow"]}, "ctx_student"),
        ("do I have lectures tomorrow", "student_schedule_query", "SQL", "Return tomorrow lectures for selected student.", {"day": ["tomorrow"]}, "ctx_student"),
        ("do i have class today", "student_schedule_query", "SQL", "Return today's classes for selected student.", {"day": ["today"]}, "ctx_student"),
        ("my timetable for Sunday", "student_schedule_query", "SQL", "Return Sunday schedule for selected student.", {"day": ["Sunday"]}, "ctx_student"),
        ("schedule for student 2122209", "student_schedule_query", "SQL", "Return schedule for StudentID 2122209.", {"student_id": ["2122209"]}),
        ("show schedule for Mazen", "student_schedule_query", "clarification", "Clarify ambiguous Mazen before schedule.", {"student_name": ["Mazen"]}),
        ("what about his schedule", "followup_query", "SQL", "Resolve pronoun and return schedule.", {}, "ctx_student"),
        ("show his timetable", "student_schedule_query", "SQL", "Resolve selected student and return timetable.", {}, "ctx_student"),
        ("schedule for group AI 1", "student_schedule_query", "SQL", "Return schedule for AI group.", {"group_code": ["AI 1"]}),
        ("what is the schedule for AI 1", "student_schedule_query", "SQL", "Return schedule for AI group.", {"group_code": ["AI 1"]}),
        ("show CS1 timetable", "student_schedule_query", "SQL", "Return CS1 timetable.", {"group_code": ["CS1"]}),
        ("labs on Sunday", "student_schedule_query", "SQL", "Return lab schedule on Sunday.", {"day": ["Sunday"]}),
        ("show labs on Tuesday", "student_schedule_query", "SQL", "Return labs on Tuesday.", {"day": ["Tuesday"]}),
        ("lectures on Monday", "student_schedule_query", "SQL", "Return lectures on Monday.", {"day": ["Monday"]}),
        ("which room has AI301", "room_query", "SQL", "Return room/location for AI301.", {"course_code": ["AI301"]}),
        ("when is Database Systems", "student_schedule_query", "SQL", "Return schedule for course phrase.", {"course_name": ["Database Systems"]}),
        ("schedule tmrw", "student_schedule_query", "SQL", "Typo/slang tomorrow schedule.", {"day": ["tomorrow"]}, "ctx_student"),
        ("class now?", "student_schedule_query", "SQL", "Incomplete current class query.", {}, "ctx_student"),
        ("do we have lab sunday", "student_schedule_query", "SQL", "Lab schedule Sunday.", {"day": ["Sunday"]}),
        ("where is my next lecture", "student_schedule_query", "SQL", "Use selected student context.", {}, "ctx_student"),
        ("same group tomorrow", "followup_query", "SQL", "Use previous group context and tomorrow filter.", {"day": ["tomorrow"]}, "ctx_group"),
    ]
)

bulk(
    [
        ("list rooms", "room_query", "SQL", "Return rooms.", {}),
        ("show all rooms", "room_query", "SQL", "Return all rooms.", {}),
        ("show labs", "room_query", "SQL", "Return lab rooms.", {}),
        ("list halls", "room_query", "SQL", "Return halls.", {}),
        ("show classrooms", "room_query", "SQL", "Return classrooms.", {}),
        ("room capacity", "room_query", "SQL", "Return room capacities.", {}),
        ("capacity of Hall 3", "room_query", "SQL", "Return Hall 3 capacity.", {"room": ["Hall 3"]}),
        ("what course is in Hall 3", "room_query", "SQL", "Return schedule for Hall 3.", {"room": ["Hall 3"]}),
        ("classes in Lab 1", "room_query", "SQL", "Return classes scheduled in Lab 1.", {"room": ["Lab 1"]}),
        ("show room schedule for Room B1", "room_query", "SQL", "Return Room B1 schedule.", {"room": ["Room B1"]}),
        ("free rooms now", "free_room_query", "SQL", "Return currently free rooms.", {}),
        ("which rooms are free now", "free_room_query", "SQL", "Return currently free rooms.", {}),
        ("available rooms", "free_room_query", "SQL", "Return available rooms.", {}),
        ("empty rooms", "free_room_query", "SQL", "Return empty rooms.", {}),
        ("vacant labs", "free_room_query", "SQL", "Return vacant labs.", {}),
        ("free labs on Sunday", "free_room_query", "SQL", "Return free labs on Sunday.", {"day": ["Sunday"]}),
        ("rooms available at 2 PM", "free_room_query", "SQL", "Return rooms free at 2 PM.", {"time": ["2 PM"]}),
        ("free rooms tomorrow", "free_room_query", "SQL", "Return rooms free tomorrow.", {"day": ["tomorrow"]}),
        ("is Hall 3 free now", "free_room_query", "SQL", "Check Hall 3 availability.", {"room": ["Hall 3"]}),
        ("any lab free at 10:00", "free_room_query", "SQL", "Return labs free at 10:00.", {"time": ["10:00"]}),
    ]
)

bulk(
    [
        ("who teaches AI301", "course_instructor_query", "SQL", "Return instructors for AI301.", {"course_code": ["AI301"]}),
        ("who is teaching Database Systems", "course_instructor_query", "SQL", "Return instructor for course phrase.", {"course_name": ["Database Systems"]}),
        ("instructor for AI301", "course_instructor_query", "SQL", "Return AI301 instructor.", {"course_code": ["AI301"]}),
        ("teacher of Machine Learning", "course_instructor_query", "SQL", "Return instructor for course phrase.", {"course_name": ["Machine Learning"]}),
        ("which faculty teaches DBMS", "course_instructor_query", "SQL", "Return DBMS instructor.", {"course_name": ["DBMS"]}),
        ("who teaches AI", "course_instructor_query", "SQL", "Return instructors teaching AI courses.", {"department": ["AI"]}),
        ("who teaches CS courses", "course_instructor_query", "SQL", "Return instructors for CS courses.", {"department": ["CS"]}),
        ("professor for AI301", "course_instructor_query", "SQL", "Return professor for AI301.", {"course_code": ["AI301"]}),
        ("faculty assigned to Natural Language Processing", "course_instructor_query", "SQL", "Return NLP faculty.", {"course_name": ["Natural Language Processing"]}),
        ("list instructors", "instructor_query", "SQL", "Return instructors.", {}),
        ("list faculty", "instructor_query", "SQL", "Return faculty/instructors.", {}),
        ("show professors", "instructor_query", "SQL", "Return professors/instructors.", {}),
        ("show all instructors", "instructor_query", "SQL", "Return all instructors.", {}),
        ("instructors in Software Engineering", "instructor_query", "SQL", "Return SE instructors.", {"department": ["Software Engineering"]}),
        ("who are the instructors in AI", "instructor_query", "SQL", "Return AI instructors.", {"department": ["AI"]}),
        ("show instructor workload report", "instructor_query", "SQL", "Return instructor workload.", {"metric": ["workload"]}),
        ("which instructor teaches the most courses", "instructor_query", "SQL", "Return highest workload instructor.", {"sort_order": ["top"]}),
        ("classes taught by Yasser Salah Eldin", "instructor_query", "SQL", "Return instructor schedule/classes.", {"instructor_name": ["Yasser Salah Eldin"]}),
    ]
)

bulk(
    [
        ("list all courses", "course_info_query", "SQL", "Return course list.", {}),
        ("show courses", "course_info_query", "SQL", "Return course list.", {}),
        ("list AI courses", "course_info_query", "SQL", "Return AI courses.", {"department": ["AI"]}),
        ("list CS subjects", "course_info_query", "SQL", "Return CS courses.", {"department": ["CS"]}),
        ("courses for Software Engineering", "course_info_query", "SQL", "Return SE courses.", {"department": ["Software Engineering"]}),
        ("what courses belong to third year AI", "course_info_query", "SQL", "Return third-year AI courses.", {"department": ["AI"]}),
        ("show year 3 semester 1 courses", "course_info_query", "SQL", "Return year 3 semester 1 courses.", {"semester": ["1"]}),
        ("credit hours for AI301", "course_info_query", "SQL", "Return credit hours for AI301.", {"course_code": ["AI301"]}),
        ("what is AI301", "course_info_query", "SQL", "Return course info for AI301.", {"course_code": ["AI301"]}),
        ("tell me about Database Systems", "course_info_query", "SQL", "Return course info for Database Systems.", {"course_name": ["Database Systems"]}),
        ("course info for Machine Learning", "course_info_query", "SQL", "Return course info for Machine Learning.", {"course_name": ["Machine Learning"]}),
        ("subjects in DS", "course_info_query", "SQL", "Return ISDS courses.", {"department": ["DS"]}),
        ("how many courses are in the database", "course_info_query", "SQL", "Return course count.", {}),
        ("show general courses", "course_info_query", "SQL", "Return general courses.", {}),
        ("show major courses", "course_info_query", "SQL", "Return major courses.", {}),
        ("AI301 credits?", "course_info_query", "SQL", "Incomplete credit-hours query.", {"course_code": ["AI301"]}),
        ("subjcts for AI", "course_info_query", "SQL", "Typo should still route to courses.", {"department": ["AI"]}),
        ("3rd year SE subjects", "course_info_query", "SQL", "Return third-year SE subjects.", {"department": ["SE"]}),
    ]
)

bulk(
    [
        ("list departments", "department_query", "SQL", "Return departments.", {}),
        ("show all departments", "department_query", "SQL", "Return all departments.", {}),
        ("what departments exist", "department_query", "SQL", "Return department list.", {}),
        ("show majors", "department_query", "SQL", "Return majors/departments.", {}),
        ("list majors", "department_query", "SQL", "Return majors.", {}),
        ("how many students are in AI", "department_query", "SQL", "Return AI student count.", {"department": ["AI"]}),
        ("how many students are in CS", "department_query", "SQL", "Return CS student count.", {"department": ["CS"]}),
        ("student breakdown by department", "department_query", "SQL", "Return department breakdown.", {}),
        ("percentage of students by department", "department_query", "SQL", "Return department percentages.", {}),
        ("count students by major", "department_query", "SQL", "Return student counts by major.", {}),
        ("tell me about Software Engineering", "department_query", "SQL", "Return SE department info.", {"department": ["Software Engineering"]}),
        ("show Information Systems and Data Science", "department_query", "SQL", "Return ISDS department info.", {"department": ["Information Systems and Data Science"]}),
        ("departmnts", "department_query", "SQL", "Typo should route to department list.", {}),
        ("majors?", "department_query", "SQL", "Short department query.", {}),
    ]
)

bulk(
    [
        ("show reset subjects", "reset_courses_query", "SQL", "Return reset/repeated course records or none found.", {}),
        ("show reset courses", "reset_courses_query", "SQL", "Return reset course records.", {}),
        ("list reset subjects", "reset_courses_query", "SQL", "Return reset subjects.", {}),
        ("reset courses for student 2122209", "reset_courses_query", "SQL", "Return reset courses for student.", {"student_id": ["2122209"]}),
        ("does Mazen have reset courses", "reset_courses_query", "clarification", "Clarify ambiguous Mazen before reset query.", {"student_name": ["Mazen"]}),
        ("which students have reset subjects", "reset_courses_query", "SQL", "Return students with reset subjects.", {}),
        ("repeated courses", "reset_courses_query", "SQL", "Return repeated courses.", {}),
        ("retaken subjects", "reset_courses_query", "SQL", "Return retaken subjects.", {}),
        ("subjects repeated by 2122136", "reset_courses_query", "SQL", "Return repeated subjects for student.", {"student_id": ["2122136"]}),
        ("any reset?", "reset_courses_query", "SQL", "Incomplete reset query.", {}, "ctx_student"),
    ]
)

bulk(
    [
        ("top students by GPA", "analytics_query", "SQL", "Return top GPA ranking.", {"metric": ["GPA"], "sort_order": ["top"]}),
        ("highest gpa students", "analytics_query", "SQL", "Return highest GPA students.", {"metric": ["GPA"]}),
        ("lowest gpa students", "analytics_query", "SQL", "Return lowest GPA students.", {"metric": ["GPA"]}),
        ("average GPA by department", "analytics_query", "SQL", "Return average GPA by department.", {"metric": ["GPA"]}),
        ("average GPA by group", "analytics_query", "SQL", "Return average GPA by group.", {"metric": ["GPA"]}),
        ("how many students by group", "analytics_query", "SQL", "Return student counts by group.", {}),
        ("count students by department", "analytics_query", "SQL", "Return student counts by department.", {}),
        ("instructor workload", "analytics_query", "SQL", "Return workload analytics.", {"metric": ["workload"]}),
        ("course statistics", "analytics_query", "SQL", "Return course analytics.", {}),
        ("department analytics", "analytics_query", "SQL", "Return department analytics.", {}),
        ("schedule conflicts", "analytics_query", "SQL", "Return schedule conflict analytics if supported.", {}),
        ("busiest instructor", "analytics_query", "SQL", "Return instructor with highest workload.", {"sort_order": ["top"]}),
        ("courses with most failures", "analytics_query", "SQL", "Return failure counts by course.", {"metric": ["failures"]}),
        ("students on academic warning", "analytics_query", "SQL", "Return academic warning list if stored.", {}),
        ("show top 5 students by gpa", "analytics_query", "SQL", "Return top 5 GPA students.", {"limit": ["5"], "metric": ["GPA"]}),
        ("which department has the most students", "analytics_query", "SQL", "Return largest department by student count.", {}),
    ]
)

bulk(
    [
        ("show Mazen GPA", "student_gpa_query", "clarification", "Ask which Mazen.", {"student_name": ["Mazen"], "metric": ["GPA"]}, "amb_flow", ["Which one"]),
        ("the one in DS", "clarification_response", "SQL", "Resolve pending candidate by group and answer pending question.", {"group_code": ["DS"]}, "amb_flow", ["Got it"]),
        ("show his failed courses", "student_failed_courses_query", "SQL", "Use selected Mazen from previous clarification.", {}, "amb_flow"),
        ("show his schedule", "student_schedule_query", "SQL", "Use selected Mazen from previous clarification.", {}, "amb_flow"),
        ("show Mazen grades", "student_grades_query", "clarification", "Ask which Mazen for grades.", {"student_name": ["Mazen"]}, "amb_grades_flow", ["Which one"]),
        ("number 3", "clarification_response", "SQL", "Resolve pending candidate by ordinal number.", {"limit": ["3"]}, "amb_grades_flow"),
        ("what about his GPA", "student_gpa_query", "SQL", "Use selected candidate from previous turn.", {"metric": ["GPA"]}, "amb_grades_flow"),
        ("show Mazen schedule", "student_schedule_query", "clarification", "Ask which Mazen for schedule.", {"student_name": ["Mazen"]}, "amb_schedule_flow"),
        ("student 2122323", "clarification_response", "SQL", "Resolve by full student ID.", {"student_id": ["2122323"]}, "amb_schedule_flow"),
        ("what about his grades", "student_grades_query", "SQL", "Use selected student after ID resolution.", {}, "amb_schedule_flow"),
        ("first one", "clarification_response", "clarification", "Should only work when pending candidates exist; otherwise ask for context.", {}, "no_pending"),
        ("the AI one", "clarification_response", "clarification", "Resolve by department/group when pending candidates exist.", {"department": ["AI"]}, "amb_department_flow"),
        ("same group", "followup_query", "SQL", "Use previous group context.", {}, "ctx_group"),
        ("same student", "followup_query", "SQL", "Use previous selected student.", {}, "ctx_student"),
        ("what about tomorrow", "followup_query", "SQL", "Use previous schedule/group/student context plus tomorrow.", {"day": ["tomorrow"]}, "ctx_student"),
        ("only labs", "followup_query", "SQL", "Apply lab filter to previous schedule context.", {}, "ctx_group"),
        ("sort by highest", "followup_query", "SQL", "Apply sort order to previous analytics context.", {"sort_order": ["highest"]}, "ctx_analytics"),
        ("show top 5", "followup_query", "SQL", "Apply limit to previous analytics context.", {"limit": ["5"]}, "ctx_analytics"),
    ]
)

bulk(
    [
        ("shw my gpa", "student_gpa_query", "SQL", "Typo should still route to GPA.", {"metric": ["GPA"]}, "ctx_student"),
        ("garde for 2122209", "student_grades_query", "SQL", "Typo should still route to grades.", {"student_id": ["2122209"]}),
        ("schedual for AI 1", "student_schedule_query", "SQL", "Typo should still route to schedule.", {"group_code": ["AI 1"]}),
        ("free roms now", "free_room_query", "SQL", "Typo should still route to free rooms.", {}),
        ("who teches AI301", "course_instructor_query", "SQL", "Typo should still route to course instructor.", {"course_code": ["AI301"]}),
        ("dept students AI", "department_query", "SQL", "Slang department-count style query.", {"department": ["AI"]}),
        ("Mazen?", "student_profile_query", "clarification", "Incomplete ambiguous name should clarify.", {"student_name": ["Mazen"]}),
        ("AI301?", "course_info_query", "SQL", "Incomplete course-code query should return course info.", {"course_code": ["AI301"]}),
        ("tomorrow?", "followup_query", "SQL", "Incomplete temporal follow-up should use context.", {"day": ["tomorrow"]}, "ctx_student"),
        ("marks?", "student_grades_query", "SQL", "Incomplete marks follow-up should use selected student.", {}, "ctx_student"),
        ("who teaches AI301 and what is it about", "course_instructor_query", "SQL+RAG", "Use SQL for instructor and RAG/course docs for explanation.", {"course_code": ["AI301"]}),
        ("what is my GPA and explain academic warning policy", "student_gpa_query", "SQL+RAG", "Use SQL for GPA and RAG for policy.", {"metric": ["GPA"]}, "ctx_student"),
        ("show my schedule and explain where the lab is", "student_schedule_query", "SQL+RAG", "Use SQL schedule plus RAG/location knowledge if available.", {}, "ctx_student"),
        ("who teaches database and explain the course", "course_instructor_query", "SQL+RAG", "Use SQL instructor plus RAG course explanation.", {"course_name": ["database"]}),
        ("tell me about fees", "ask_knowledge", "RAG", "Use RAG, not SQL.", {}),
        ("does the college have a library", "ask_knowledge", "RAG", "Use RAG knowledge base.", {}),
    ]
)


assert len(TEST_CASES) == 200, f"Expected 200 stress cases, found {len(TEST_CASES)}"


def export_json(path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(TEST_CASES, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    export_json(Path(__file__).with_suffix(".json"))
    print(f"Exported {len(TEST_CASES)} cases")
