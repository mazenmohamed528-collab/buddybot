"""Stress-test runner for BuddyBot Rasa NLU and SQL engine routing.

Examples:
    python tests/stress_test_runner.py --mode nlu
    python tests/stress_test_runner.py --mode all --sql-engine-url http://127.0.0.1:8010/query
    python tests/stress_test_runner.py --export-cases tests/stress_test_cases.json
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging
import os
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

try:
    from stress_test_cases import TEST_CASES, export_json
except ImportError:
    from tests.stress_test_cases import TEST_CASES, export_json

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
logging.getLogger("rasa").setLevel(logging.WARNING)
logging.getLogger("tensorflow").setLevel(logging.WARNING)
logging.getLogger("matplotlib").setLevel(logging.WARNING)


SQL_INTENTS = {
    "ask_database_question",
    "student_profile_query",
    "student_gpa_query",
    "student_grades_query",
    "student_failed_courses_query",
    "student_schedule_query",
    "course_info_query",
    "course_instructor_query",
    "department_query",
    "room_query",
    "free_room_query",
    "instructor_query",
    "analytics_query",
    "followup_query",
    "reset_courses_query",
    "academic_progress_query",
}

RAG_INTENTS = {"ask_knowledge"}
CLARIFICATION_INTENTS = {"clarification_response"}

SEEDED_CONTEXTS: Dict[str, Dict[str, Any]] = {
    "ctx_student": {
        "student_id": "2122209",
        "student_name": "Mazen Mohamed Abd Elmageed Badawi",
        "department_code": "ISDS",
        "group_code": "DS",
        "last_domain": "student",
    },
    "ctx_group": {
        "department_code": "AI",
        "group_code": "AI 1",
        "last_domain": "schedule",
    },
    "ctx_analytics": {
        "last_domain": "analytics",
    },
}

ALIASES = [
    {"ai", "artificialintelligence", "a.i."},
    {"cscs", "cybersecurity", "cybersecurity"},
    {"isds", "ds", "datascience", "informationsystems", "informationsystemsanddatascience"},
    {"se", "softwareengineering"},
    {"gpa", "cgpa", "cumulativegpa"},
]


def normalize_value(value: Any) -> str:
    text = str(value or "").lower().strip()
    return "".join(ch for ch in text if ch.isalnum())


def values_match(expected: Any, actual: Any) -> bool:
    expected_norm = normalize_value(expected)
    actual_norm = normalize_value(actual)
    if expected_norm == actual_norm:
        return True
    for alias_set in ALIASES:
        if expected_norm in alias_set and actual_norm in alias_set:
            return True
    return expected_norm in actual_norm or actual_norm in expected_norm


def latest_model(models_dir: Path) -> Path:
    models = sorted(models_dir.glob("*.tar.gz"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not models:
        raise FileNotFoundError(f"No Rasa model archives found in {models_dir}")
    return models[0]


def load_rasa_agent(model_path: Path):
    from rasa.core.agent import Agent

    return Agent.load(str(model_path))


def parse_with_rasa(agent: Any, message: str) -> Dict[str, Any]:
    parsed = agent.parse_message(message)
    if inspect.isawaitable(parsed):
        return asyncio.run(parsed)
    return parsed


def route_from_intent(intent_name: str) -> str:
    if intent_name in SQL_INTENTS:
        return "SQL"
    if intent_name in RAG_INTENTS:
        return "RAG"
    if intent_name in CLARIFICATION_INTENTS:
        return "clarification"
    return "conversation"


def route_from_sql_engine(response: Dict[str, Any]) -> str:
    if response.get("needs_clarification"):
        return "clarification"
    if response.get("handled") and response.get("domain") not in {None, "unknown"}:
        return "SQL"
    return "unknown"


def expected_entities_match(
    expected_entities: Dict[str, List[str]], actual_entities: List[Dict[str, Any]]
) -> Tuple[bool, List[str]]:
    missing: List[str] = []
    if not expected_entities:
        return True, missing

    by_entity: Dict[str, List[Any]] = defaultdict(list)
    for entity in actual_entities:
        by_entity[entity.get("entity", "")].append(entity.get("value"))

    for entity_name, expected_values in expected_entities.items():
        actual_values = by_entity.get(entity_name, [])
        if not actual_values:
            missing.append(f"{entity_name}={expected_values}")
            continue
        matched = any(
            values_match(expected_value, actual_value)
            for expected_value in expected_values
            for actual_value in actual_values
        )
        if not matched:
            missing.append(f"{entity_name}={expected_values} actual={actual_values}")
    return not missing, missing


def confidence_info(parsed: Optional[Dict[str, Any]]) -> Tuple[float, float]:
    if not parsed:
        return math.nan, math.nan
    ranking = parsed.get("intent_ranking") or []
    top = float((parsed.get("intent") or {}).get("confidence") or 0.0)
    second = float(ranking[1].get("confidence") or 0.0) if len(ranking) > 1 else 0.0
    return top, top - second


def call_sql_engine(
    url: str,
    case: Dict[str, Any],
    context_by_session: Dict[str, Dict[str, Any]],
    timeout: int = 30,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    route = case["expected_route"]
    if route == "RAG":
        return None, None

    session_id = case.get("session_id")
    context = context_by_session.get(session_id or "", {}).copy()
    payload = {
        "question": case["user_message"],
        "context": context,
        "debug": False,
    }
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"

    if session_id:
        updates = data.get("context_updates") or {}
        next_context = context.copy()
        for key, value in updates.items():
            if value in (None, [], {}):
                next_context.pop(key, None)
            else:
                next_context[key] = value
        context_by_session[session_id] = next_context
    return data, None


def evaluate_case(
    case: Dict[str, Any],
    agent: Optional[Any],
    sql_engine_url: Optional[str],
    context_by_session: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    result = dict(case)
    parsed: Optional[Dict[str, Any]] = None
    if agent is not None:
        parsed = parse_with_rasa(agent, case["user_message"])

    predicted_intent = (parsed or {}).get("intent", {}).get("name")
    actual_entities = (parsed or {}).get("entities", [])
    intent_pass = predicted_intent == case["expected_intent"] if parsed else None
    entity_pass, missing_entities = expected_entities_match(case["expected_entities"], actual_entities) if parsed else (None, [])

    predicted_route = route_from_intent(predicted_intent or "") if parsed else None
    sql_response = None
    sql_error = None
    if sql_engine_url:
        sql_response, sql_error = call_sql_engine(sql_engine_url, case, context_by_session)
        if sql_response:
            predicted_route = route_from_sql_engine(sql_response)

    route_pass = predicted_route == case["expected_route"] if predicted_route is not None else None
    if sql_engine_url is None and case["expected_route"] == "clarification" and predicted_route == "SQL":
        # In NLU-only mode an ambiguous database request should still route to
        # the SQL action; the SQL engine detects the ambiguity later.
        route_pass = True
    if case["expected_route"] == "SQL+RAG" and predicted_route in {"SQL", "RAG"}:
        route_pass = False

    contains_pass: Optional[bool] = True
    response_text = (sql_response or {}).get("answer", "")
    if case.get("expected_response_contains") and not sql_response:
        contains_pass = None
    else:
        for expected_text in case.get("expected_response_contains") or []:
            if expected_text.lower() not in response_text.lower():
                contains_pass = False
                break

    applicable = [value for value in [intent_pass, entity_pass, route_pass, contains_pass] if value is not None]
    pass_fail = "PASS" if applicable and all(applicable) and not sql_error else "FAIL"

    confidence, margin = confidence_info(parsed)
    confusing = bool(parsed and (confidence < 0.65 or margin < 0.15))

    result.update(
        {
            "predicted_intent": predicted_intent,
            "intent_confidence": confidence,
            "intent_margin": margin,
            "actual_entities": actual_entities,
            "predicted_route": predicted_route,
            "intent_pass": intent_pass,
            "entity_pass": entity_pass,
            "route_pass": route_pass,
            "behavior_pass": contains_pass,
            "missing_entities": missing_entities,
            "sql_engine_error": sql_error,
            "sql_engine_domain": (sql_response or {}).get("domain"),
            "sql_engine_row_count": (sql_response or {}).get("row_count"),
            "sql_engine_answer": response_text,
            "confusing": confusing,
            "pass_fail": pass_fail,
        }
    )
    return result


def percent(passed: int, total: int) -> float:
    return round((passed / total) * 100, 2) if total else 0.0


def make_suggestions(results: List[Dict[str, Any]]) -> List[str]:
    suggestions: List[str] = []
    intent_misses = [row for row in results if row.get("intent_pass") is False]
    entity_misses = [row for row in results if row.get("entity_pass") is False]
    route_misses = [row for row in results if row.get("route_pass") is False]
    sql_errors = [row for row in results if row.get("sql_engine_error")]
    mixed_misses = [row for row in results if row.get("expected_route") == "SQL+RAG" and row.get("route_pass") is False]

    if intent_misses:
        common = Counter((row["expected_intent"], row.get("predicted_intent")) for row in intent_misses).most_common(5)
        suggestions.append(f"Add/adjust NLU examples for intent confusions: {common}")
    if entity_misses:
        common_entities = Counter(
            missing.split("=")[0]
            for row in entity_misses
            for missing in row.get("missing_entities", [])
        ).most_common(8)
        suggestions.append(f"Improve entity annotations/lookups/regexes for: {common_entities}")
    if route_misses:
        common_routes = Counter((row["expected_route"], row.get("predicted_route")) for row in route_misses).most_common(5)
        suggestions.append(f"Improve router/rules for route mismatches: {common_routes}")
    if sql_errors:
        suggestions.append(f"Fix SQL engine validation/compiler errors. Error count: {len(sql_errors)}")
    if mixed_misses:
        suggestions.append("Implement a SQL+RAG hybrid route for mixed factual + explanatory questions.")
    if not suggestions:
        suggestions.append("No high-level fixes suggested. Review low-confidence cases for dataset hardening.")
    return suggestions


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    intent_total = sum(row.get("intent_pass") is not None for row in results)
    entity_total = sum(row.get("entity_pass") is not None for row in results)
    route_total = sum(row.get("route_pass") is not None for row in results)
    behavior_total = sum(row.get("behavior_pass") is not None for row in results)
    passed_total = sum(row["pass_fail"] == "PASS" for row in results)

    return {
        "total_cases": total,
        "passed_cases": passed_total,
        "overall_pass_rate": percent(passed_total, total),
        "intent_accuracy": percent(sum(row.get("intent_pass") is True for row in results), intent_total),
        "entity_accuracy": percent(sum(row.get("entity_pass") is True for row in results), entity_total),
        "routing_accuracy": percent(sum(row.get("route_pass") is True for row in results), route_total),
        "behavior_check_accuracy": percent(sum(row.get("behavior_pass") is True for row in results), behavior_total),
        "failed_cases": [row for row in results if row["pass_fail"] == "FAIL"],
        "confusing_cases": [row for row in results if row.get("confusing")],
        "suggested_fixes": make_suggestions(results),
    }


def print_summary(summary: Dict[str, Any], report_path: Path) -> None:
    print("\nBuddyBot Stress Test Summary")
    print("=" * 34)
    print(f"Total cases:        {summary['total_cases']}")
    print(f"Passed cases:       {summary['passed_cases']}")
    print(f"Overall pass rate:  {summary['overall_pass_rate']}%")
    print(f"Intent accuracy:    {summary['intent_accuracy']}%")
    print(f"Entity accuracy:    {summary['entity_accuracy']}%")
    print(f"Routing accuracy:   {summary['routing_accuracy']}%")
    print(f"Behavior accuracy:  {summary['behavior_check_accuracy']}%")
    print(f"Failed cases:       {len(summary['failed_cases'])}")
    print(f"Confusing cases:    {len(summary['confusing_cases'])}")
    print(f"Report:             {report_path}")
    print("\nSuggested fixes:")
    for suggestion in summary["suggested_fixes"]:
        print(f"- {suggestion}")

    if summary["failed_cases"]:
        print("\nFirst 10 failed cases:")
        for row in summary["failed_cases"][:10]:
            print(
                f"- {row['id']} | {row['user_message']} | "
                f"intent {row.get('predicted_intent')} expected {row['expected_intent']} | "
                f"route {row.get('predicted_route')} expected {row['expected_route']}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run BuddyBot stress tests.")
    parser.add_argument("--mode", choices=["nlu", "sql-engine", "all"], default="all")
    parser.add_argument("--model", default=None, help="Path to Rasa model .tar.gz. Defaults to newest model.")
    parser.add_argument("--models-dir", default="models", help="Directory containing Rasa model archives.")
    parser.add_argument("--sql-engine-url", default="http://127.0.0.1:8010/query")
    parser.add_argument("--output", default="tests/stress_test_report.json")
    parser.add_argument("--export-cases", default=None, help="Export the dataset to JSON and exit.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N cases.")
    parser.add_argument("--filter", default=None, help="Run cases whose id/message/intent contains this text.")
    parser.add_argument("--fail-exit", action="store_true", help="Exit with code 1 if any case fails.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.export_cases:
        export_json(args.export_cases)
        print(f"Exported {len(TEST_CASES)} cases to {args.export_cases}")
        return 0

    project_root = Path.cwd()
    cases = list(TEST_CASES)
    if args.filter:
        needle = args.filter.lower()
        cases = [
            case
            for case in cases
            if needle in case["id"].lower()
            or needle in case["user_message"].lower()
            or needle in case["expected_intent"].lower()
        ]
    if args.limit:
        cases = cases[: args.limit]

    agent = None
    if args.mode in {"nlu", "all"}:
        model_path = Path(args.model) if args.model else latest_model(project_root / args.models_dir)
        print(f"Loading Rasa model: {model_path}")
        agent = load_rasa_agent(model_path)

    sql_engine_url = args.sql_engine_url if args.mode in {"sql-engine", "all"} else None
    context_by_session = {key: value.copy() for key, value in SEEDED_CONTEXTS.items()}

    started = time.time()
    results = [
        evaluate_case(case, agent=agent, sql_engine_url=sql_engine_url, context_by_session=context_by_session)
        for case in cases
    ]
    elapsed = round(time.time() - started, 2)

    summary = summarize(results)
    report = {
        "mode": args.mode,
        "elapsed_seconds": elapsed,
        "summary": {key: value for key, value in summary.items() if key not in {"failed_cases", "confusing_cases"}},
        "failed_cases": summary["failed_cases"],
        "confusing_cases": summary["confusing_cases"],
        "results": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print_summary(summary, output_path)
    return 1 if args.fail_exit and summary["failed_cases"] else 0


if __name__ == "__main__":
    sys.exit(main())
