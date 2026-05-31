import sys
from pathlib import Path


PROJECT_ROOT = Path(r"C:\dev\rasa_project")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from actions.actions import (  # noqa: E402
    answer_from_rows,
    cached_continuation_result,
    fci_list_students_sql,
    hybrid_route,
    is_greeting,
    is_status_check,
    looks_like_database_request,
    looks_like_educational_rag_request,
    looks_like_official_knowledge_request,
    looks_like_policy_rag_request,
    looks_like_result_continuation,
    looks_like_schedule_file_request,
    continuation_replay_question,
    stale_sql_engine_result,
    student_initial_page_size,
    student_list_limit,
    wants_all_continuation,
)


def main() -> None:
    assert is_greeting("اهلا")
    assert is_greeting("السلام عليكم")
    assert is_status_check("hru")
    assert looks_like_official_knowledge_request("مين عميد الكلية؟")
    assert not looks_like_database_request("مين عميد الكلية؟")
    assert looks_like_official_knowledge_request("show me official rules for attendance")
    assert not looks_like_database_request("show me official rules for attendance")
    assert looks_like_result_continuation("all of them")
    assert looks_like_result_continuation("all of them?")
    assert looks_like_result_continuation("and the rest?")
    assert looks_like_result_continuation("al of them")
    assert wants_all_continuation("i want all")
    assert wants_all_continuation("al of them")
    assert not looks_like_result_continuation("show me all students in data science?")
    assert looks_like_database_request("give me all students in data science")
    assert looks_like_database_request("show me all students in data sciencs")
    assert looks_like_database_request("all the students in data science")
    assert looks_like_database_request("4th year second semester data science saturday schedule")
    assert looks_like_educational_rag_request("what's data science")
    assert looks_like_educational_rag_request("tell ne about software engineering")
    assert not looks_like_database_request("what's data science")
    assert not looks_like_database_request("tell me about software engineering")
    assert hybrid_route("what's data science")["route"] == "educational_rag"
    assert hybrid_route("tell ne about software engineering")["route"] == "educational_rag"
    assert hybrid_route("what courses should i take if i'm in data science")["route"] == "educational_rag"
    assert hybrid_route("give me the majors")["route"] == "educational_rag"
    assert looks_like_policy_rag_request("الغياب")
    assert not looks_like_database_request("الغياب")
    assert hybrid_route("الغياب")["route"] == "policy_rag"
    assert hybrid_route("exam schedule please")["route"] == "policy_rag"
    assert hybrid_route("جدول الامتحانات امتي؟")["route"] == "policy_rag"
    assert hybrid_route("ايه قسم علوم الحاسب")["route"] == "educational_rag"
    assert hybrid_route("هات طلبة الداتا ساينس")["route"] == "structured_sql"
    assert hybrid_route("علوم الحاسب")["route"] == "educational_rag"
    assert hybrid_route("قسم هندسة البرمجيات")["route"] == "educational_rag"
    assert hybrid_route("كم طالب DS")["route"] == "structured_sql"
    assert hybrid_route("who's dr Ahmed Esmat?")["route"] == "structured_sql"
    assert hybrid_route("student 22209")["route"] == "structured_sql"
    assert hybrid_route("who teaches data science?")["route"] == "structured_sql"
    assert hybrid_route("who teaches human rights?")["route"] == "structured_sql"
    assert hybrid_route("تغيير التخصص")["route"] == "policy_rag"
    assert hybrid_route("تغيير المسار")["route"] == "policy_rag"
    assert hybrid_route("التخصص")["route"] == "policy_rag"
    assert hybrid_route("الاقسام")["route"] == "educational_rag"
    assert hybrid_route("what is my attendance?")["route"] == "structured_sql"
    assert hybrid_route("نسبة حضوري كام؟")["route"] == "structured_sql"
    assert looks_like_schedule_file_request("ابعتلي ملف الجدول")
    assert hybrid_route("ابعتلي ملف الجدول")["route"] == "structured_sql"
    assert student_list_limit("show me all students in data science?") == 500
    assert student_list_limit("show me students in data science") == 500
    assert student_list_limit("show me all students in data sciencs") == 500
    assert student_initial_page_size("show me all students in data science?") == 10
    assert "SELECT TOP 500" in fci_list_students_sql("show me all students in data science?")
    stale_result = {
        "handled": True,
        "domain": "student",
        "operation": "list",
        "answer": "I found 20 matching students. Here are the first 10:\n- Example",
    }
    assert stale_sql_engine_result("show me all students in data science?", stale_result)
    old_answer = answer_from_rows(["StudentID", "FullName"], [(1, "A"), (2, "B"), (3, "C")], "show me students", row_limit=2)
    assert "show more" in old_answer

    class DummyTracker:
        def __init__(self, slots, events=None, latest_message=None):
            self.slots = slots
            self.events = events or []
            self.latest_message = latest_message or {}

        def get_slot(self, name):
            return self.slots.get(name)

    assert continuation_replay_question(DummyTracker({"department_code": "ISDS"})) == "give me 50 students in data science"

    replay_tracker = DummyTracker(
        {},
        events=[
            {"event": "user", "text": "show me all students in data science?"},
            {"event": "user", "text": "all of them"},
        ],
    )
    assert continuation_replay_question(replay_tracker) == "give me 50 students in data science"

    cached_rows = [
        {
            "StudentID": f"21220{i}",
            "FullName": f"Student {i}",
            "GroupCode": "DS",
            "DepartmentName": "Information Systems & Data Science",
        }
        for i in range(1, 6)
    ]
    cached_tracker = DummyTracker(
        {
            "sql_result_cache": cached_rows,
            "sql_result_plan": {"domain": "student", "operation": "list", "page_size": 2},
            "sql_result_offset": 2,
            "sql_result_page_size": 2,
        }
    )
    cached_result = cached_continuation_result("all of them", cached_tracker)
    assert cached_result and cached_result["handled"]
    assert "Showing results 3-5 of 5" in cached_result["answer"]
    assert cached_result["context_updates"]["last_result_offset"] == 5
    print("Routing regression tests passed.")


if __name__ == "__main__":
    main()
