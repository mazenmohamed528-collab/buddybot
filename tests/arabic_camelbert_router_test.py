import sys
from pathlib import Path


PROJECT_ROOT = Path(r"C:\dev\rasa_project")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from actions.arabic_camelbert_router import (  # noqa: E402
    CamelBertArabicRouter,
    contains_arabic_or_arabizi,
    normalize_arabic_text,
    predict_arabic_route,
)
from actions.actions import camelbert_route_hint, hybrid_route, is_greeting  # noqa: E402


def main() -> None:
    assert normalize_arabic_text("إختبار  الســــيارات") == "اختبار السيارات"
    assert contains_arabic_or_arabizi("الغياب")
    assert contains_arabic_or_arabizi("meen 3ameed el koleya")

    assert CamelBertArabicRouter._label_to_route("attendance_policy") == "policy_rag"
    assert CamelBertArabicRouter._label_to_route("academic_warning") == "policy_rag"
    assert CamelBertArabicRouter._label_to_route("registration") == "policy_rag"
    assert CamelBertArabicRouter._label_to_route("fees_query") == "policy_rag"
    assert CamelBertArabicRouter._label_to_route("gpa_query") == "structured_sql"
    assert CamelBertArabicRouter._label_to_route("schedule_query") == "structured_sql"
    assert CamelBertArabicRouter._label_to_route("student_lookup") == "structured_sql"
    assert CamelBertArabicRouter._label_to_route("educational") == "educational_rag"
    assert CamelBertArabicRouter._label_to_route("file_request") == "file_retrieval"
    assert CamelBertArabicRouter._label_to_route("fraud") is None
    assert CamelBertArabicRouter._label_to_route("legitimate") is None

    # No model is required for CI/local smoke tests. Missing dependencies/model
    # should never break the Rasa action server.
    assert predict_arabic_route("الغياب") is None or isinstance(predict_arabic_route("الغياب"), dict)
    assert camelbert_route_hint("الغياب") is None or isinstance(camelbert_route_hint("الغياب"), dict)

    assert is_greeting("ازيك")
    assert hybrid_route("الغياب")["route"] == "policy_rag"
    assert hybrid_route("ايه قسم علوم الحاسب")["route"] == "educational_rag"
    assert hybrid_route("هات طلبة الداتا ساينس")["route"] == "structured_sql"
    assert hybrid_route("جدول الامتحانات امتى؟")["route"] == "policy_rag"
    assert hybrid_route("ابعتلي ملف الجدول")["route"] == "structured_sql"
    print("Arabic CAMeLBERT router tests passed.")


if __name__ == "__main__":
    main()
