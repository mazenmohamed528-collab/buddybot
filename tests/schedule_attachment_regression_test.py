import sys
from pathlib import Path
from typing import Optional


SQL_ENGINE_PATH = Path(r"C:\dev\sql_engine_service")
if str(SQL_ENGINE_PATH) not in sys.path:
    sys.path.insert(0, str(SQL_ENGINE_PATH))

from sql_engine.models import ContextPayload, QueryRequest  # noqa: E402
from sql_engine.service import SqlEngineService  # noqa: E402


class FakeScheduleRepository:
    def execute(self, query):
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


def ask(service: SqlEngineService, question: str, context: Optional[ContextPayload] = None):
    return service.answer(QueryRequest(question=question, context=context or ContextPayload(), debug=True))


def assert_attachment(result, expected_id_part: str):
    assert result.attachments, result.answer
    ids = [attachment.attachment_id for attachment in result.attachments]
    assert any(expected_id_part in attachment_id for attachment_id in ids), ids
    assert "Files:" in result.answer, result.answer


def main() -> None:
    service = SqlEngineService(repository=FakeScheduleRepository())

    second = ask(service, "give me second semester schedule")
    assert second.domain == "schedule", second
    assert_attachment(second, "sem2-full")

    fourth_ds = ask(service, "schedule for fourth year data science")
    assert fourth_ds.domain == "schedule", fourth_ds
    assert_attachment(fourth_ds, "year4-isds")
    assert any(attachment.page_number == 14 for attachment in fourth_ds.attachments), fourth_ds.attachments

    pdf = ask(service, "send me schedule PDF")
    assert pdf.domain == "schedule", pdf
    assert any("full" in attachment.attachment_id for attachment in pdf.attachments), pdf.attachments

    ai_second = ask(service, "schedule for AI second semester")
    assert ai_second.domain == "schedule", ai_second
    assert_attachment(ai_second, "year3-ai")

    followup_file = ask(
        service,
        "show it as a file",
        ContextPayload(
            last_domain="schedule",
            semester=2,
            year_level=3,
            department_code="AI",
            group_code="AI",
        ),
    )
    assert followup_file.domain == "schedule", followup_file
    assert_attachment(followup_file, "year3-ai")

    print("Schedule attachment regression tests passed.")


if __name__ == "__main__":
    main()
