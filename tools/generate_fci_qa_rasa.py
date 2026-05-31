from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DOMAIN_PATH = PROJECT_ROOT / "domain.yml"
RULES_PATH = DATA_DIR / "rules.yml"
NLU_OUTPUT = DATA_DIR / "fci_qa_nlu.yml"
RULES_OUTPUT = DATA_DIR / "fci_qa_rules.yml"

DOCX_SOURCES = [
    Path(r"E:\OneDrive - Sadat Academy for Management Sciences\FinalYear\Grad_Project\files\New folder\FCI_Bilingual_QA_Dataset (1).docx"),
    Path(r"E:\OneDrive - Sadat Academy for Management Sciences\FinalYear\Grad_Project\files\New folder\FCI_Bilingual_QA_Bank (1).docx"),
]

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
def cell_text(cell: ET.Element) -> str:
    paragraphs = []
    for paragraph in cell.findall(".//w:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS))
        if text.strip():
            paragraphs.append(text.strip())
    return " ".join(paragraphs)


def extract_docx_text(path: Path) -> str:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))

    body = root.find("w:body", NS)
    if body is None:
        return ""

    blocks: list[str] = []
    for child in list(body):
        if child.tag.endswith("}p"):
            text = "".join(node.text or "" for node in child.findall(".//w:t", NS)).strip()
            if text:
                blocks.append(text)
        elif child.tag.endswith("}tbl"):
            rows = []
            for row in child.findall("w:tr", NS):
                cells = [cell_text(cell) for cell in row.findall("w:tc", NS)]
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                blocks.append("\n".join(rows))
    return "\n\n".join(blocks)


def clean_text(text: str) -> str:
    text = re.sub(r"-{8,}", " ", text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_qa_entries(text: str, source_name: str) -> list[dict[str, str]]:
    cleaned = re.sub(r"\n-{5,}\n", "\n", text)
    patterns = [
        (
            "en",
            re.compile(
                r"Q(?P<num>\d+)\s*\(EN\)\s*:\s*(?P<question>.*?)"
                r"A(?P=num)?\s*(?:\(EN\))?\s*:\s*(?P<answer>.*?)(?=\n\s*(?:Q\d+\s*\(EN\)\s*:|س\d+\s*:|[A-Z][A-Za-z &/-]{2,50}\n)|\Z)",
                flags=re.S,
            ),
        ),
        (
            "ar",
            re.compile(
                r"س(?P<num>\d+)\s*:\s*(?P<question>.*?)"
                r"ج(?P=num)?\s*:\s*(?P<answer>.*?)(?=\n\s*(?:Q\d+\s*\(EN\)\s*:|س\d+\s*:|[A-Z][A-Za-z &/-]{2,50}\n)|\Z)",
                flags=re.S,
            ),
        ),
    ]

    entries: list[dict[str, str]] = []
    for language, pattern in patterns:
        for match in pattern.finditer(cleaned):
            question = clean_text(match.group("question"))
            answer = clean_text(match.group("answer"))
            if question and answer:
                entries.append(
                    {
                        "source": source_name,
                        "number": match.group("num"),
                        "language": language,
                        "question": question,
                        "answer": answer,
                    }
                )
    return entries


TOPIC_RULES = OrderedDict(
    [
        ("vision", ["vision", "رؤية"]),
        ("mission", ["mission", "رسالة"]),
        ("goals", ["goals", "objectives", "أهداف", "الاهداف"]),
        ("departments", ["departments", "specializations", "majors", "أقسام", "الاقسام", "تخصصات"]),
        ("admission_requirements", ["admission requirements", "شروط القبول", "شروط الالتحاق"]),
        ("admission_documents", ["documents", "papers", "application", "الأوراق", "اوراق", "وثائق", "مستندات"]),
        ("transfer", ["transfer", "تحويل", "المحولين"]),
        ("study_system", ["study system", "credit-hour", "credit hour", "نظام الدراسة", "الساعات المعتمدة"]),
        ("study_plan", ["study plan", "خطة الدراسة"]),
        ("specialization", ["specialization", "major", "تخصص", "التخصص"]),
        ("change_specialization", ["change specialization", "change major", "تغيير التخصص", "تغيير المسار"]),
        ("graduation", ["graduate", "graduation", "bachelor", "تخرج", "البكالوريوس"]),
        ("registration", ["registration", "register", "تسجيل", "التسجيل"]),
        ("add_drop", ["add/drop", "add drop", "withdraw", "withdrawal", "drop", "إضافة", "الحذف", "الانسحاب"]),
        ("attendance", ["attendance", "absence", "absent", "الحضور", "الغياب", "غياب"]),
        ("registration_suspension", ["suspend", "suspension", "وقف التسجيل", "وقف القيد"]),
        ("exams", ["exam", "midterm", "final", "results", "امتحان", "الامتحانات", "الميدترم", "الفاينل"]),
        ("grading", ["grade", "grading", "gpa", "marks", "تقدير", "درجات", "المعدل"]),
        ("academic_warning", ["warning", "academic warning", "إنذار", "انذار"]),
        ("honors", ["honors", "honour", "مرتبة الشرف"]),
        ("fees", ["fees", "tuition", "refund", "رسوم", "المصاريف", "استرداد"]),
        ("discipline", ["discipline", "penalties", "violations", "تأديب", "عقوبات", "مخالفات"]),
        ("medical", ["medical", "الرعاية الطبية", "الكشف الطبي"]),
        ("training", ["training", "internship", "تدريب"]),
    ]
)


STOPWORDS = {
    "what",
    "when",
    "where",
    "which",
    "who",
    "how",
    "does",
    "are",
    "the",
    "for",
    "and",
    "with",
    "about",
    "explain",
    "tell",
    "give",
    "details",
    "fci",
    "faculty",
    "computer",
    "computers",
    "information",
}


def infer_topic(text: str) -> str:
    lowered = text.lower()
    for topic, keywords in TOPIC_RULES.items():
        for keyword in keywords:
            normalized_keyword = keyword.lower()
            if re.fullmatch(r"[a-z0-9 ]+", normalized_keyword):
                if re.search(rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])", lowered):
                    return topic
            elif normalized_keyword in lowered:
                return topic
    return "guide"


