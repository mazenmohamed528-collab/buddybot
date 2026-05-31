from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List

import requests


PROJECT_ROOT = Path(r"C:\dev\rasa_project")
SQL_ENGINE_ROOT = Path(r"C:\dev\sql_engine_service")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SQL_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(SQL_ENGINE_ROOT))

from actions.actions import hybrid_route, looks_like_database_request, looks_like_official_knowledge_request  # noqa: E402


@dataclass
class EvalCase:
    message: str
    expected_route: str
    category: str


CASES = [
    EvalCase("give me all students in data science", "SQL", "pagination"),
    EvalCase("all of them", "SQL", "followup"),
    EvalCase("4th year second semester data science saturday schedule", "SQL", "schedule_filter"),
    EvalCase("مين عميد الكلية؟", "RAG", "arabic_official"),
    EvalCase("ايه نظام الانذار الاكاديمي؟", "RAG", "arabic_policy"),
    EvalCase("show me official rules for attendance", "RAG", "official_policy"),
    EvalCase("What is the academic warning system?", "RAG", "student_guide"),
    EvalCase("what's data science", "RAG", "educational"),
    EvalCase("tell ne about software engineering", "RAG", "educational"),
    EvalCase("give me the majors", "RAG", "departments"),
    EvalCase("الغياب", "RAG", "arabic_policy"),
    EvalCase("all the students in data science", "SQL", "pagination"),
]


def predicted_route(message: str) -> str:
    route = hybrid_route(message).get("route")
    if route in {"policy_rag", "educational_rag", "file_retrieval"}:
        return "RAG"
    if route in {"structured_sql", "clarification"}:
        return "SQL"
    if looks_like_official_knowledge_request(message):
        return "RAG"
    if looks_like_database_request(message) or message.lower() in {"all of them", "next", "show more"}:
        return "SQL"
    return "fallback"


def maybe_call_rag(message: str, url: str = "http://127.0.0.1:8000/query") -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        response = requests.post(url, json={"question": message, "n_results": 4}, timeout=4)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        if response.ok:
            payload = response.json()
            return {
                "available": True,
                "latency_ms": elapsed_ms,
                "source_count": len(payload.get("sources") or []),
                "answer_preview": (payload.get("answer") or "")[:160],
            }
        return {"available": False, "latency_ms": elapsed_ms, "error": response.text[:160]}
    except Exception as exc:
        return {"available": False, "latency_ms": round((time.perf_counter() - start) * 1000, 2), "error": str(exc)}


def main() -> None:
    results: List[Dict[str, Any]] = []
    for case in CASES:
        route = predicted_route(case.message)
        record = {
            **asdict(case),
            "predicted_route": route,
            "route_passed": route == case.expected_route,
        }
        if route == "RAG":
            record["rag"] = maybe_call_rag(case.message)
        results.append(record)

    passed = sum(1 for item in results if item["route_passed"])
    report = {
        "total": len(results),
        "route_passed": passed,
        "route_accuracy": round(passed / len(results), 3),
        "results": results,
    }
    output_path = PROJECT_ROOT / "tests" / "assistant_optimization_eval_report.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
