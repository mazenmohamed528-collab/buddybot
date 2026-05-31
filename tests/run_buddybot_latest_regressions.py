"""Latest BuddyBot routing regression tests.

Run while Rasa is serving REST on port 5005:

    python tests\run_buddybot_latest_regressions.py

The script sends messages to Rasa, checks lightweight response keywords, prints
PASS/FAIL, and writes failed cases to tests\buddybot_failed_regressions.json.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import requests


DEFAULT_URL = "http://127.0.0.1:5005/webhooks/rest/webhook"
REPORT_PATH = Path(__file__).with_name("buddybot_failed_regressions.json")


TESTS: List[Dict[str, Any]] = [
    {
        "name": "FCI identity quick reply does not search courses",
        "message": "What is FCI?",
        "must_all": ["Faculty of Computers and Information", "Sadat Academy", "five specialisations"],
        "must_any": ["Computer Sciences", "Artificial Intelligence", "Cyber Security"],
        "forbidden": ["course matches", "Feasibility", "efficiency", "coefficient"],
    },
    {
        "name": "BuddyBot identity expansion works",
        "message": "what are u",
        "must_all": ["I'm BuddyBot", "Student profiles", "Official documents"],
        "forbidden": ["created by", "course matches", "Source:"],
    },
    {
        "name": "English thanks stays chitchat",
        "message": "thanks",
        "must_all": ["You're welcome"],
        "forbidden": ["Student Affairs", "Source:", "course matches"],
    },
    {
        "name": "Arabic thanks stays chitchat",
        "message": "شكرا",
        "must_all": ["العفو", "أنا هنا"],
        "forbidden": ["شؤون الطلاب", "المصدر:", "Page"],
    },
    {
        "name": "gibberish asks for rephrase",
        "message": "hgj/gl",
        "must_all": ["rephrase"],
        "forbidden": ["Student Affairs", "Source:", "course matches"],
    },
    {
        "name": "student activities is a topic not student lookup",
        "message": "student activities",
        "must_all": ["Student activities at FCI", "hackathons"],
        "forbidden": ["StudentID", "matching students", "I couldn't find a student"],
    },
    {
        "name": "FCI policies phrase guard is not student lookup",
        "message": "fci policies",
        "must_all": ["key FCI academic policies", "Attendance", "Academic Warning"],
        "forbidden": ["StudentID", "matching students", "course matches"],
    },
    {
        "name": "tools topic uses hardcoded Data Science answer",
        "message": "tools for data science",
        "must_all": ["Essential tools for Data Science", "Python", "Power BI"],
        "forbidden": ["Source:", "course matches", "StudentID"],
    },
    {
        "name": "generic tools question stores clarification context",
        "message": "what are the tools used for it",
        "must_all": ["Which specialisation", "ISDS/Data Science"],
        "forbidden": ["Source:", "StudentID", "course matches"],
    },
    {
        "name": "tools clarification reply resolves department",
        "message": "data science",
        "must_all": ["Essential tools for Data Science", "Python", "Power BI"],
        "forbidden": ["Information Systems department", "Source:", "course matches"],
    },
    {
        "name": "unfiltered schedule asks for clarification",
        "message": "schedule",
        "must_all": ["What schedule are you looking for?", "schedule for Data Visualization", "Lab 4"],
        "forbidden": ["day:", "start time:", "course code:", "target group:"],
    },
    {
        "name": "extended study tips are hardcoded",
        "message": "how to study",
        "must_all": ["Study tips that actually work", "Pomodoro", "Programming"],
        "forbidden": ["Source:", "StudentID", "course matches"],
    },
    {
        "name": "extended Arabic study tips are not gibberish",
        "message": "\u0643\u064a\u0641 \u0623\u0630\u0627\u0643\u0631",
        "must_all": ["Study tips that actually work", "CS/IT students"],
        "forbidden": ["لم أفهم", "Source:", "StudentID"],
    },
    {
        "name": "Arabic fees typo is corrected",
        "message": "\u0627\u0644\u0635\u0627\u0631\u064a\u0641",
        "must_all": ["\u0627\u0644\u0631\u0633\u0648\u0645 \u0627\u0644\u062f\u0631\u0627\u0633\u064a\u0629", "40%"],
        "forbidden": ["لم أفهم", "Source:", "StudentID"],
    },
    {
        "name": "Arabic keyboard mash is rejected",
        "message": "\u0647\u0649\u0641\u062b\u0642\u0649\u0633\u0627\u0647\u062d",
        "must_all": ["\u0644\u0645 \u0623\u0641\u0647\u0645"],
        "forbidden": ["\u0633\u0627\u0639\u0629 \u0645\u0639\u062a\u0645\u062f\u0629", "Source:"],
    },
    {
        "name": "Arabic greeting uses warm template",
        "message": "\u0627\u0644\u0633\u0644\u0627\u0645 \u0639\u0644\u064a\u0643\u0645",
        "must_all": ["\u0623\u0647\u0644\u0627\u064b \u0648\u0633\u0647\u0644\u0627\u064b", "BuddyBot", "\u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0637\u0644\u0627\u0628"],
        "forbidden": ["Hey, I'm BuddyBot"],
    },
    {
        "name": "English greeting uses new template",
        "message": "hi",
        "must_all": ["Hey!", "FCI's campus assistant", "official documents", "Arabic or English"],
        "forbidden": ["Ask me about FCI students"],
    },
    {
        "name": "Computer Science overview is hardcoded",
        "message": "what is computer science",
        "must_all": ["Computer Science (CS)", "Theory & Mathematics", "Systems"],
        "forbidden": ["Source:", "StudentID", "course matches"],
    },
    {
        "name": "Programming hard feeling gets wellbeing answer",
        "message": "programming is hard",
        "must_all": ["How long it really takes", "Realistic timelines"],
        "forbidden": ["Source:", "StudentID"],
    },
    {
        "name": "Conversation continuation is not student lookup",
        "message": "not bad",
        "must_any": ["Glad", "Sure", "Tell me", "Good point"],
        "forbidden": ["StudentID", "I couldn't find a student", "course matches", "Source:"],
    },
    {
        "name": "Egyptian advice trigger is hardcoded",
        "message": "\u0627\u0646\u0635\u062d\u0646\u064a",
        "must_all": ["\u0628\u0643\u0644 \u0633\u0631\u0648\u0631", "\u0637\u0631\u0642 \u0627\u0644\u0645\u0630\u0627\u0643\u0631\u0629"],
        "forbidden": ["StudentID", "Source:", "\u0644\u0645 \u0623\u0641\u0647\u0645"],
    },
    {
        "name": "Egyptian study trigger is hardcoded",
        "message": "\u0639\u0627\u0648\u0632 \u0627\u0630\u0627\u0643\u0631",
        "must_all": ["\u0646\u0635\u0627\u064a\u062d \u0645\u0630\u0627\u0643\u0631\u0629", "Active Recall", "Anki"],
        "forbidden": ["StudentID", "Source:", "\u0644\u0645 \u0623\u0641\u0647\u0645"],
    },
    {
        "name": "Egyptian burnout trigger is hardcoded",
        "message": "\u0632\u0647\u0642\u062a",
        "must_all": ["CS \u0635\u0639\u0628\u0629", "\u0645\u0634 \u0645\u0639\u0646\u0627\u0647\u0627"],
        "forbidden": ["StudentID", "Source:", "\u0644\u0645 \u0623\u0641\u0647\u0645"],
    },
    {
        "name": "English intent opener routes to topic",
        "message": "i want to study better",
        "must_all": ["\u0646\u0635\u0627\u064a\u062d \u0645\u0630\u0627\u0643\u0631\u0629", "Active Recall"],
        "forbidden": ["StudentID", "I couldn't find a student", "Source:"],
    },
    {
        "name": "extended CV topic is hardcoded",
        "message": "cv for internship",
        "must_all": ["Writing a strong CV", "GitHub", "Projects"],
        "forbidden": ["Source:", "StudentID", "course matches"],
    },
    {
        "name": "transport question bypasses academy profile",
        "message": "how to get to Sadat Academy",
        "must_all": ["Getting to Sadat Academy", "Maadi Station", "Uber"],
        "forbidden": ["public higher-education institution", "founded in 1981"],
    },
    {
        "name": "github student pack topic is hardcoded",
        "message": "github student pack",
        "must_all": ["GitHub Student Developer Pack", "GitHub Copilot", "education.github.com/pack"],
        "forbidden": ["Source:", "StudentID"],
    },
    {
        "name": "course schedule routes to database",
        "message": "what's data science schedule",
        "must_any": ["ISDS", "Introduction to Data Science", "Saturday", "lecture"],
        "forbidden": ["Question 13", "Source:", "official FCI student guide"],
    },
    {
        "name": "department context is remembered",
        "message": "what's cyber security",
        "must_all": ["Cyber Security", "24"],
        "forbidden": ["Source:"],
    },
    {
        "name": "follow-up course list uses last department",
        "message": "what are the 24 courses?",
        "must_any": ["CSCS301", "Principles of Cryptology", "Courses for CSCS"],
        "forbidden": ["Question 37", "Source:"],
    },
    {
        "name": "all of them shows all remaining courses",
        "message": "all of them",
        "must_all": ["That's all 24 courses", "CSCS456"],
        "forbidden": ["Showing courses 6-10", "Say \"next\" or \"show more\""],
    },
    {
        "name": "short student suffix resolves safely",
        "message": "student 209",
        "must_all": ["2122209", "Mazen"],
        "forbidden": ["330 matching students", "first 10"],
    },
    {
        "name": "student GPA follow-up is academic record not student list",
        "message": "his gpa",
        "must_all": ["Academic Record", "Overall Cumulative GPA"],
        "forbidden": ["matching students", "third-year cumulative GPA", "academic year:"],
    },
    {
        "name": "student typo still routes to student list",
        "message": "show me srudents in data science",
        "must_all": ["matching students", "Information Systems & Data Science"],
        "forbidden": ["Question", "Source:", "email:", "department code", "current year"],
    },
    {
        "name": "student partial name lookup works",
        "message": "show me student Sarah Emad",
        "must_all": ["Sarah Emad", "2122285"],
        "forbidden": ["spelling mistake", "could not find matching data"],
    },
    {
        "name": "creator name still searches student when asked as student",
        "message": "Show me student Mazen Mohamed",
        "must_all": ["Mazen", "2122209"],
        "forbidden": ["one of BuddyBot's creators", "created by"],
    },
    {
        "name": "student pronoun email uses last student",
        "message": "his email",
        "must_all": ["Mazen.Badawy.22209@sadatacademy.edu.eg"],
        "forbidden": ["His Email", "Student Affairs", "couldn't find a student"],
    },
    {
        "name": "bare student name lookup works",
        "message": "Marceleno Ayman Eskander",
        "must_all": ["Marceleno Ayman Eskander Grace", "2122051"],
        "forbidden": ["spelling mistake", "could not find matching data"],
    },
    {
        "name": "unknown student name uses Student Affairs fallback",
        "message": "show me student Notareal Person",
        "must_all": ["I couldn't find a student named", "Student Affairs", "FCI"],
        "forbidden": ["spelling mistake", "could not find matching data"],
    },
    {
        "name": "bare instructor lookup works",
        "message": "Ahmed Esmat",
        "must_all": ["Courses taught by", "Ahmed Esmat"],
        "must_any": ["ISDS301", "Introduction to Data Science", "Data Mining"],
    },
    {
        "name": "Wael teaching query is not hijacked by project bio",
        "message": "what courses dr wael teach",
        "must_all": ["Courses taught by", "Wael"],
        "must_any": ["Big Data", "Blockchain", "IoT"],
        "forbidden": ["Courses for CS", "supervised the BuddyBot project"],
    },
    {
        "name": "institution context is remembered",
        "message": "what's Sadat Academy?",
        "must_all": ["Sadat Academy", "Maadi"],
        "forbidden": ["Source:"],
    },
    {
        "name": "pronoun follow-up does not search for course 'it'",
        "message": "tell me about it",
        "must_any": ["Sadat Academy", "Maadi"],
        "forbidden": ["Digital Circuitry", "English for IT Professionals", "course matches for 'it'"],
    },
    {
        "name": "department comparison returns both sides",
        "message": "what's the difference between data science and AI?",
        "must_all": ["Difference", "ISDS", "AI"],
        "forbidden": ["Question", "Source:"],
    },
    {
        "name": "Arabic specialization policy is clean",
        "message": "تغيير التخصص",
        "must_all": ["مرة واحدة", "السنة النهائية"],
        "forbidden": ["المصدر:", "Source:", "سؤال", "حسب", "لم أجد طالبا"],
    },
    {
        "name": "Arabic fees policy is not student lookup",
        "message": "الرسوم الدراسية",
        "must_all": ["الرسوم الدراسية", "40%"],
        "forbidden": ["لم أجد طالبا", "المصدر:", "سؤال"],
    },
    {
        "name": "Arabic absence policy is clean",
        "message": "الغياب",
        "must_all": ["25%", "ساعات المقرر"],
        "forbidden": ["ممكن توضح", "25٪ 25%", "?", "؟", "المصدر:"],
    },
    {
        "name": "Arabic enrollment certificate is hardcoded",
        "message": "ازاي اطلع اثبات قيد؟",
        "must_all": ["إثبات القيد", "شؤون الطلاب", "بطاقة الرقم القومي"],
        "forbidden": ["الساعات المعتمدة", "التخصص", "Page", "المادة رقم", "المعادي.\n📍 مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، المعادي"],
    },
    {
        "name": "Arabic fee synonym is hardcoded",
        "message": "كام المصاريف؟",
        "must_all": ["الرسوم الدراسية", "40%", "المبلغ الدقيق"],
        "forbidden": ["Page", "المادة رقم", "Source:"],
    },
    {
        "name": "Arabic complaint synonym is hardcoded",
        "message": "أشتكي فين؟",
        "must_all": ["تقديم شكوى رسمية", "مكتب شؤون الطلاب", "وكيل الكلية"],
        "forbidden": ["Page", "المادة رقم", "Source:"],
    },
    {
        "name": "Arabic grade appeal is hardcoded",
        "message": "ازاي اقدم تظلم؟",
        "must_all": ["التظلم من نتيجة الامتحان", "شؤون الطلاب", "لجنة مراجعة"],
        "forbidden": ["الساعات المعتمدة", "Page", "المادة رقم", "Source:"],
    },
    {
        "name": "Arabic result inquiry is hardcoded",
        "message": "امتى النتايج؟",
        "must_all": ["الاستعلام عن النتيجة", "أسبوعين", "مكتب شؤون الطلاب"],
        "forbidden": ["Page", "المادة رقم", "Source:"],
    },
    {
        "name": "Arabic fee payment is hardcoded",
        "message": "عايز ادفع المصروفات",
        "must_all": ["دفع المصروفات الدراسية", "إيصال الدفع", "الإدارة المالية"],
        "forbidden": ["Page", "المادة رقم", "Source:"],
    },
    {
        "name": "Arabic training is hardcoded",
        "message": "تدريب صيفي",
        "must_all": ["التدريب الصيفي", "خطاب تدريب", "LinkedIn"],
        "forbidden": ["Page", "المادة رقم", "Source:"],
    },
    {
        "name": "Arabic graduation project is hardcoded",
        "message": "مشروع تخرج",
        "must_all": ["مشروع التخرج", "السنة الرابعة", "4 أسابيع"],
        "forbidden": ["Page", "المادة رقم", "Source:"],
    },
    {
        "name": "Arabic academic warning policy is hardcoded",
        "message": "الانذار الاكاديمي",
        "must_all": ["2.0", "15 ساعة"],
        "forbidden": ["المادة رقم", "Page", "المصدر:"],
    },
    {
        "name": "Arabic advising and registration policy is hardcoded",
        "message": "الارشاد و التسجيل",
        "must_all": ["المرشدون الأكاديميون", "15 ساعة"],
        "forbidden": ["من يضع", "ما الحد", "المصدر:"],
    },
    {
        "name": "Arabic vision mission goals policy is hardcoded",
        "message": "رؤية و رسالة و اهداف الكلية",
        "must_all": ["رؤية الكلية", "رسالة الكلية", "أهداف الكلية"],
        "forbidden": ["Page", "المادة رقم", "English translation pending"],
    },
    {
        "name": "Arabic incomplete grade policy is hardcoded",
        "message": "الرسوب وتقدير غير مكتمل",
        "must_all": ["تقدير غير مكتمل", "F"],
        "forbidden": ["English translation pending", "Use the paired Arabic", "المادة رقم"],
    },
    {
        "name": "Arabic exam policy is hardcoded",
        "message": "نظام الامتحانات",
        "must_all": ["الامتحان الهجين", "اعتماد النتائج"],
        "forbidden": ["نظام تأديب الطلاب", "المادة رقم", "Page"],
    },
    {
        "name": "Arabic scientific departments policy is hardcoded",
        "message": "الاقسام العلمية",
        "must_all": ["خمسة تخصصات", "الذكاء الاصطناعي", "الأمن السيبراني"],
        "forbidden": ["بحسب المصادر", "علوم الحاسب، هندسة البرمجيات"],
    },
    {
        "name": "Arabic department-section wording returns scientific departments policy",
        "message": "قسم علوم الحاسب",
        "must_all": ["خمسة تخصصات", "علوم الحاسب", "هندسة البرمجيات"],
        "forbidden": ["الخوارزميات، هياكل البيانات", "الدراسات العليا"],
    },
    {
        "name": "unknown question uses helpful fallback",
        "message": "what is the cafeteria robot policy?",
        "must_any": ["Student Affairs", "شؤون الطلاب", "I don't have that information"],
        "forbidden": ["Question", "Source:"],
    },
]


def merged_text(responses: List[Dict[str, Any]]) -> str:
    return "\n".join(str(item.get("text") or "") for item in responses).strip()


def contains_all(text: str, expected: List[str]) -> bool:
    lowered = text.lower()
    return all(item.lower() in lowered for item in expected)


def contains_any(text: str, expected: List[str]) -> bool:
    if not expected:
        return True
    lowered = text.lower()
    return any(item.lower() in lowered for item in expected)


def contains_none(text: str, forbidden: List[str]) -> bool:
    lowered = text.lower()
    return all(item.lower() not in lowered for item in forbidden)


def run_case(url: str, sender: str, case: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    response = requests.post(
        url,
        json={"sender": sender, "message": case["message"]},
        timeout=timeout,
    )
    response.raise_for_status()
    text = merged_text(response.json())
    forbidden = case.get("forbidden") or []
    ok = (
        contains_all(text, case.get("must_all") or [])
        and contains_any(text, case.get("must_any") or [])
        and contains_none(text, forbidden)
    )
    return {
        "name": case["name"],
        "message": case["message"],
        "passed": ok,
        "response": text,
        "expected_all": case.get("must_all") or [],
        "expected_any": case.get("must_any") or [],
        "forbidden": forbidden,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--sender", default=f"buddybot-regression-{int(time.time())}")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    failures: List[Dict[str, Any]] = []
    for case in TESTS:
        try:
            result = run_case(args.url, args.sender, case, args.timeout)
        except Exception as exc:
            result = {
                "name": case["name"],
                "message": case["message"],
                "passed": False,
                "response": f"ERROR: {exc}",
            }
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} - {result['name']}")
        if not result["passed"]:
            print(f"  message: {result['message']}")
            print(f"  response: {result['response'][:500]}")
            failures.append(result)

    if failures:
        REPORT_PATH.write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSaved {len(failures)} failed case(s) to {REPORT_PATH}")
        return 1

    if REPORT_PATH.exists():
        REPORT_PATH.unlink()
    print("\nAll BuddyBot latest regressions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
