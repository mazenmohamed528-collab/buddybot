import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "models" / "gnn_student_exam_model.npz"

_CACHE: Dict[str, Any] = {"mtime": None, "artifact": None}


def _format_number(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if np.isnan(numeric):
        return "not recorded"
    return f"{numeric:.1f}".rstrip("0").rstrip(".")


def _format_points(value: Any) -> str:
    text = _format_number(abs(float(value)))
    unit = "point" if text == "1" else "points"
    return f"{text} {unit}"


def _friendly_label(column: str) -> str:
    labels = {
        "Attendance": "attendance",
        "Hours_Studied": "study hours",
        "Access_to_Resources": "resource access",
        "Previous_Scores": "previous score",
        "Parental_Involvement": "parental involvement",
        "Tutoring_Sessions": "tutoring sessions",
        "Motivation_Level": "motivation",
        "Teacher_Quality": "teacher quality",
        "Peer_Influence": "peer influence",
        "Family_Income": "family income",
        "Sleep_Hours": "sleep hours",
        "Physical_Activity": "physical activity",
        "Internet_Access": "internet access",
        "Learning_Disabilities": "learning disabilities",
    }
    return labels.get(column, column.replace("_", " ").lower())


def _friendly_value(column: str, value: Any) -> str:
    if value is None or str(value) == "not recorded":
        return "not recorded"
    if column in {"Internet_Access", "Learning_Disabilities", "Extracurricular_Activities"}:
        if str(value) == "1":
            return "yes"
        if str(value) == "0":
            return "no"
    if column == "Attendance":
        return f"{_format_number(value)}%"
    return _format_number(value)


def _possessive_pronoun(gender: Any) -> str:
    gender_text = str(gender).strip().lower()
    if gender_text == "male":
        return "his"
    if gender_text == "female":
        return "her"
    return "this student's"


def _subject_pronoun(gender: Any) -> str:
    gender_text = str(gender).strip().lower()
    if gender_text == "male":
        return "he"
    if gender_text == "female":
        return "she"
    return "this student"


def _object_pronoun(gender: Any) -> str:
    gender_text = str(gender).strip().lower()
    if gender_text == "male":
        return "him"
    if gender_text == "female":
        return "her"
    return "this student"


def _join_natural(items: list) -> str:
    items = [item for item in items if item]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _movement_sentence(change: float, previous: float, possessive: str) -> str:
    if np.isnan(previous):
        return "There is no previous score stored here, so I cannot compare the direction of change."

    previous_text = _format_number(previous)
    if abs(change) < 0.5:
        return f"It is basically unchanged from {possessive} previous score of {previous_text}."
    if change < 0:
        tone = "only a tiny" if abs(change) <= 1.5 else "a"
        return (
            f"Compared with {possessive} previous score of {previous_text}, "
            f"that is {tone} drop of {_format_points(change)}."
        )
    tone = "a small" if change <= 1.5 else "a"
    return (
        f"Compared with {possessive} previous score of {previous_text}, "
        f"that is {tone} rise of {_format_points(change)}."
    )


def _expectation_sentence(residual: float) -> str:
    gap = abs(residual)
    if gap <= 1.5:
        return "that is basically on target"
    if residual > 0:
        return f"it came in about {_format_points(gap)} higher than expected"
    return f"it came in about {_format_points(gap)} lower than expected"


def _pattern_sentence(actual: float, change: float, subject: str, possessive: str) -> str:
    actual_text = _format_number(actual)
    if change < -5:
        return (
            f"My read is: {possessive} previous score shows stronger past performance, "
            f"but the current pattern looks much closer to students scoring around {actual_text}."
        )
    if change > 5:
        return (
            f"My read is: {subject} improved, and {actual_text} still looks "
            "believable for this student's current pattern."
        )
    return f"My read is: {actual_text} is believable for this student's current pattern."


def _value_text(values_by_column: Dict[str, Any], column: str) -> str:
    return _friendly_value(column, values_by_column.get(column))


def _positive_clues(values_by_column: Dict[str, Any]) -> list:
    clues = []

    tutoring = values_by_column.get("Tutoring_Sessions")
    try:
        if float(tutoring) > 0:
            sessions = _format_number(tutoring)
            label = "session" if sessions == "1" else "sessions"
            clues.append(f"{sessions} tutoring {label}")
    except (TypeError, ValueError):
        pass

    involvement = str(values_by_column.get("Parental_Involvement", "")).strip()
    if involvement.lower() == "high":
        clues.append("high parental involvement")

    resources = str(values_by_column.get("Access_to_Resources", "")).strip()
    if resources.lower() == "high":
        clues.append("high resource access")

    motivation = str(values_by_column.get("Motivation_Level", "")).strip()
    if motivation.lower() == "high":
        clues.append("high motivation")

    hours = values_by_column.get("Hours_Studied")
    try:
        if float(hours) >= 20:
            clues.append(f"{_format_number(hours)} study hours")
    except (TypeError, ValueError):
        pass

    return clues


def _watchouts(values_by_column: Dict[str, Any]) -> list:
    watchouts = []

    attendance = values_by_column.get("Attendance")
    try:
        attendance_number = float(attendance)
        if attendance_number < 75:
            watchouts.append(f"attendance at only {_format_number(attendance)}%")
    except (TypeError, ValueError):
        pass

    resources = str(values_by_column.get("Access_to_Resources", "")).strip()
    if resources.lower() == "low":
        watchouts.append("low resource access")

    motivation = str(values_by_column.get("Motivation_Level", "")).strip()
    if motivation.lower() == "low":
        watchouts.append("low motivation")

    return watchouts


def _prediction_gap_sentence(residual: float, predicted_text: str) -> str:
    gap_text = _format_points(residual)
    if residual > 0:
        return f"My estimate was about {predicted_text}, so this is roughly {gap_text} higher than expected."
    return f"My estimate was about {predicted_text}, so this is roughly {gap_text} lower than expected."


def _quality_sentence(val_mae: Any) -> str:
    if val_mae is None:
        return "I'd treat that as a strong clue, not a guaranteed cause."
    return (
        f"This kind of estimate is usually within about {_format_number(val_mae)} score points, "
        "so I'd treat that as a strong clue, not a guaranteed cause."
    )


def _capitalize_sentence(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _load_artifact() -> Optional[Dict[str, Any]]:
    if not MODEL_PATH.exists():
        return None

    mtime = MODEL_PATH.stat().st_mtime
    if _CACHE["artifact"] is not None and _CACHE["mtime"] == mtime:
        return _CACHE["artifact"]

    data = np.load(MODEL_PATH, allow_pickle=True)
    artifact = {key: data[key] for key in data.files}
    if "metrics_json" in artifact:
        artifact["metrics"] = json.loads(str(artifact["metrics_json"]))
    else:
        artifact["metrics"] = {}

    _CACHE["mtime"] = mtime
    _CACHE["artifact"] = artifact
    return artifact


def explain_student_with_gnn(
    student_id: str,
    profile_context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    artifact = _load_artifact()
    if artifact is None:
        return None

    try:
        requested_id = int(student_id)
    except (TypeError, ValueError):
        return None

    student_ids = artifact["student_ids"].astype(int)
    matches = np.where(student_ids == requested_id)[0]
    if len(matches) == 0:
        return None

    index = int(matches[0])
    actual = float(artifact["actual_scores"][index])
    predicted = float(artifact["predictions"][index])
    previous = float(artifact["previous_scores"][index])
    residual = actual - predicted
    change = actual - previous

    neighbor_indices = artifact["neighbor_indices"][index].astype(int)
    actual_scores = artifact["actual_scores"].astype(float)
    neighbor_scores = actual_scores[neighbor_indices]
    neighbor_scores = neighbor_scores[~np.isnan(neighbor_scores)]
    neighbor_avg = float(np.mean(neighbor_scores)) if len(neighbor_scores) else float("nan")

    report_columns = [str(value) for value in artifact["report_columns"]]
    report_values = artifact["report_values"][index]
    source_importance = {
        str(source): float(score)
        for source, score in zip(
            artifact["importance_sources"],
            artifact["importance_scores"].astype(float),
        )
    }

    ranked_columns = sorted(
        report_columns,
        key=lambda column: source_importance.get(column, 0.0),
        reverse=True,
    )
    facts = []
    values_by_column = dict(zip(report_columns, report_values))
    for column in ranked_columns:
        value = values_by_column.get(column)
        if value is None or str(value) == "not recorded":
            continue
        label = _friendly_label(column)
        facts.append(f"{label} {_friendly_value(column, value)}")
        if len(facts) == 6:
            break

    metrics = artifact.get("metrics", {})
    val_mae = metrics.get("val_mae")
    quality = _quality_sentence(val_mae)

    comparison = ""
    if not np.isnan(neighbor_avg):
        comparison = f" Similar students average about {_format_number(neighbor_avg)}."

    fact_text = "; ".join(facts) if facts else "the available student factors"
    profile_context = profile_context or {}
    gender = profile_context.get("Gender", values_by_column.get("Gender"))
    possessive = _possessive_pronoun(gender)
    subject = _subject_pronoun(gender)
    obj = _object_pronoun(gender)
    movement = _movement_sentence(change, previous, possessive)
    expectation = _expectation_sentence(residual)
    pattern = _pattern_sentence(actual, change, subject, possessive)
    positive_clues = _positive_clues(values_by_column)
    watchouts = _watchouts(values_by_column)
    previous_text = _format_number(previous)
    actual_text = _format_number(actual)
    predicted_text = _format_number(predicted)
    residual_gap = abs(residual)

    if residual_gap > 6:
        clue_text = _join_natural(positive_clues) or fact_text
        watch_text = _join_natural(watchouts)
        watch_sentence = f" I would still keep an eye on {watch_text}." if watch_text else ""
        return (
            f"This one is unusual. {subject.capitalize()} scored {actual_text}, "
            f"with a previous score of {previous_text}. "
            f"{_prediction_gap_sentence(residual, predicted_text)} "
            f"Similar students average about {_format_number(neighbor_avg)}.\n\n"
            f"So I would not say the database fully explains this score. "
            f"The helpful clues are {clue_text}.{watch_sentence} "
            "But a jump this far above the expected pattern can also mean there is "
            "something missing from the temporary database, a special exam/bonus rule, "
            "or a value that needs checking.\n\n"
            f"So the honest answer is: {actual_text} is an outlier compared with similar "
            f"students, not something I would pretend is obvious. {quality}"
        )

    if change > 1.5:
        clue_text = _join_natural(positive_clues)
        if not clue_text:
            clue_text = f"{fact_text}"
        caution = ""
        if watchouts:
            caution = f" The part I would still watch is {_join_natural(watchouts)}."
        return (
            f"Yeah, {subject} improved: {previous_text} to {actual_text}, "
            f"up {_format_points(change)}. I would read that as a real lift, not just noise.\n\n"
            f"The closest matching pattern puts {obj} around {predicted_text}, "
            f"and similar students average about {_format_number(neighbor_avg)}. "
            f"The useful clues are {clue_text}.{caution}\n\n"
            "So my short answer is: the improvement looks believable from the support/study "
            f"signals and the similar-student pattern. {quality}"
        )

    if change < -1.5:
        watch_text = _join_natural(watchouts)
        if not watch_text:
            watch_text = f"{fact_text}"
        return (
            f"Yeah, that drop stands out: {previous_text} to {actual_text}, "
            f"down {_format_points(change)}. My estimate was about {predicted_text}, "
            f"so the final score is close to the expected pattern.\n\n"
            f"The things I would look at first are {watch_text}. "
            f"Similar students average about {_format_number(neighbor_avg)}, which is why "
            f"{actual_text} does not look strange from the data side. {quality}"
        )

    return (
        f"For StudentID {requested_id}, {actual_text} looks pretty consistent. "
        f"My estimate was around {predicted_text}, so {expectation}."
        f"{comparison}\n\n"
        f"The main clues are {fact_text}. {pattern} {quality}"
    )