def slugify(text: str, language: str) -> str:
    topic = infer_topic(text)
    if language == "ar":
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
        return f"{topic}_{digest}"

    words = [
        word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if len(word) > 2 and word not in STOPWORDS
    ]
    suffix = "_".join(words[:5]) or hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    suffix = re.sub(r"[^a-z0-9_]+", "_", suffix).strip("_")
    return f"{topic}_{suffix[:48]}"


def normalize_answer(answer: str) -> str:
    return re.sub(r"\W+", "", answer.lower(), flags=re.UNICODE)


def variant_examples(question: str, language: str) -> list[str]:
    examples = [question]
    lower_question = question[:1].lower() + question[1:]
    if language == "en":
        prefixed = question.lower().startswith(("can you explain", "tell me", "i want to know", "give me details", "quick answer"))
        if prefixed:
            return unique_preserve_order(clean_text(example) for example in examples)
        if not question.lower().startswith("can you explain"):
            examples.append(f"Can you explain {lower_question}")
        examples.append(f"Tell me {lower_question}")
        examples.append(f"I want to know {lower_question}")
        examples.append(f"Give me details about {lower_question}")
        examples.append(f"quick answer: {lower_question}")
    else:
        prefixed = question.startswith(("ممكن", "عايز", "اشرح", "اديني"))
        if prefixed:
            return unique_preserve_order(clean_text(example) for example in examples)
        examples.append(f"ممكن توضح {question}")
        examples.append(f"عايز أعرف {question}")
        examples.append(f"اشرح {question}")
        examples.append(f"اديني تفاصيل عن {question}")
        examples.append(f"{question} في FCI")
    return unique_preserve_order(clean_text(example).rstrip("?؟") for example in examples)


