"""HTTP acceptance test runner for BuddyBot.

This script sends real messages to a running Rasa 3.6.x server, compares the
bot response with expected keywords/actions/intents, prints PASS/FAIL, and
writes failed cases to a JSON report.

Start services first, for example:

    cd C:\\dev\\rasa_project
    .\\.venv\\Scripts\\rasa.exe run actions
    .\\.venv\\Scripts\\rasa.exe run --enable-api --cors "*" -p 5005

Then run:

    .\\.venv\\Scripts\\python.exe tests\\run_buddybot_acceptance_tests.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


DEFAULT_RASA_URL = "http://127.0.0.1:5005"
DEFAULT_CASES = Path(__file__).with_name("buddybot_acceptance_cases.json")
DEFAULT_REPORT = Path(__file__).with_name("buddybot_acceptance_failures.json")


@dataclass
class CaseResult:
    id: str
    passed: bool
    message: str
    expected_route: str
    response_text: str = ""
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    actions: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def load_cases(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list of test cases")
    return data


def normalize_text(text: str) -> str:
    return " ".join(str(text or "").casefold().split())


def contains_any(text: str, keywords: Iterable[str]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(keyword) in normalized for keyword in keywords if str(keyword).strip())


def missing_all_keywords(text: str, keywords: Iterable[str]) -> List[str]:
    normalized = normalize_text(text)
    return [
        str(keyword)
        for keyword in keywords
        if str(keyword).strip() and normalize_text(keyword) not in normalized
    ]


def forbidden_hits(text: str, keywords: Iterable[str]) -> List[str]:
    normalized = normalize_text(text)
    return [
        str(keyword)
        for keyword in keywords
        if str(keyword).strip() and normalize_text(keyword) in normalized
    ]


def post_json(url: str, payload: Dict[str, Any], timeout: int) -> Tuple[Optional[Any], Optional[str]]:
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json(), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def get_json(url: str, timeout: int) -> Tuple[Optional[Any], Optional[str]]:
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json(), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def parse_message(rasa_url: str, message: str, timeout: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    data, error = post_json(f"{rasa_url}/model/parse", {"text": message}, timeout)
    if error:
        return None, error
    return data if isinstance(data, dict) else None, None


def send_message(rasa_url: str, sender: str, message: str, timeout: int) -> Tuple[str, Optional[str]]:
    payload = {"sender": sender, "message": message}
    data, error = post_json(f"{rasa_url}/webhooks/rest/webhook", payload, timeout)
    if error:
        return "", error
    if not isinstance(data, list):
        return "", f"Unexpected REST webhook response: {data!r}"

    text_parts: List[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if item.get("text"):
            text_parts.append(str(item["text"]))
        if item.get("image"):
            text_parts.append(str(item["image"]))
        if item.get("attachment"):
            text_parts.append(str(item["attachment"]))
        for button in item.get("buttons") or []:
            if isinstance(button, dict) and button.get("title"):
                text_parts.append(str(button["title"]))
    return "\n".join(text_parts).strip(), None


def tracker_actions_after_latest_user(rasa_url: str, sender: str, timeout: int) -> Tuple[List[str], Optional[str]]:
    tracker, error = get_json(f"{rasa_url}/conversations/{sender}/tracker", timeout)
    if error:
        return [], error
    events = (tracker or {}).get("events") or []
    latest_user_index = -1
    for index, event in enumerate(events):
        if event.get("event") == "user":
            latest_user_index = index
    actions: List[str] = []
    for event in events[latest_user_index + 1 :]:
        if event.get("event") == "action" and event.get("name"):
            actions.append(str(event["name"]))
    return actions, None


def action_matches(actions: List[str], expected: List[str]) -> bool:
    if not expected:
        return True
    for actual in actions:
        for wanted in expected:
            if wanted.endswith("*"):
                if actual.startswith(wanted[:-1]):
                    return True
            elif actual == wanted:
                return True
    return False


def sender_for_case(case: Dict[str, Any], run_id: str) -> str:
    session_id = case.get("session_id")
    if session_id:
        return f"{run_id}_{session_id}"
    return f"{run_id}_{case['id']}"


def evaluate_case(
    case: Dict[str, Any],
    rasa_url: str,
    run_id: str,
    timeout: int,
    inspect_api: bool,
    require_inspection: bool,
) -> CaseResult:
    sender = sender_for_case(case, run_id)
    message = str(case["message"])
    result = CaseResult(
        id=str(case["id"]),
        passed=True,
        message=message,
        expected_route=str(case.get("expected_route", "")),
    )

    parsed: Optional[Dict[str, Any]] = None
    if inspect_api:
        parsed, parse_error = parse_message(rasa_url, message, timeout)
        if parse_error:
            msg = f"Could not inspect intent via /model/parse: {parse_error}"
            if require_inspection:
                result.failures.append(msg)
            else:
                result.warnings.append(msg)
        elif parsed:
            intent = parsed.get("intent") or {}
            result.intent = intent.get("name")
            result.intent_confidence = intent.get("confidence")

    response_text, send_error = send_message(rasa_url, sender, message, timeout)
    result.response_text = response_text
    if send_error:
        result.failures.append(f"REST webhook error: {send_error}")
        result.passed = False
        return result

    if inspect_api:
        actions, tracker_error = tracker_actions_after_latest_user(rasa_url, sender, timeout)
        result.actions = actions
        if tracker_error:
            msg = f"Could not inspect actions via tracker API: {tracker_error}"
            if require_inspection:
                result.failures.append(msg)
            else:
                result.warnings.append(msg)

    expected_intents = list(case.get("expected_intents") or [])
    if expected_intents and result.intent and result.intent not in expected_intents:
        result.failures.append(
            f"Intent mismatch: expected one of {expected_intents}, got {result.intent!r}"
        )

    expected_actions = list(case.get("expected_actions") or [])
    if expected_actions and result.actions and not action_matches(result.actions, expected_actions):
        result.failures.append(
            f"Action mismatch: expected one of {expected_actions}, got {result.actions}"
        )
    elif expected_actions and not result.actions and require_inspection:
        result.failures.append(f"No actions available to compare; expected one of {expected_actions}")

    expected_all = list(case.get("expected_keywords_all") or [])
    missing = missing_all_keywords(response_text, expected_all)
    if missing:
        result.failures.append(f"Missing required keywords: {missing}")

    expected_any = list(case.get("expected_keywords_any") or [])
    if expected_any and not contains_any(response_text, expected_any):
        result.failures.append(f"Expected at least one keyword from: {expected_any}")

    forbidden = list(case.get("forbidden_keywords") or [])
    hits = forbidden_hits(response_text, forbidden)
    if hits:
        result.failures.append(f"Forbidden keywords appeared: {hits}")

    result.passed = not result.failures
    return result


def filter_cases(cases: List[Dict[str, Any]], include: List[str], exclude: List[str]) -> List[Dict[str, Any]]:
    if not include and not exclude:
        return cases
    selected: List[Dict[str, Any]] = []
    include_set = {item.casefold() for item in include}
    exclude_set = {item.casefold() for item in exclude}
    for case in cases:
        haystack = {
            str(case.get("id", "")).casefold(),
            str(case.get("category", "")).casefold(),
            str(case.get("language", "")).casefold(),
            str(case.get("expected_route", "")).casefold(),
        }
        if include_set and not (haystack & include_set):
            continue
        if exclude_set and (haystack & exclude_set):
            continue
        selected.append(case)
    return selected


def write_failure_report(path: Path, results: List[CaseResult], metadata: Dict[str, Any]) -> None:
    failures = [result for result in results if not result.passed]
    payload = {
        "metadata": metadata,
        "failed_count": len(failures),
        "failures": [
            {
                "id": result.id,
                "message": result.message,
                "expected_route": result.expected_route,
                "intent": result.intent,
                "intent_confidence": result.intent_confidence,
                "actions": result.actions,
                "response_text": result.response_text,
                "failures": result.failures,
                "warnings": result.warnings,
            }
            for result in failures
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run BuddyBot Rasa HTTP acceptance tests.")
    parser.add_argument("--rasa-url", default=DEFAULT_RASA_URL, help="Base URL for Rasa server")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="Path to acceptance cases JSON")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Path for failed cases report")
    parser.add_argument("--timeout", type=int, default=40, help="HTTP timeout in seconds")
    parser.add_argument("--include", nargs="*", default=[], help="Only run cases matching id/category/language/route")
    parser.add_argument("--exclude", nargs="*", default=[], help="Skip cases matching id/category/language/route")
    parser.add_argument("--no-inspect-api", action="store_true", help="Do not call /model/parse or tracker APIs")
    parser.add_argument("--require-inspection", action="store_true", help="Fail if intent/action inspection is unavailable")
    parser.add_argument("--stop-on-fail", action="store_true", help="Stop after first failed case")
    args = parser.parse_args()

    cases = filter_cases(load_cases(args.cases), args.include, args.exclude)
    if not cases:
        print("No cases selected.")
        return 2

    run_id = f"accept_{int(time.time())}"
    inspect_api = not args.no_inspect_api
    results: List[CaseResult] = []

    print(f"BuddyBot acceptance tests")
    print(f"Rasa URL: {args.rasa_url}")
    print(f"Cases: {len(cases)}")
    print(f"Run id: {run_id}")
    print()

    for index, case in enumerate(cases, start=1):
        result = evaluate_case(
            case=case,
            rasa_url=args.rasa_url.rstrip("/"),
            run_id=run_id,
            timeout=args.timeout,
            inspect_api=inspect_api,
            require_inspection=args.require_inspection,
        )
        results.append(result)

        status = "PASS" if result.passed else "FAIL"
        intent_part = f" intent={result.intent}" if result.intent else ""
        actions_part = f" actions={result.actions}" if result.actions else ""
        print(f"[{status}] {index:03d}/{len(cases):03d} {result.id}: {result.message}{intent_part}{actions_part}")
        if result.warnings:
            for warning in result.warnings:
                print(f"       WARN: {warning}")
        if result.failures:
            for failure in result.failures:
                print(f"       FAIL: {failure}")
            print(f"       RESPONSE: {result.response_text[:500]}")
            if args.stop_on_fail:
                break

    passed = sum(1 for result in results if result.passed)
    failed = len(results) - passed
    metadata = {
        "rasa_url": args.rasa_url,
        "cases_file": str(args.cases),
        "run_id": run_id,
        "selected_count": len(cases),
        "executed_count": len(results),
        "passed_count": passed,
        "failed_count": failed,
        "inspect_api": inspect_api,
    }
    write_failure_report(args.report, results, metadata)

    print()
    print(f"Summary: {passed} passed, {failed} failed, {len(results)} executed.")
    print(f"Failure report: {args.report}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
