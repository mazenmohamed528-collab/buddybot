import sys
from pathlib import Path
from typing import Optional
import re


SQL_ENGINE_PATH = Path(r"C:\dev\sql_engine_service")
if str(SQL_ENGINE_PATH) not in sys.path:
    sys.path.insert(0, str(SQL_ENGINE_PATH))

from sql_engine.models import ContextPayload, QueryRequest  # noqa: E402
from sql_engine.service import SqlEngineService  # noqa: E402


class FakeRepository:
    def execute(self, query):
        sql = query.sql
        lowered = sql.lower()
        params = [str(param) for param in query.params]
        if "as matchrank" in lowered:
            return [
                self._candidate("2122209", "Mazen Mohamed Abd Elmageed Badawi", "DS", "ISDS"),
                self._candidate("2122322", "Mazen Hany Mohamed Nagah Mohamed", "CS1", "CS"),
                self._candidate("2122323", "Mazen Wael Fawzy Mohamed", "AI 1", "AI"),
            ]
        if "with courseprogress" in lowered:
            return [
                {
                    "StudentID": "2122209",
                    "FullName": "Mazen Mohamed Abd Elmageed Badawi",
                    "GroupCode": "DS",
                    "DepartmentCode": "ISDS",
                    "DepartmentName": "Information Systems and Data Science",
                    "StoredCurrentYear": 3,
                    "StoredCurrentSemester": 1,
                    "AcademicYear": 2025,
                    "Semester": 1,
                    "SemesterGPA": 3.41,
                    "SemesterCumulativeGPA": 3.41,
                    "CreditsEarned": 18,
                    "CreditsAttempted": 18,
                    "CompletedSemesters": 2,
                    "HasSemester1": 1,
                    "HasSemester2": 1,
                    "GpaCreditsEarned": 36,
                    "GpaCreditsAttempted": 36,
                    "FailedCourseRecords": 0,
                    "OpenCourseRecords": 0,
                    "PassedCreditHours": 36,
                },
                {
                    "StudentID": "2122209",
                    "FullName": "Mazen Mohamed Abd Elmageed Badawi",
                    "GroupCode": "DS",
                    "DepartmentCode": "ISDS",
                    "DepartmentName": "Information Systems and Data Science",
                    "StoredCurrentYear": 3,
                    "StoredCurrentSemester": 1,
                    "AcademicYear": 2025,
                    "Semester": 2,
                    "SemesterGPA": 3.55,
                    "SemesterCumulativeGPA": 3.48,
                    "CreditsEarned": 18,
                    "CreditsAttempted": 18,
                    "CompletedSemesters": 2,
                    "HasSemester1": 1,
                    "HasSemester2": 1,
                    "GpaCreditsEarned": 36,
                    "GpaCreditsAttempted": 36,
                    "FailedCourseRecords": 0,
                    "OpenCourseRecords": 0,
                    "PassedCreditHours": 36,
                },
            ]
        if "from courses c" in lowered:
            return [
                {
                    "CourseCode": "ISDS403",
                    "CourseName": "Categorical Data Analysis",
                    "CreditHours": 3,
                    "TotalMarks": 100,
                    "CourseYear": 4,
                    "CourseSemester": 1,
                    "Category": "major",
                    "DepartmentCode": "ISDS",
                    "DepartmentName": "Information Systems and Data Science",
                }
            ]
        if "select distinct top" in lowered and "from v_rasa_schedule sch" in lowered:
            return [
                {
                    "CourseCode": "ISDS403",
                    "CourseName": "Categorical Data Analysis",
                    "InstructorTitle": "Dr.",
                    "InstructorName": "Mostafa Yakoub",
                    "TargetGroup": "ISDS",
                }
            ]
        if "from v_rasa_schedule sch" in lowered:
            return [
                {
                    "DayOfWeek": "Saturday",
                    "StartTime": "14:00",
                    "EndTime": "15:30",
                    "TargetGroup": "ISDS",
                    "CourseCode": "ISDS403",
                    "CourseName": "Categorical Data Analysis",
                    "InstructorName": "Mostafa Yakoub",
                    "RoomName": "Lab 4",
                    "RoomType": "lab",
                    "SectionType": "lecture",
                }
            ]
        if "from v_rasa_students s" in lowered and "join students st" in lowered:
            if any(param.endswith("209") for param in params):
                return [
                    {
                        "StudentID": "2122209",
                        "FullName": "Mazen Mohamed Abd Elmageed Badawi",
                        "Email": "Mazen.Badawy.22209@sadatacademy.edu.eg",
                        "CurrentYear": 3,
                        "CurrentSemester": 1,
                        "GroupCode": "DS",
                        "DepartmentCode": "ISDS",
                        "DepartmentName": "Information Systems and Data Science",
                        "Status": "active",
                    }
                ]
            top = self._top(sql)
            return [
                {
                    "StudentID": str(2122000 + index),
                    "FullName": f"Student {index:02d}",
                    "Email": f"student{index}@sadatacademy.edu.eg",
                    "CurrentYear": 3,
                    "CurrentSemester": 2 if "current_semester" in lowered else 1,
                    "GroupCode": "AI 1",
                    "DepartmentCode": "AI",
                    "DepartmentName": "Artificial Intelligence",
                    "Status": "active",
                }
                for index in range(1, top + 1)
            ]
        return []

    @staticmethod
    def _candidate(student_id, full_name, group_code, department_code):
        return {
            "student_id": student_id,
            "full_name": full_name,
            "email": f"{student_id}@sadatacademy.edu.eg",
            "group_code": group_code,
            "department_code": department_code,
            "department_name": department_code,
        }

    @staticmethod
    def _top(sql: str) -> int:
        match = re.search(r"top\s*\((\d+)\)", sql, re.I)
        return int(match.group(1)) if match else 20