def unique_preserve_order(items: Any) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def group_entries(entries: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
    for entry in entries:
        key = (entry["language"], normalize_answer(entry["answer"]))
        if key not in groups:
            slug = slugify(entry["question"], entry["language"])
            source_marker = hashlib.sha1(f"{entry['source']}:{entry['number']}:{entry['language']}".encode("utf-8")).hexdigest()[:6]
            intent = f"fci_qa_{slug}_{entry['language']}_{source_marker}"
            groups[key] = {
                "intent": intent,
                "response": f"utter_{intent}",
                "language": entry["language"],
                "answer": entry["answer"],
                "examples": [],
                "sources": set(),
            }
        groups[key]["examples"].extend(variant_examples(entry["question"], entry["language"]))
        groups[key]["sources"].add(entry["source"])

    final_groups = []
    used_intents = set()
    for group in groups.values():
        base_intent = group["intent"]
        intent = base_intent
        suffix = 2
        while intent in used_intents:
            intent = f"{base_intent}_{suffix}"
            suffix += 1
        group["intent"] = intent
        group["response"] = f"utter_{intent}"
        group["examples"] = unique_preserve_order(group["examples"])
        group["sources"] = sorted(group["sources"])
        final_groups.append(group)
        used_intents.add(intent)
    return final_groups


def add_manual_short_form_groups(groups: list[dict[str, Any]]) -> None:
    supplements = [
        {
            "intent": "fci_qa_change_specialization_short_ar",
            "response": "utter_fci_qa_change_specialization_short_ar",
            "language": "ar",
            "answer": (
                "يمكن تغيير التخصص مرة واحدة فقط خلال فترة الدراسة، ولا يسمح لطلاب السنة النهائية بتغيير التخصص. "
                "ويكون التغيير في حدود المقاعد الشاغرة. وتُقدَّم طلبات تغيير التخصص إلى عميد الكلية خلال الأسبوعين "
                "الأخيرين من الفصل الدراسي."
            ),
            "examples": [
                "تغيير التخصص",
                "تغيير المسار",
                "تغيير القسم",
                "ازاي اغير التخصص",
                "ممكن اغير تخصصي",
                "عايز اغير المسار",
                "قواعد تغيير التخصص",
                "شروط تغيير التخصص",
            ],
            "sources": ["FCI_Bilingual_QA_Bank (1).docx"],
        },
        {
            "intent": "fci_qa_departments_short_ar",
            "response": "utter_fci_qa_departments_short_ar",
            "language": "ar",
            "answer": "الأقسام المتاحة هي: علوم الحاسب، نظم المعلومات، وهندسة البرمجيات.",
            "examples": [
                "الاقسام",
                "الأقسام",
                "اقسام الكلية",
                "أقسام الكلية",
                "التخصصات",
                "ما هي الاقسام",
                "ايه الاقسام",
                "ايه تخصصات الكلية",
            ],
            "sources": ["FCI_Bilingual_QA_Dataset (1).docx", "FCI_Bilingual_QA_Bank (1).docx"],
        },
        {
            "intent": "fci_qa_specialization_short_ar",
            "response": "utter_fci_qa_specialization_short_ar",
            "language": "ar",
            "answer": (
                "يبدأ التخصص في الفرقة الثالثة. يختار الطالب تخصصًا رئيسيًا وآخر فرعيًا، ولا يجوز أن يكون "
                "التخصصان الرئيسي والفرعي في نفس المجال."
            ),
            "examples": [
                "التخصص",
                "نظام التخصص",
                "التخصص في الكلية",
                "متى التخصص",
                "امتى التخصص",
                "ازاي بيكون التخصص",
                "التخصص الرئيسي والفرعي",
            ],
            "sources": ["FCI_Bilingual_QA_Dataset (1).docx", "FCI_Bilingual_QA_Bank (1).docx"],
        },
        {
            "intent": "fci_qa_change_specialization_short_en",
            "response": "utter_fci_qa_change_specialization_short_en",
            "language": "en",
            "answer": (
                "A student may change specialization only once during the study period. Final-year students may not "
                "change specialization, and changes depend on available seats. Requests are submitted to the Dean "
                "during the last two weeks of the semester."
            ),
            "examples": [
                "change specialization",
                "change major",
                "can i change my major",
                "rules for changing specialization",
                "how do i change my specialization",
            ],
            "sources": ["FCI_Bilingual_QA_Bank (1).docx"],
        },
    ]
    existing = {group["intent"] for group in groups}
    for supplement in supplements:
        if supplement["intent"] not in existing:
            groups.append(supplement)
            existing.add(supplement["intent"])


def dump_nlu(groups: list[dict[str, Any]]) -> None:
    nlu = []
    for group in groups:
        examples = "\n".join(f"- {example}" for example in group["examples"])
        nlu.append({"intent": group["intent"], "examples": examples + "\n"})
    NLU_OUTPUT.write_text(yaml.safe_dump({"version": "3.1", "nlu": nlu}, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")


def dump_rules(groups: list[dict[str, Any]]) -> None:
    rules = []
    for group in groups:
        rules.append(
            {
                "rule": f"answer {group['intent']}",
                "steps": [
                    {"intent": group["intent"]},
                    {"action": group["response"]},
                ],
            }
        )
    RULES_OUTPUT.write_text(yaml.safe_dump({"version": "3.1", "rules": rules}, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")


def response_text(answer: str, language: str, sources: list[str]) -> str:
    source_label = ", ".join(sources)
    if language == "ar":
        return f"حسب دليل كلية الحاسبات والمعلومات الرسمي: {answer}\nالمصدر: {source_label}"
    return f"According to the official FCI student guide Q&A: {answer}\nSource: {source_label}"


def update_domain(groups: list[dict[str, Any]]) -> None:
    domain = yaml.safe_load(DOMAIN_PATH.read_text(encoding="utf-8"))
    domain.setdefault("intents", [])
    domain.setdefault("responses", {})
    domain["intents"] = [intent for intent in domain["intents"] if not str(intent).startswith("fci_qa_")]
    domain["responses"] = {
        name: response
        for name, response in domain["responses"].items()
        if not str(name).startswith("utter_fci_qa_")
    }

    intent_set = set(domain["intents"])
    for group in groups:
        if group["intent"] not in intent_set:
            domain["intents"].append(group["intent"])
            intent_set.add(group["intent"])
        domain["responses"][group["response"]] = [
            {"text": response_text(group["answer"], group["language"], group["sources"])}
        ]

    DOMAIN_PATH.write_text(yaml.safe_dump(domain, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")


def update_fallback_rule() -> None:
    data = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
    rules = data.setdefault("rules", [])
    for rule in rules:
        steps = rule.get("steps") or []
        if steps and steps[0].get("intent") == "nlu_fallback":
            rule["steps"] = [{"intent": "nlu_fallback"}, {"action": "action_conversation_router"}]
            break
    else:
        rules.append({"rule": "fallback rule", "steps": [{"intent": "nlu_fallback"}, {"action": "action_conversation_router"}]})
    RULES_PATH.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")


def main() -> None:
    entries: list[dict[str, str]] = []
    for path in DOCX_SOURCES:
        if not path.exists():
            raise FileNotFoundError(path)
        entries.extend(parse_qa_entries(extract_docx_text(path), path.name))

    groups = group_entries(entries)
    add_manual_short_form_groups(groups)
    dump_nlu(groups)
    dump_rules(groups)
    update_domain(groups)
    update_fallback_rule()
    print(f"Extracted {len(entries)} Q&A pairs from {len(DOCX_SOURCES)} DOCX files.")
    print(f"Generated {len(groups)} grouped Rasa QA intents.")
    print(f"Wrote {NLU_OUTPUT}")
    print(f"Wrote {RULES_OUTPUT}")
    print(f"Updated {DOMAIN_PATH}")
    print(f"Updated fallback rule in {RULES_PATH}")


if __name__ == "__main__":
    main()