def ask(service: SqlEngineService, question: str, context: Optional[ContextPayload] = None):
    return service.answer(QueryRequest(question=question, context=context or ContextPayload(), debug=True))


def context_from_updates(updates: dict) -> ContextPayload:
    return ContextPayload(
        student_id=updates.get("student_id"),
        student_name=updates.get("student_name"),
        course_code=updates.get("course_code"),
        course_name=updates.get("course_name"),
        department_code=updates.get("department_code"),
        group_code=updates.get("group_code"),
        semester=updates.get("semester"),
        day=updates.get("day"),
        time=updates.get("time"),
        last_domain=updates.get("last_domain"),
        pending_candidates=updates.get("pending_candidates") or [],
        pending_question=updates.get("pending_question"),
        last_result_rows=updates.get("last_result_rows") or [],
        last_result_plan=updates.get("last_result_plan"),
        last_result_offset=updates.get("last_result_offset") or 0,
        last_result_page_size=updates.get("last_result_page_size") or 10,
    )


def main() -> None:
    service = SqlEngineService(repository=FakeRepository())

    result = ask(service, "give me 50 students")
    assert result.domain == "student", result
    assert result.row_count == 50, result.answer
    assert "first 10" not in result.answer.lower(), result.answer

    cached = ask(service, "give me all students in data science")
    assert cached.domain == "student", cached.answer
    assert cached.row_count == 50, cached.answer
    assert "first 10" in cached.answer.lower(), cached.answer
    continued = ask(service, "all of them", context_from_updates(cached.context_updates))
    assert continued.domain == "student", continued.answer
    assert "showing results 11-50 of 50" in continued.answer.lower(), continued.answer

    first = ask(service, "do you have a student called Mazen")
    assert first.needs_clarification, first.answer
    pending = ContextPayload(
        pending_candidates=first.candidates,
        pending_question=first.pending_question,
    )
    second = ask(service, "do u have a student with a code of 209", pending)
    assert not second.needs_clarification, second.answer
    assert "pending_students" not in str(second.context_updates).lower()
    assert "2122209" in second.answer, second.answer
    assert "could not match that choice" not in second.answer.lower(), second.answer

    partial = ask(service, "code 209")
    assert partial.domain == "student", partial
    assert "2122209" in partial.answer, partial.answer

    semester_students = ask(service, "who's in semester 2?")
    assert semester_students.domain == "student", semester_students
    assert "current_semester" in (semester_students.sql or "").lower(), semester_students.sql

    saturday_ds = ask(service, "what lectures on saturday for data science")
    assert saturday_ds.domain == "schedule", saturday_ds.answer
    assert saturday_ds.context_updates.get("department_code") == "ISDS", saturday_ds.context_updates
    assert saturday_ds.context_updates.get("day") == "Saturday", saturday_ds.context_updates
    semester_followup = ask(service, "for second semester", context_from_updates(saturday_ds.context_updates))
    assert semester_followup.domain == "schedule", semester_followup
    assert "sch.semester = ?" in (semester_followup.sql or ""), semester_followup.sql
    assert "could not find" not in semester_followup.answer.lower(), semester_followup.answer

    strict_schedule = ask(service, "4th year second semester data science saturday schedule")
    assert strict_schedule.domain == "schedule", strict_schedule.answer
    sql_lower = (strict_schedule.sql or "").lower()
    assert "sch.course_year = ?" in sql_lower, strict_schedule.sql
    assert "sch.semester = ?" in sql_lower, strict_schedule.sql
    assert "sch.day_of_week = ?" in sql_lower, strict_schedule.sql
    assert "sch.target_group in" in sql_lower, strict_schedule.sql

    course = ask(service, "what about categorical data analysis")
    assert course.domain == "course", course.answer
    assert "Categorical Data Analysis" in course.answer, course.answer
    assert course.context_updates.get("course_code") == "ISDS403", course.context_updates
    instructor = ask(service, "who teaches it?", context_from_updates(course.context_updates))
    assert instructor.domain == "instructor", instructor
    assert "Categorical Data Analysis" in instructor.answer, instructor.answer
    assert "Mostafa Yakoub" in instructor.answer, instructor.answer

    progress = ask(
        service,
        "is he now in fourth year?",
        ContextPayload(student_id="2122209", student_name="Mazen Mohamed Abd Elmageed Badawi"),
    )
    assert progress.domain == "academic_progress", progress.answer
    assert "stored profile" in progress.answer.lower(), progress.answer
    assert (
        "official promotion status" in progress.answer.lower()
        or "cannot confirm" in progress.answer.lower()
    ), progress.answer

    print("SQL engine regression tests passed.")


if __name__ == "__main__":
    main()
