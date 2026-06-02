import os
import re
import sys
import time
import unicodedata
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any, Text, Dict, List, Optional, Sequence

import requests
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

try:
    import pyodbc
except Exception:
    pyodbc = None

try:
    import psycopg2
except Exception:
    psycopg2 = None

try:
    from actions.gnn_student_model import explain_student_with_gnn
except Exception:
    explain_student_with_gnn = None

try:
    from actions.fci_knowledge_base import (
        COURSES,
        DEPARTMENTS,
        find_courses_by_instructor,
        find_courses_by_keyword,
        format_course_answer,
        get_department,
        get_courses_by_dept,
    )
except Exception:
    try:
        from fci_knowledge_base import (
            COURSES,
            DEPARTMENTS,
            find_courses_by_instructor,
            find_courses_by_keyword,
            format_course_answer,
            get_department,
            get_courses_by_dept,
        )
    except Exception:
        COURSES = {}
        DEPARTMENTS = {}
        find_courses_by_instructor = None
        find_courses_by_keyword = None
        format_course_answer = None
        get_department = None
        get_courses_by_dept = None

try:
    from actions.extended_knowledge_base import extended_topic_answer, extended_topic_trigger_words
except Exception:
    try:
        from extended_knowledge_base import extended_topic_answer, extended_topic_trigger_words
    except Exception:
        def extended_topic_answer(question: str) -> Optional[str]:
            return None

        def extended_topic_trigger_words() -> set[str]:
            return set()

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"
RAG_URL = "http://127.0.0.1:8000/query"
SQL_ENGINE_URL = os.getenv("BUDDYBOT_SQL_ENGINE_URL") or "http://127.0.0.1:8010/query"
SQL_ENGINE_DISABLED = os.getenv("BUDDYBOT_DISABLE_SQL_ENGINE", "0").strip().lower() in {"1", "true", "yes"}
SQL_ENGINE_LOCAL_PATH = os.getenv("BUDDYBOT_SQL_ENGINE_LOCAL_PATH", r"C:\dev\sql_engine_service")
DB_DIALECT = (os.getenv("BUDDYBOT_DB_DIALECT") or os.getenv("DB_DIALECT") or "sqlserver").lower()
DB_URL = os.getenv("BUDDYBOT_DATABASE_URL") or os.getenv("DATABASE_URL")
DB_DRIVER = os.getenv("BUDDYBOT_DB_DRIVER", "ODBC Driver 17 for SQL Server")
DB_SERVER = os.getenv("BUDDYBOT_DB_SERVER") or os.getenv("DB_HOST") or "localhost"
DB_NAME = os.getenv("BUDDYBOT_DB_NAME") or os.getenv("DB_NAME") or "FCI_UNIVERSITY"
DB_USER = os.getenv("BUDDYBOT_DB_USER") or os.getenv("DB_USER")
DB_PASSWORD = os.getenv("BUDDYBOT_DB_PASSWORD") or os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("BUDDYBOT_DB_PORT") or os.getenv("DB_PORT")
DB_SSLMODE = os.getenv("BUDDYBOT_DB_SSLMODE") or os.getenv("DB_SSLMODE") or "require"
_LOCAL_SQL_ENGINE = None

CREATOR_TEAM_RESPONSE = (
    "BuddyBot was created by Mazen Mohamed Abdelmageed, Sama Waleed Hussein, "
    "Jonier Hany Fokeeh, Aliaa Amr Hamed, and Abdullah Mohamed Abdelhamed. "
    "They are Computer Science students in the Data Science major at Sadat Academy "
    "for Management Sciences in Egypt. The project was supervised by Assistant Prof. "
    "Dr. Wael Karam."
)

CREATOR_PERSON_RESPONSES = {
    "mazen": "Mazen Mohamed Abdelmageed is one of BuddyBot's creators and part of the student team behind the project.",
    "sama": "Sama Waleed Hussein is one of BuddyBot's creators and part of the student team behind the project.",
    "jonier": "Jonier Hany Fokeeh is one of BuddyBot's creators and part of the student team behind the project.",
    "aliaa": "Aliaa Amr Hamed is one of BuddyBot's creators and part of the student team behind the project.",
    "abdullah": "Abdullah Mohamed Abdelhamed is one of BuddyBot's creators and part of the student team behind the project.",
    "wael": (
        "Assistant Prof. Dr. Wael Karam supervised the BuddyBot project and is also an active "
        "FCI instructor teaching Blockchain, IoT, and Big Data courses."
    ),
}

PROJECT_PURPOSE_RESPONSE = (
    "The idea behind BuddyBot is to act like a friendly CampusGPT for university services. "
    "Instead of making students search static websites, portals, PDFs, social posts, or wait "
    "for admin replies, it gives them one chat interface for quick answers about things like "
    "student data, schedules, grades, exam dates, registration deadlines, and campus services."
)

PROJECT_WHY_RESPONSE = (
    "BuddyBot was created because university information is often scattered and slow to access. "
    "The goal is to give students fast 24/7 help while reducing repeated questions and workload "
    "for university staff."
)

FCI_IDENTITY_RESPONSE = (
    "The Faculty of Computers and Information (FCI) is part of Sadat Academy\n"
    "for Management Sciences, located in Maadi, Cairo.\n"
    "FCI offers a 4-year Bachelor's degree across five specialisations:\n"
    "- Computer Sciences (CS)\n"
    "- Artificial Intelligence (AI)\n"
    "- Cyber Security (CSCS)\n"
    "- Information Systems & Data Science (ISDS)\n"
    "- Software Engineering (SE)\n"
    "The first two years cover shared foundation courses for all students.\n"
    "Specialisation begins in Year 3.\n"
    "BuddyBot is FCI's campus assistant — ask me about students, courses,\n"
    "GPA, schedules, instructors, or any FCI policy!"
)

STUDENT_AFFAIRS_CONTACT_EN = (
    "Student Affairs at FCI can help with official student services, forms, certificates, "
    "registration questions, and cases that need direct administrative confirmation.\n"
    "📍 Faculty of Computers & Information, Sadat Academy, Maadi Campus."
)

STUDENT_AFFAIRS_CONTACT_AR = (
    "شؤون الطلاب في كلية الحاسبات والمعلومات يمكنهم مساعدتك في الخدمات الرسمية، "
    "الشهادات، النماذج، التسجيل، وأي موضوع يحتاج تأكيداً إدارياً مباشراً.\n"
    "📍 كلية الحاسبات والمعلومات، أكاديمية السادات، فرع المعادي."
)

ACTIVITIES_EN_RESPONSE = (
    "Student activities at FCI include cultural, sports, technical, and social events:\n"
    "- Cultural and arts activities such as theatre, music, public speaking, and debates.\n"
    "- Sports activities such as football, volleyball, basketball, table games, and chess.\n"
    "- Technical clubs and competitions such as programming, AI, cybersecurity, CTF, hackathons, and app development.\n"
    "- Trips, open days, festivals, and graduation project exhibitions.\n"
    "To join or ask about current dates, contact the Student Union or Student Affairs.\n"
    "📍 Faculty of Computers & Information, Sadat Academy, Maadi Campus."
)

DISCIPLINE_EN_RESPONSE = (
    "Student discipline at FCI follows the university regulations. Disciplinary actions can range "
    "from warnings to exam restrictions, temporary suspension, or final dismissal in serious cases. "
    "For an official case review, please contact Student Affairs or the faculty administration.\n"
    "📍 Faculty of Computers & Information, Sadat Academy, Maadi Campus."
)

ACADEMIC_WARNING_EN_RESPONSE = (
    "⚠️ Academic Warning at FCI:\n\n"
    "Triggered when: your cumulative GPA drops below 2.0.\n\n"
    "What happens:\n"
    "- Your maximum credit load is capped at 15 hours/semester.\n"
    "- You have 2 semesters to raise your GPA to at least 2.0.\n"
    "- If you reach 2.0 → warning is cleared.\n"
    "- If you don't after 2 semesters → you may only re-register courses you previously failed.\n"
    "- You get exactly 2 chances total to clear the warning.\n\n"
    "Specialisation change option:\n"
    "You may transfer to another major within FCI if it improves your chances of clearing the warning "
    "(requires Vice Dean approval).\n\n"
    "How to avoid it:\n"
    "- Don't skip classes — 25% absence = automatic fail.\n"
    "- Study consistently, not just before exams.\n"
    "- See your academic advisor early if you're struggling.\n"
    "- Use the add/drop period to drop courses you can't handle.\n\n"
    "📍 If you're at risk, visit Student Affairs immediately.\n"
    "📍 FCI, Sadat Academy, Maadi Campus."
)

ABSENCE_POLICY_EN_RESPONSE = (
    "📋 FCI Absence Policy — The 25% Rule:\n\n"
    "If your absences exceed 25% of total teaching hours for ANY course:\n"
    "❌ You are automatically FAILED in that course.\n"
    "❌ You are BARRED from sitting the final exam.\n\n"
    "Exception: if your absence is excused and approved by the Faculty Council, "
    "you receive a W (Withdrawn) grade instead of a fail.\n\n"
    "⚠️ You will receive a written absence warning before reaching the limit — don't ignore it.\n\n"
    "Students must attend: lectures, practical sessions, midterm exams, labs, "
    "and all registered course activities.\n\n"
    "📍 Report any absences to Student Affairs immediately.\n"
    "📍 FCI, Sadat Academy, Maadi Campus."
)

TUITION_FEES_EN_RESPONSE = (
    "💰 FCI Tuition Fees & Refund Policy:\n\n"
    "Fees are set by the Academy's Academic Council each year.\n\n"
    "Refund policy if you withdraw:\n"
    "- Week 1 of semester:            100% refunded ✅\n"
    "- After week 1, before 3 weeks:   70% refunded\n"
    "- After 3 weeks, before midterms: 40% refunded\n"
    "- After midterm exams:              0% refunded ❌\n\n"
    "Important:\n"
    "- You cannot register for courses until fees are paid.\n"
    "- Keep your payment receipt — required for registration.\n"
    "- Payment is available at the Finance Office directly or via bank transfer "
    "(ask Finance for account details).\n\n"
    "For the exact amount for this semester:\n"
    "📍 Finance Office / Student Affairs\n"
    "📍 FCI, Sadat Academy, Maadi Campus."
)

CHANGE_MAJOR_EN_RESPONSE = (
    "🔄 Changing Your Specialisation at FCI:\n\n"
    "Rules:\n"
    "- You may only change specialisation ONCE during your entire study period.\n"
    "- Final year students cannot change specialisation.\n"
    "- Changes are subject to available seats in the requested specialisation.\n"
    "- Requests are submitted to the Dean during the last 2 weeks of the semester.\n\n"
    "Academic warning exception:\n"
    "If you are on academic warning, you may transfer to another specialisation within FCI "
    "if it improves your chances of clearing the warning — requires Vice Dean approval.\n\n"
    "The five specialisations available:\n"
    "- Computer Sciences (CS)\n"
    "- Artificial Intelligence (AI)\n"
    "- Cyber Security (CSCS)\n"
    "- Information Systems & Data Science (ISDS)\n"
    "- Software Engineering (SE)\n\n"
    "📍 Submit your request to Student Affairs or the Dean's office.\n"
    "📍 FCI, Sadat Academy, Maadi Campus."
)

ADD_DROP_EN_RESPONSE = (
    "📋 FCI Add/Drop Policy:\n\n"
    "- Students may add courses or withdraw/drop courses during the first 2 weeks "
    "from the start of the semester, following the faculty's official procedures.\n"
    "- After this period, withdrawal may be recorded as W or F in the student's record "
    "unless there is an accepted excuse approved by the Faculty Council.\n"
    "- After dropping a course, the student's study load must not fall below "
    "15 credit hours unless the faculty approves an exception.\n\n"
    "📍 For the official form and deadlines for the current semester, visit Student Affairs.\n"
    "📍 FCI, Sadat Academy, Maadi Campus."
)

DOCUMENTS_EN_RESPONSE = (
    "Official student documents are requested through Student Affairs. Common documents include "
    "enrollment certificates, military-service certificates, transcripts, graduation certificates, "
    "replacement documents, and embassy or employer letters. Bring your national ID and student card, "
    "and mention the purpose of the document clearly.\n"
    "📍 Faculty of Computers & Information, Sadat Academy, Maadi Campus."
)

INTERNSHIP_EN_RESPONSE = (
    "For internships, FCI students can request an official training letter from Student Affairs, "
    "then submit it to a company with their CV. After finishing the internship, bring the completion "
    "certificate back to Student Affairs or your academic advisor so it can be recorded.\n"
    "Useful places to search include LinkedIn, WUZZUF, Forasna, faculty groups, and instructors' industry contacts.\n"
    "📍 Faculty of Computers & Information, Sadat Academy, Maadi Campus."
)

FCI_POLICY_SUMMARY_RESPONSE = (
    "Here are the key FCI academic policies BuddyBot can answer:\n"
    "📋 Attendance — 25% absence limit per course\n"
    "📋 Academic Warning — triggered when GPA drops below 2.0\n"
    "📋 Specialisation Change — once only, not in final year\n"
    "📋 Exam System — hybrid (electronic + traditional)\n"
    "📋 Grading Scale — 4.0 system (A+ to F)\n"
    "📋 Tuition Fees — set by Academy Council, refund policy applies\n"
    "📋 Add/Drop — within first 2 weeks of semester\n"
    "📋 Registration Freeze — up to 4 semesters total\n"
    "📋 Discipline — University Law No. 49 of 1972\n\n"
    "Ask me about any of these topics for full details!"
)

SCHEDULE_CLARIFICATION_RESPONSE = (
    "What schedule are you looking for? You can ask by:\n"
    "- Course name: 'schedule for Data Visualization'\n"
    "- Group: 'schedule for ISDS group'\n"
    "- Day: 'Saturday schedule'\n"
    "- Instructor: 'Dr Ahmed Esmat's schedule'\n"
    "- Room: 'what's in Lab 4'"
)

TOOLS_ISDS_RESPONSE = (
    "Essential tools for Data Science (ISDS) students:\n\n"
    "🐍 Programming & Analysis:\n"
    "- Python — pandas, NumPy, scikit-learn for data manipulation and ML.\n"
    "- SQL — for querying relational databases (required for every ISDS job).\n"
    "- Jupyter Notebook / Google Colab — for experiments and notebooks.\n\n"
    "📊 Business Intelligence & Visualisation:\n"
    "- Power BI or Tableau — dashboards, reports, and data storytelling.\n"
    "  (Know at least one well before graduation.)\n"
    "- Matplotlib / Seaborn — for Python-based charts.\n\n"
    "🤖 Machine Learning:\n"
    "- scikit-learn — start here for classical ML.\n"
    "- XGBoost / LightGBM — for competitions and production models.\n"
    "- TensorFlow or PyTorch — for deep learning.\n\n"
    "☁️ Big Data:\n"
    "- Apache Spark — for large-scale data processing (ISDS455).\n"
    "- Hadoop / Hive — ecosystem for distributed data storage.\n"
    "- Apache Kafka — for real-time data streams.\n\n"
    "📦 Databases:\n"
    "- SQL Server / PostgreSQL — relational.\n"
    "- MongoDB — NoSQL document store.\n"
    "- Tableau / Power BI — BI layer.\n\n"
    "🗂️ Version Control & Collaboration:\n"
    "- Git + GitHub — essential for all projects.\n"
    "- Kaggle — datasets, competitions, and community notebooks."
)

TOOLS_CSCS_RESPONSE = (
    "Essential tools for Cyber Security (CSCS) students:\n\n"
    "🐧 Operating Systems & Shell:\n"
    "- Linux (Kali Linux preferred) — standard OS for security work.\n"
    "- Bash scripting — for automation and tool chaining.\n\n"
    "🔍 Network Analysis:\n"
    "- Wireshark — network packet capture and analysis.\n"
    "- Nmap — network scanning and host discovery.\n"
    "- Zeek — network monitoring and threat detection.\n\n"
    "🕸️ Web Application Security:\n"
    "- Burp Suite Community — intercepting proxy for web pen testing.\n"
    "- OWASP ZAP — automated web vulnerability scanner.\n\n"
    "💥 Exploitation & CTF:\n"
    "- Metasploit Framework — exploitation and post-exploitation.\n"
    "- Hack The Box / TryHackMe — practice platforms for ethical hacking.\n"
    "- CTFd — for participating in Capture The Flag competitions.\n\n"
    "🔐 Cryptography & Forensics:\n"
    "- OpenSSL — for cryptographic operations.\n"
    "- Autopsy / FTK Lite — digital forensics investigation.\n"
    "- Volatility — memory forensics.\n\n"
    "☁️ Cloud & Containers:\n"
    "- Docker — containerisation basics.\n"
    "- AWS Free Tier + GuardDuty — cloud security practice.\n\n"
    "🐍 Programming:\n"
    "- Python — scripting, tool development, automation.\n"
    "- Git + GitHub — version control for all projects."
)

TOOLS_CS_RESPONSE = (
    "Essential tools for Computer Science (CS) students:\n\n"
    "💻 Development:\n"
    "- VS Code or IntelliJ IDEA — primary IDE.\n"
    "- Python, Java, C++ — core languages.\n"
    "- Git + GitHub — version control (mandatory for every project).\n\n"
    "🌐 Web & APIs:\n"
    "- React — frontend framework.\n"
    "- FastAPI or Node.js — backend API development.\n"
    "- Postman — API testing.\n\n"
    "🗄️ Databases:\n"
    "- SQL Server / PostgreSQL — relational databases.\n"
    "- MongoDB — NoSQL basics.\n\n"
    "🤖 AI & Data:\n"
    "- Python + NumPy + pandas + scikit-learn — AI fundamentals.\n"
    "- TensorFlow or PyTorch — deep learning.\n"
    "- Google Colab — free GPU for experiments.\n\n"
    "🐋 DevOps:\n"
    "- Docker — containerisation basics.\n"
    "- GitHub Actions — CI/CD pipelines.\n\n"
    "👁️ Graphics & Vision:\n"
    "- OpenGL — for the Computer Graphics course.\n"
    "- OpenCV — for Computer Vision."
)

TOOLS_SE_RESPONSE = (
    "Essential tools for Software Engineering (SE) students:\n\n"
    "🗂️ Version Control & Collaboration:\n"
    "- Git + GitHub — branching, pull requests, code review.\n"
    "- GitHub Actions / Jenkins — CI/CD pipelines.\n\n"
    "💻 Development:\n"
    "- VS Code or IntelliJ IDEA — primary IDE.\n"
    "- Python, Java, or C# — core languages for SE courses.\n"
    "- Postman — API testing and documentation.\n\n"
    "🧪 Testing:\n"
    "- JUnit (Java) / pytest (Python) — unit testing frameworks.\n"
    "- SonarQube — code quality and static analysis.\n"
    "- Selenium — automated UI testing.\n\n"
    "🐋 DevOps & Cloud:\n"
    "- Docker + Docker Compose — containerisation.\n"
    "- Kubernetes basics — container orchestration.\n"
    "- AWS or Azure Free Tier — cloud deployment practice.\n\n"
    "🎨 Design:\n"
    "- Figma — UI/UX prototyping and wireframing.\n"
    "- UML tools (draw.io, StarUML) — architecture diagrams.\n\n"
    "🗄️ Databases:\n"
    "- SQL Server / PostgreSQL — relational databases.\n"
    "- MongoDB — NoSQL basics.\n\n"
    "📋 Project Management:\n"
    "- Jira or Trello — agile sprint tracking.\n"
    "- Confluence — documentation."
)

TOOLS_AI_RESPONSE = (
    "Essential tools for Artificial Intelligence (AI) students:\n\n"
    "🐍 Core Python Stack:\n"
    "- Python — the primary language for all AI work.\n"
    "- NumPy + pandas — data manipulation fundamentals.\n"
    "- scikit-learn — classical ML (start here).\n"
    "- Matplotlib / Seaborn — visualisation.\n\n"
    "🧠 Deep Learning:\n"
    "- PyTorch — preferred for research and flexibility.\n"
    "- TensorFlow / Keras — alternative, more deployment-friendly.\n"
    "- Google Colab / Kaggle — free GPU notebooks.\n\n"
    "🗣️ NLP:\n"
    "- HuggingFace Transformers — BERT, GPT, and modern NLP models.\n"
    "- NLTK / spaCy — classic NLP preprocessing.\n"
    "- LangChain — for building LLM-powered applications.\n\n"
    "🤖 Robotics:\n"
    "- ROS2 — Robot Operating System (AI354 / AI404).\n"
    "- Gazebo — robot simulation environment.\n\n"
    "🥽 VR/AR:\n"
    "- Unity + C# — VR/AR development (AI403).\n\n"
    "🧩 Reasoning & Agents:\n"
    "- Prolog — logic programming (AI303).\n"
    "- OpenAI Gym / Gymnasium — reinforcement learning environments.\n\n"
    "🗂️ Version Control:\n"
    "- Git + GitHub — mandatory for all projects.\n"
    "- MLflow — experiment tracking and model versioning."
)

TOOLS_CLARIFICATION_RESPONSE = (
    "Which specialisation do you want tools for: CS, AI, Cyber Security, "
    "ISDS/Data Science, or Software Engineering?"
)

STUDENT_AFFAIRS_EN_FALLBACK = (
    "I don't have enough information about that topic.\n"
    "For further help, please visit the Student Affairs office at FCI.\n"
    "📍 Faculty of Computers & Information, Sadat Academy, Maadi Campus."
)
STUDENT_AFFAIRS_AR_FALLBACK = (
    "لا تتوفر لديّ معلومات كافية عن هذا الموضوع.\n"
    "للمزيد من المساعدة، يُرجى التوجه إلى مكتب شؤون الطلاب في كلية "
    "الحاسبات والمعلومات — سيكونون سعداء بمساعدتك.\n"
    "📍 كلية الحاسبات والمعلومات، أكاديمية السادات، فرع المعادي."
)

GREETING_EN_RESPONSE = (
    "Hey! 👋 I'm BuddyBot, FCI's campus assistant at Sadat Academy.\n"
    "Ask me about students, GPA, courses, schedules, instructors,\n"
    "FCI policies, official documents, or any campus service.\n"
    "Arabic or English — your choice!"
)

GREETING_AR_RESPONSE = (
    "أهلاً وسهلاً! 👋 أنا BuddyBot، مساعدك في كلية الحاسبات والمعلومات.\n"
    "ممكن أساعدك في:\n"
    "🎓 بيانات الطلاب والمعدلات\n"
    "📚 المقررات الدراسية وأعضاء هيئة التدريس\n"
    "🗓️ الجداول الدراسية والقاعات\n"
    "📋 لوائح الكلية (غياب، إنذار، امتحانات)\n"
    "📄 الأوراق الرسمية (إثبات قيد، تجنيد، ترانسكريبت)\n"
    "🏫 الأنشطة الطلابية والخدمات\n"
    "اسألني أي حاجة!"
)

GREETING_RESPONSE = GREETING_EN_RESPONSE

BOT_IDENTITY_RESPONSE = (
    "I'm BuddyBot 🤖 — FCI's campus assistant at Sadat Academy, Maadi.\n"
    "I can help you with:\n"
    "- 🎓 Student profiles and GPA\n"
    "- 📚 Course info and instructors\n"
    "- 🗓️ Class schedules and rooms\n"
    "- 📋 FCI policies (attendance, warnings, exams)\n"
    "- 📄 Official documents (enrollment cert, transcripts, etc.)\n"
    "- 🏫 Campus services and activities\n"
    "- 🇪🇬 Arabic or English — your choice!\n"
    "Just ask me anything."
)

THANKS_EN_RESPONSE = (
    "You're welcome! Let me know if there's anything else I can help with."
)

THANKS_AR_RESPONSE = (
    "العفو! 😊 أنا هنا لو احتجت أي حاجة تانية."
)

QUESTION_OPENER_EN_RESPONSE = "Of course! Go ahead - what's your question? 😊"
QUESTION_OPENER_AR_RESPONSE = "أكيد! اتفضل - اسأل براحتك 😊"

STATUS_EN_RESPONSE = (
    "I'm doing great, thanks for asking! 😊\n"
    "What can I help you with today?"
)
STATUS_AR_RESPONSE = "تمام والحمد لله! 😊 بخدمتك - اسأل براحتك."

ABUSE_EN_RESPONSE = (
    "I'm here to help with FCI-related questions. 😊\n"
    "Let me know if you need anything about courses, students, schedules, or campus policies."
)
ABUSE_AR_RESPONSE = (
    "أنا هنا لمساعدتك في أسئلة كلية الحاسبات والمعلومات. 😊\n"
    "اسألني عن أي حاجة تخص الكلية."
)

CLOSING_RESPONSE = (
    "Alright, we can stop here. I'll be ready whenever you want to check another student, "
    "calculation, or campus-service question."
)

CLARIFY_RESPONSE = (
    "I didn't catch that clearly. Try asking for a student ID, an average or percentage, "
    "a comparison, or a campus-service question."
)

GENERAL_CHAT_FALLBACK_RESPONSE = (
    "I can chat normally too. Tell me what you need help with: studying, planning, "
    "motivation, stress, campus life, or a student-data question."
)

EMOTIONAL_SUPPORT_EN_RESPONSE = (
    "💙 I hear you, and what you're feeling is completely valid.\n"
    "University can be genuinely hard, and feeling this way does not mean you're weak or failing.\n\n"
    "Right now, try this:\n"
    "- Stop and breathe. Not everything needs to be solved today.\n"
    "- Talk to someone you trust: a friend, family member, or professor.\n"
    "- Step outside for 15 minutes if you can. It genuinely helps.\n\n"
    "If it feels bigger than you can handle alone, Student Affairs can guide you to support services.\n"
    "📍 FCI, Sadat Academy, Maadi Campus.\n\n"
    "What's specifically bothering you? Tell me more and I'll do my best to help. 😊"
)

EMOTIONAL_SUPPORT_AR_RESPONSE = (
    "💙 سامعك، وده طبيعي جداً إنك تحس كده.\n"
    "الدراسة صعبة، ومش معناها إنك ضعيف أو فاشل.\n\n"
    "دلوقتي جرّب:\n"
    "- وقف شوية. مش لازم تحل كل حاجة دلوقتي.\n"
    "- كلم حد بتثق فيه: صاحب، أهل، أو دكتور في الكلية.\n"
    "- خد نفس واطلع 15 دقيقة بره لو تقدر.\n\n"
    "لو حاسس إن الموضوع أكبر من كده، مكتب شؤون الطلاب ممكن يساعدك تلاقي دعم.\n"
    "📍 كلية الحاسبات والمعلومات، أكاديمية السادات، المعادي.\n\n"
    "إيه اللي بيضايقك بالظبط؟ ممكن أساعدك أكتر. 😊"
)

WASTING_TIME_EN_RESPONSE = (
    "⏰ Feeling like you're wasting time is one of the most common student struggles. You're not alone.\n\n"
    "Try this right now:\n"
    "1. Write down just 3 things you want to finish today.\n"
    "2. Start with the smallest one, even if it takes only 2 minutes.\n"
    "3. Put your phone in another room for one focused hour.\n\n"
    "Pomodoro helps a lot: 25 minutes focus, then 5 minutes break. After 4 rounds, take a longer break.\n"
    "Want me to help you build a study plan for this week? 😊"
)

WASTING_TIME_AR_RESPONSE = (
    "⏰ إحساس إنك بتضيّع وقتك ده من أكتر الحاجات اللي بتضايق طلاب الجامعة، وانت مش لوحدك.\n\n"
    "جرّب دلوقتي:\n"
    "1. اكتب 3 حاجات بس عايز تخلصهم النهارده.\n"
    "2. ابدأ بأصغر واحدة فيهم، حتى لو دقيقتين.\n"
    "3. شيل التليفون بره الأوضة ساعة واحدة بس.\n\n"
    "تقنية Pomodoro بتساعد جداً: 25 دقيقة تركيز، بعدها 5 دقايق راحة.\n"
    "عايز أساعدك تعمل خطة دراسة للأسبوع ده؟ 😊"
)

HELP_EN_RESPONSE = (
    "I'm here! 😊 Tell me exactly what you need help with:\n\n"
    "- 📋 FCI policies: absence, warnings, fees, major change\n"
    "- 📚 Courses and instructors\n"
    "- 🎓 Student profiles and GPA\n"
    "- 🗓️ Class schedules\n"
    "- 📄 Official documents: enrollment certificates, transcripts\n"
    "- 💼 Career advice: CV, internships, job search\n"
    "- 📖 Study advice: techniques, time management, stress\n"
    "- 🏫 Campus services and activities\n\n"
    "Tell me what's on your mind and I'll help. 💙"
)

HELP_AR_RESPONSE = (
    "أنا هنا! 😊 قولي بالظبط عايز مساعدة في إيه:\n\n"
    "- 📋 سياسات الكلية: غياب، إنذار، رسوم، تغيير تخصص\n"
    "- 📚 المقررات والدكاترة\n"
    "- 🎓 بيانات الطلاب والمعدلات\n"
    "- 🗓️ الجداول الدراسية\n"
    "- 📄 الأوراق الرسمية: إثبات قيد، تجنيد، ترانسكريبت\n"
    "- 💼 نصائح مهنية: CV، تدريب، شغل\n"
    "- 📖 نصائح دراسية: مذاكرة، تنظيم وقت، ضغط\n"
    "- 🏫 خدمات وأنشطة الكلية\n\n"
    "قولي إيه اللي بيضايقك وهساعدك. 💙"
)

TYPO_NORMALIZATIONS = {
    "analuze": "analyze",
    "analize": "analyze",
    "departmant": "department",
    "departmnt": "department",
    "converstion": "conversation",
    "converstation": "conversation",
    "convo": "conversation",
    "advie": "advice",
    "advicee": "advice",
    "studnet": "student",
    "studnets": "students",
    "srudent": "student",
    "srudents": "students",
    "sutdent": "student",
    "sutdents": "students",
    "studetn": "student",
    "studetns": "students",
    "studentss": "students",
    "teahces": "teaches",
    "teahce": "teach",
    "teches": "teaches",
    "taeches": "teaches",
    "shwo": "show",
    "sohw": "show",
    "scool": "school",
    "rised": "improved",
    "imporved": "improved",
    "assisstant": "assistant",
    "avarage": "average",
    "avrage": "average",
    "avearge": "average",
    "avergae": "average",
    "averge": "average",
    "attendace": "attendance",
    "attendence": "attendance",
    "attandance": "attendance",
    "waht": "what",
    "taht": "that",
    "thatss": "that's",
    "that'ss": "that's",
    "calcuation": "calculation",
    "calcuations": "calculations",
    "calulation": "calculation",
    "manay": "many",
    "sciencs": "science",
    "scienc": "science",
    "scinece": "science",
    "enginering": "engineering",
    "softwar": "software",
    "securty": "security",
    "abbout": "about",
    "everthing": "everything",
    "calc": "calculate",
    "em": "me",
    "od": "of",
    "ne": "me",
}


def get_connection(retries: int = 3):
    last_error = None
    for attempt in range(max(retries, 1)):
        try:
            if DB_URL:
                if DB_URL.startswith(("postgres://", "postgresql://")):
                    if psycopg2 is None:
                        raise RuntimeError("psycopg2 is required for PostgreSQL/Supabase connections.")
                    return psycopg2.connect(DB_URL, sslmode=DB_SSLMODE, connect_timeout=10)
                if pyodbc is None:
                    raise RuntimeError("pyodbc is required for SQL Server connections.")
                return pyodbc.connect(DB_URL, timeout=10)

            if DB_DIALECT in {"postgres", "postgresql", "supabase"}:
                if psycopg2 is None:
                    raise RuntimeError("psycopg2 is required for PostgreSQL/Supabase connections.")
                return psycopg2.connect(
                    host=DB_SERVER,
                    database=DB_NAME,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    port=int(DB_PORT or 5432),
                    sslmode=DB_SSLMODE,
                    connect_timeout=10,
                )

            if pyodbc is None:
                raise RuntimeError("pyodbc is required for SQL Server connections.")
            return pyodbc.connect(
                f"DRIVER={{{DB_DRIVER}}};"
                f"SERVER={DB_SERVER};"
                f"DATABASE={DB_NAME};"
                "Trusted_Connection=yes;"
                "Encrypt=no;"
                "TrustServerCertificate=yes;",
                timeout=10,
            )
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(1)
    raise last_error


def safe_query(query: str, params: Optional[Sequence[Any]] = None) -> Optional[List[Any]]:
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.fetchall()
    except Exception as exc:
        print(f"Database error: {exc}", file=sys.stderr)
        return None
    finally:
        if conn:
            conn.close()


def postgres_mode() -> bool:
    if DB_URL and DB_URL.startswith(("postgres://", "postgresql://")):
        return True
    return DB_DIALECT in {"postgres", "postgresql", "supabase"}


def adapt_sql_for_configured_database(sql: str) -> str:
    if not postgres_mode():
        return sql

    adapted = sql.strip().rstrip(";")
    adapted = re.sub(
        r"(?is)CONVERT\s*\(\s*VARCHAR\s*\(\s*5\s*\)\s*,\s*([a-z_][a-z0-9_\.]*)\s*,\s*108\s*\)",
        r"TO_CHAR(\1, 'HH24:MI')",
        adapted,
    )

    top_match = re.match(r"(?is)^\s*SELECT\s+(DISTINCT\s+)?TOP\s*\(?\s*(\d+)\s*\)?\s+(.*)$", adapted)
    if top_match and not re.search(r"(?is)\bLIMIT\s+\d+\s*$", adapted):
        distinct = top_match.group(1) or ""
        adapted = f"SELECT {distinct}{top_match.group(3).strip()} LIMIT {top_match.group(2)}"

    adapted = re.sub(r"\bLEN\s*\(", "LENGTH(", adapted, flags=re.IGNORECASE)
    adapted = re.sub(r"\bISNULL\s*\(", "COALESCE(", adapted, flags=re.IGNORECASE)
    adapted = re.sub(r"\bGETDATE\s*\(\s*\)", "CURRENT_DATE", adapted, flags=re.IGNORECASE)
    adapted = adapted.replace("[", "").replace("]", "")
    return adapted


CANONICAL_COLUMN_NAMES = {
    "studentid": "StudentID",
    "student_id": "StudentID",
    "fullname": "FullName",
    "full_name": "FullName",
    "email": "Email",
    "currentyear": "CurrentYear",
    "current_year": "CurrentYear",
    "currentsemester": "CurrentSemester",
    "current_semester": "CurrentSemester",
    "groupcode": "GroupCode",
    "group_code": "GroupCode",
    "departmentcode": "DepartmentCode",
    "deptcode": "DepartmentCode",
    "dept_code": "DepartmentCode",
    "departmentname": "DepartmentName",
    "deptname": "DepartmentName",
    "dept_name": "DepartmentName",
    "status": "Status",
    "academic_year": "AcademicYear",
    "academicyear": "AcademicYear",
    "semester": "Semester",
    "semestergpa": "SemesterGPA",
    "semester_gpa": "SemesterGPA",
    "cumulativegpa": "CumulativeGPA",
    "cumulative_gpa": "CumulativeGPA",
    "thirdyearcumulativegpa": "ThirdYearCumulativeGPA",
    "third_year_cumulative_gpa": "ThirdYearCumulativeGPA",
    "coursecode": "CourseCode",
    "course_code": "CourseCode",
    "coursename": "CourseName",
    "course_name": "CourseName",
    "credithours": "CreditHours",
    "credit_hours": "CreditHours",
    "instructor": "Instructor",
    "instructorid": "InstructorID",
    "instructor_id": "InstructorID",
    "instructortitle": "InstructorTitle",
    "instructor_title": "InstructorTitle",
    "instructorname": "InstructorName",
    "instructor_name": "InstructorName",
    "room": "Room",
    "roomtype": "RoomType",
    "room_type": "RoomType",
    "roomname": "RoomName",
    "room_name": "RoomName",
    "day": "Day",
    "dayofweek": "DayOfWeek",
    "day_of_week": "DayOfWeek",
    "start": "Start",
    "starttime": "StartTime",
    "start_time": "StartTime",
    "end": "End",
    "endtime": "EndTime",
    "end_time": "EndTime",
    "sectiontype": "SectionType",
    "section_type": "SectionType",
    "targetgroup": "TargetGroup",
    "target_group": "TargetGroup",
}


def cursor_column_names(cursor: Any) -> List[str]:
    if not cursor.description:
        return []
    columns = [column[0] for column in cursor.description]
    if not postgres_mode():
        return columns
    return [CANONICAL_COLUMN_NAMES.get(str(column).lower(), column) for column in columns]


def call_ollama(prompt: str, timeout: int = 180) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json().get("response", "").strip()


ARABIC_DEPARTMENT_ANSWERS = {
    "cs": (
        "قسم علوم الحاسب (CS) يركز على أساسيات علم الحاسب وبناء الأنظمة: "
        "الخوارزميات، هياكل البيانات، أنظمة التشغيل، الشبكات، أمن الحاسب، "
        "الرسوميات، الرؤية الحاسوبية، والحوسبة السحابية. يؤهل القسم الطلاب "
        "للعمل في تطوير البرمجيات، هندسة الأنظمة، البحث العلمي، والدراسات العليا."
    ),
    "ai": (
        "قسم الذكاء الاصطناعي (AI) يركز على بناء أنظمة ذكية قادرة على التعلم "
        "والاستنتاج والإدراك. يدرس الطالب تعلم الآلة، التعلم العميق، معالجة "
        "اللغة الطبيعية، الروبوتات، الأنظمة متعددة الوكلاء، والواقع الافتراضي "
        "والمعزز."
    ),
    "cscs": (
        "قسم الأمن السيبراني (CSCS) يركز على حماية الأنظمة والشبكات والبيانات "
        "من الهجمات الرقمية. يشمل التخصص التشفير، اختبار الاختراق، الأدلة "
        "الجنائية الرقمية، إدارة المخاطر، أمن الشبكات، أمن السحابة، وأمن إنترنت الأشياء."
    ),
    "isds": (
        "قسم نظم المعلومات وعلوم البيانات (ISDS) يربط بين علوم الحاسب والإحصاء "
        "وذكاء الأعمال. يدرس الطالب جمع البيانات وتخزينها وتحليلها وتصويرها، "
        "إلى جانب تعلم الآلة، التنقيب عن البيانات، البيانات الضخمة، وسلاسل الكتل."
    ),
    "se": (
        "قسم هندسة البرمجيات (SE) يركز على بناء البرمجيات بشكل احترافي وعلى نطاق "
        "واسع. يدرس الطالب تحليل المتطلبات، تصميم المعمارية، اختبار البرمجيات، "
        "ضمان الجودة، إدارة المشروعات، الحوسبة السحابية، وتطبيقات إنترنت الأشياء."
    ),
}


ARABIC_POLICY_ANSWERS: Sequence[Dict[str, Any]] = [
    {
        "triggers": ["الخلفية التاريخية", "مبررات انشاء الكلية", "تاريخ الكلية", "لماذا انشيت الكلية"],
        "answer": (
            "بدأ تدريس تخصصات الحاسب الآلي ونظم المعلومات في أكاديمية السادات منذ سنوات التأسيس، "
            "استجابةً للحاجة المتنامية في السوق المصري والعربي إلى متخصصين في علوم الحاسب وتقنية "
            "المعلومات. وقد أُنشئت كلية الحاسبات والمعلومات رسمياً لتوحيد هذه البرامج تحت مظلة "
            "أكاديمية وبحثية متكاملة، تهدف إلى إعداد كوادر بشرية متميزة تُسهم في التنمية الرقمية "
            "للمجتمع المصري وتواكب متطلبات سوق العمل محلياً وإقليمياً وعالمياً."
        ),
    },
    {
        "triggers": [
            "رؤية ورسالة واهداف",
            "رؤية و رسالة و اهداف",
            "روية ورسالة واهداف",
            "روية و رسالة و اهداف",
            "رؤية ورسالة",
            "رؤية و رسالة",
            "رؤية الكلية",
            "رسالة الكلية",
            "اهداف الكلية",
            "روية ورسالة",
            "روية و رسالة",
        ],
        "answer": (
            "رؤية الكلية:\n"
            "تتطلع كلية الحاسبات والمعلومات إلى الارتقاء بالمستوى العلمي والتطبيقي والبحثي في "
            "مجالات علوم الحاسب ونظم المعلومات وهندسة البرمجيات، لتحقيق مكانة مرموقة بين كليات "
            "الحاسبات والمعلومات محلياً وإقليمياً وعالمياً، مع الالتزام بأخلاقيات المهنة وتنمية "
            "المجتمع المصري معلوماتياً.\n\n"
            "رسالة الكلية:\n"
            "تسعى الكلية لتقديم مستوى تعليمي وبحثي متميز في علوم الحاسب ونظم المعلومات وهندسة "
            "البرمجيات، وإعداد خريجين مؤهلين قادرين على المنافسة محلياً وعالمياً.\n\n"
            "أهداف الكلية:\n"
            "- إعداد متخصصين بمهارات نظرية وتطبيقية في علوم الحاسب ونظم المعلومات.\n"
            "- إجراء البحوث العلمية والتطبيقية في مجالات الحاسب والمعلومات وهندسة البرمجيات.\n"
            "- تقديم الاستشارات العلمية والتقنية.\n"
            "- تدريب الكوادر التقنية في قطاعات الدولة.\n"
            "- رفع الوعي المجتمعي بتكنولوجيا المعلومات.\n"
            "- عقد المؤتمرات والاجتماعات العلمية.\n"
            "- إبرام الاتفاقيات العلمية مع المؤسسات المحلية والإقليمية والدولية.\n"
            "- دعم النشر العلمي وإنشاء وحدات بحثية متخصصة."
        ),
    },
    {
        "triggers": [
            "الاقسام العلمية",
            "الاقسام",
            "التخصصات",
            "الدرجات العلمية",
            "اقسام الكلية",
            "تخصصات الكلية",
            "قسم علوم الحاسب",
            "قسم نظم المعلومات",
            "قسم هندسة البرمجيات",
        ],
        "answer": (
            "تمنح كلية الحاسبات والمعلومات درجة البكالوريوس في خمسة تخصصات:\n"
            "- علوم الحاسب (Computer Sciences) - CS\n"
            "- الذكاء الاصطناعي (Artificial Intelligence) - AI\n"
            "- الأمن السيبراني (Cyber Security) - CSCS\n"
            "- نظم المعلومات وعلوم البيانات (Information Systems & Data Science) - ISDS\n"
            "- هندسة البرمجيات (Software Engineering) - SE\n\n"
            "يقضي الطالب السنتين الأولى والثانية في دراسة مقررات مشتركة لجميع التخصصات، ثم يختار "
            "تخصصه عند انتقاله للسنة الثالثة. الدراسة باللغة الإنجليزية لجميع المقررات التخصصية."
        ),
    },
    {
        "triggers": ["نظام الدراسة", "اسلوب الدراسة", "كيف الدراسة"],
        "answer": (
            "تعتمد الكلية نظام الساعات المعتمدة (Credit Hours System). تنقسم السنة الدراسية إلى "
            "فصلين دراسيين، ومدة الدراسة أربع سنوات (8 فصول دراسية). يدرس الطالب في السنتين "
            "الأولى والثانية مقررات مشتركة لجميع التخصصات، ثم يدرس في السنتين الثالثة والرابعة "
            "مقررات التخصص الذي يختاره. الدراسة باللغة الإنجليزية لجميع المقررات التخصصية."
        ),
    },
    {
        "triggers": [
            "نظام الساعات المعتمدة",
            "نظام الساعات",
            "نظان الساعات",
            "ساعات معتمدة",
            "كام ساعة للتخرج",
            "ساعات التخرج",
            "credit hours",
            "144 ساعة",
        ],
        "answer": (
            "نظام الساعات المعتمدة في FCI:\n"
            "- إجمالي ساعات التخرج: 144 ساعة معتمدة.\n"
            "- توزيع المستويات الأكاديمية:\n"
            "  - المستوى الأول (السنة الأولى):   1 – 36 ساعة منجزة.\n"
            "  - المستوى الثاني (السنة الثانية): 37 – 72 ساعة منجزة.\n"
            "  - المستوى الثالث (السنة الثالثة): 73 – 108 ساعة منجزة.\n"
            "  - المستوى الرابع (السنة الرابعة): 109 – 144 ساعة منجزة.\n"
            "- الحد الأدنى للتسجيل في الفصل الاعتيادي: 15 ساعة معتمدة.\n"
            "- الحد الأقصى: 18 ساعة (يُرفع إلى 21 بموافقة الكلية لمن معدله ≥ 3.0).\n"
            "- الدراسة باللغة الإنجليزية لجميع المقررات التخصصية."
        ),
    },
    {
        "triggers": ["شروط الالتحاق", "شروط القبول", "قواعد القبول", "قواعد واحكام القبول", "كيف ادخل الكلية", "شروط الدخول"],
        "answer": (
            "شروط الالتحاق بكلية الحاسبات والمعلومات:\n"
            "- اجتياز الثانوية العامة بقسم علمي (رياضيات أو علوم) أو ما يعادلها.\n"
            "- استيفاء الحد الأدنى للدرجات المقرر من الكلية.\n"
            "- اجتياز إجراءات التقديم والقبول في المواعيد المحددة.\n"
            "- القبول في حدود الطاقة الاستيعابية المتاحة."
        ),
    },
    {
        "triggers": ["الاوراق المطلوبة", "الأوراق المطلوبة", "طلبات القبول", "وثائق القبول", "ما المطلوب للتقديم", "اوراق الالتحاق"],
        "answer": (
            "الأوراق المطلوبة للالتحاق بكلية الحاسبات والمعلومات:\n"
            "- صورة من شهادة الثانوية العامة أو ما يعادلها (مع الأصل للاطلاع).\n"
            "- صورة من شهادة الميلاد (مع الأصل للاطلاع).\n"
            "- صورة بطاقة الرقم القومي.\n"
            "- 6 صور شخصية حديثة.\n"
            "- بيان قيد للطلاب المحوَّلين من كليات أخرى.\n"
            "تُقدَّم جميع الأوراق إلى إدارة شؤون الطلاب بالكلية، ويجب إحضار أصول جميع الأوراق "
            "عند القبول النهائي."
        ),
    },
    {
        "triggers": ["الارشاد والتسجيل", "الارشاد و التسجيل", "الارشاد الاكاديمي", "خطة الدراسة", "التسجيل", "المرشد الاكاديمي"],
        "answer": (
            "الإرشاد الأكاديمي:\n"
            "المرشدون الأكاديميون هم أعضاء هيئة التدريس ومعاونوهم المخصَّصون من الكلية لتوجيه "
            "الطلاب في اختيار المواد الدراسية اللازمة للحصول على الدرجة العلمية، وذلك قبل فترة "
            "التسجيل في كل فصل دراسي.\n\n"
            "التسجيل:\n"
            "يضع وكيل الكلية لشؤون التعليم والطلاب خطة التسجيل وإجراءاته قبل كل فصل. على الطالب "
            "مراجعة مرشده الأكاديمي وتسجيل المواد في المواعيد المحددة. الحد الأدنى للتسجيل في "
            "الفصل الاعتيادي 15 ساعة معتمدة، والحد الأقصى 18 ساعة معتمدة، ويُرفع إلى 21 بموافقة "
            "الكلية لمن معدله التراكمي 3.0 فأكثر."
        ),
    },
    {
        "triggers": ["العبء الدراسي", "كم ساعة اسجل", "ساعات التسجيل", "الحد الادني للساعات", "الحد الاقصي للساعات"],
        "answer": (
            "العبء الدراسي في الفصل الاعتيادي:\n"
            "- الحد الأدنى: 15 ساعة معتمدة.\n"
            "- الحد الأقصى: 18 ساعة معتمدة.\n"
            "- يمكن رفع الحد الأقصى إلى 21 ساعة بموافقة الكلية للطلاب الذين يبلغ معدلهم التراكمي 3.0 فأكثر.\n"
            "- في حالة الإنذار الأكاديمي لا يتجاوز العبء 15 ساعة معتمدة."
        ),
    },
    {
        "triggers": ["الانسحاب والاضافة", "اضافة مادة", "حذف مادة", "الانسحاب من مادة", "اضافة وحذف"],
        "answer": (
            "يحق للطالب إضافة مقررات أو الانسحاب منها خلال الأسبوعين الأولين من بداية الفصل "
            "الدراسي وفق الإجراءات المقررة. الانسحاب بعد هذه المدة يُسجَّل كرسوب أو انسحاب في "
            "سجل الطالب ما لم يكن بعذر مقبول يوافق عليه مجلس الكلية. يجب ألا يقل العبء الدراسي "
            "بعد الحذف عن 15 ساعة معتمدة إلا بموافقة الكلية."
        ),
    },
    {
        "triggers": ["وقف التسجيل", "تجميد الدراسة", "ايقاف الدراسة", "الانقطاع عن الدراسة"],
        "answer": (
            "يجوز للطالب وقف تسجيله لمدة لا تتجاوز فصلين دراسيين متتاليين بعذر مقبول وبموافقة "
            "مجلس الكلية. لا تتجاوز مدة الوقف الإجمالية أربعة فصول دراسية طوال فترة الدراسة. "
            "يجب تقديم طلب وقف التسجيل قبل انتهاء فترة الانسحاب المعتمدة، ولا تُحتسب فترة الوقف "
            "ضمن الحد الأقصى لمدة الدراسة المسموح بها."
        ),
    },
    {
        "triggers": ["المواظبة", "الغياب", "انذار الغياب", "نسبة الغياب", "المواظبة وانذار الغياب"],
        "answer": (
            "نسبة الغياب المسموح بها هي 25% من إجمالي ساعات المقرر الدراسي. إذا تجاوز الطالب "
            "هذه النسبة:\n"
            "- يُحرَم من دخول الامتحان النهائي في ذلك المقرر.\n"
            "- يُسجَّل له رسوب تلقائياً في المقرر.\n"
            "يُنبَّه الطالب بإنذار غياب خطي قبل بلوغ الحد الأقصى لإتاحة الفرصة لتصحيح الوضع."
        ),
    },
    {
        "triggers": [
            "تغيير التخصص",
            "تحويل التخصص",
            "اغير تخصصي",
            "تغيير تخصصي",
            "كيف يمكنني تغيير تخصصي",
            "ازاي اغير تخصصي",
            "تحويل القسم",
            "تغيير القسم",
            "تغيير المسار",
            "التخصص",
        ],
        "answer": (
            "تغيير التخصص:\n"
            "- يُسمح بتغيير التخصص مرة واحدة فقط طوال فترة الدراسة.\n"
            "- لا يُسمح لطلاب السنة النهائية بتغيير التخصص.\n"
            "- يكون التغيير في حدود المقاعد الشاغرة في التخصص المطلوب.\n"
            "- تُقدَّم طلبات التغيير إلى عميد الكلية خلال الأسبوعين الأخيرين من الفصل الدراسي.\n"
            "- يحق للطالب التحويل إلى تخصص آخر داخل الكلية إذا كان ذلك يُحسِّن فرصته في إزالة "
            "الإنذار الأكاديمي، بموافقة وكيل الكلية."
        ),
    },
    {
        "triggers": ["الانذار الاكاديمي", "انذار اكاديمي", "الانذار", "المعدل منخفض"],
        "answer": (
            "الإنذار الأكاديمي:\n"
            "يُمنَح الطالب إنذاراً أكاديمياً إذا انخفض معدله التراكمي عن 2.0.\n"
            "- خلال الفصلين الدراسيين التاليين للإنذار يجب رفع المعدل التراكمي إلى 2.0 على الأقل.\n"
            "- يُقيَّد العبء الدراسي خلال فترة الإنذار بحد أقصى 15 ساعة معتمدة.\n"
            "- إذا لم يرفع الطالب معدله خلال المدة المحددة فقد يُفصَل من الكلية وفق قرار مجلس الكلية.\n"
            "- يجوز تحويل الطالب إلى تخصص آخر إذا كان ذلك يُحسِّن فرصته في رفع معدله، بموافقة وكيل الكلية."
        ),
    },
    {
        "triggers": ["الرسوب وتقدير", "الرسوب", "تقدير غير مكتمل", "رسبت في مادة", "غير مكتمل", "incomplete"],
        "answer": (
            "الرسوب:\n"
            "يُعتبَر الطالب راسباً في المقرر إذا حصل على تقدير F (صفر نقطة من 4.0). المقرر "
            "الراسب يُحتسَب في المعدل التراكمي ويجب إعادته لاحقاً.\n\n"
            "تقدير غير مكتمل (Incomplete):\n"
            "يُمنَح للطالب الذي لم يستكمل متطلبات المقرر بسبب ظروف طارئة أو عذر مقبول يوافق "
            "عليه مجلس الكلية. يجب على الطالب إزالة تقدير غير مكتمل خلال الفصل الدراسي التالي، "
            "وإذا لم يُزَل خلال المدة المحددة يتحوَّل تلقائياً إلى رسوب (F)."
        ),
    },
    {
        "triggers": ["التقويم", "المعدلات", "المعدل الفصلي", "المعدل التراكمي", "نظام التقييم", "الدرجات", "التقويم والمعدلات"],
        "answer": (
            "نظام التقييم (4.0 Scale):\n"
            "- A = 4.0: ممتاز\n"
            "- A- = 3.7: ممتاز ناقص\n"
            "- B+ = 3.5: جيد جداً+\n"
            "- B = 3.0: جيد جداً\n"
            "- B- = 2.7: جيد جداً ناقص\n"
            "- C+ = 2.5: جيد+\n"
            "- C = 2.0: جيد\n"
            "- D = 1.0: مقبول\n"
            "- F = 0.0: راسب\n"
            "المعدل الفصلي يُحسَب في نهاية كل فصل دراسي، والمعدل التراكمي يُحسَب على مجموع "
            "ساعات الدراسة الكلية. الحد الأدنى للنجاح والتخرج هو معدل تراكمي 2.0 على الأقل."
        ),
    },
    {
        "triggers": [
            "الرسوم الدراسية",
            "المصروفات",
            "المصاريف",
            "مصاريف",
            "فلوس الكلية",
            "كام المصاريف",
            "هدفع قد ايه",
            "رسوم الكلية",
            "كم الرسوم",
            "رد الرسوم",
            "fees",
        ],
        "answer": (
            "الرسوم الدراسية:\n"
            "تُحدَّد الرسوم الدراسية من قِبَل مجلس الأكاديمية العلمي.\n\n"
            "سياسة استرداد الرسوم عند الانسحاب:\n"
            "- الانسحاب خلال الأسبوع الأول من الفصل: يُردّ 100% من الرسوم.\n"
            "- الانسحاب بعد الأسبوع الأول وقبل مرور ثلاثة أسابيع: يُردّ 70%.\n"
            "- الانسحاب بعد ثلاثة أسابيع وقبل اختبارات منتصف الفصل: يُردّ 40%.\n"
            "- بعد اختبارات منتصف الفصل: لا يُردّ شيء من الرسوم.\n\n"
            "للاستفسار عن قيمة الرسوم الحالية، يُرجى التواصل مع إدارة شؤون الطلاب.\n"
            "📍 كلية الحاسبات والمعلومات، أكاديمية السادات، فرع المعادي."
        ),
    },
    {
        "triggers": ["نظام الامتحانات", "الامتحانات", "اعتماد النتائج", "موعد الامتحانات", "كيف الامتحانات"],
        "answer": (
            "نظام الامتحانات:\n"
            "- يُطبَّق نظام الامتحان الهجين (إلكتروني وتقليدي) وفقاً لطبيعة كل مقرر وقرارات المجلس الأعلى للجامعات.\n"
            "- يجوز لمجلس الكلية قرار عقد الامتحان إلكترونياً في مقرر أو أكثر.\n"
            "- تشمل الدرجة النهائية عادةً أعمال السنة وامتحان نصف الفصل وامتحان نهاية الفصل.\n\n"
            "اعتماد النتائج:\n"
            "- تُعتمَد النتائج من مجلس الكلية قبل إعلانها رسمياً.\n"
            "- في حال الاعتراض على نتيجة، يحق للطالب تقديم طلب مراجعة خلال المدة المحددة بعد إعلان النتائج.\n"
            "- مراجعة أوراق الإجابة تتم وفق الإجراءات الرسمية المقررة."
        ),
    },
    {
        "triggers": ["نظام تاديب الطلاب", "تاديب الطلاب", "العقوبات", "المخالفات", "الغش في الامتحانات"],
        "answer": (
            "نظام تأديب الطلاب:\n"
            "يسري على طلاب كلية الحاسبات والمعلومات قانون تنظيم الجامعات رقم 49 لسنة 1972 "
            "ولائحته التنفيذية فيما يخص نظام التأديب. العقوبات التأديبية تتدرج على النحو التالي:\n"
            "- الإنذار الشفهي أو الكتابي.\n"
            "- الحرمان من امتحان مقرر أو أكثر.\n"
            "- الفصل من الكلية لمدة محددة.\n"
            "- الفصل النهائي من الكلية في الحالات الجسيمة مثل الغش المتكرر.\n"
            "تُنظَر قضايا التأديب أمام مجلس تأديب الطلاب المختص."
        ),
    },
    {
        "triggers": ["احكام انتقالية", "احكام عامة", "احكام انتقالية وعامة"],
        "answer": (
            "تسري أحكام قانون تنظيم الجامعات رقم 49 لسنة 1972 ولائحته التنفيذية على كل ما لم "
            "يرد بشأنه نص خاص في لائحة الكلية. يختص مجلس الكلية بتفسير أحكام اللائحة والبت "
            "في الحالات الاستثنائية. الطلاب المنقولون من كليات أخرى تُحتسَب لهم الساعات "
            "المعتمدة المعادلة وفق قرار مجلس الكلية."
        ),
    },
    {
        "triggers": [
            "اثبات القيد",
            "اثبات قيد",
            "شهادة قيد",
            "بيان قيد",
            "قيد الكلية",
            "كيف اطلع اثبات قيد",
            "ازاي اطلع اثبات قيد",
            "enrollment",
            "enrollment certificate",
        ],
        "answer": (
            "إثبات القيد (شهادة تفيد بأنك طالب مقيد في الكلية):\n"
            "• تُستخرَج من مكتب شؤون الطلاب بكلية الحاسبات والمعلومات.\n"
            "• الأوراق المطلوبة: صورة بطاقة الرقم القومي + صورة بطاقة الطالب.\n"
            "• تُقدَّم طلباً كتابياً لشؤون الطلاب مع تحديد الغرض من الشهادة "
            "(تجنيد، سفارة، بنك، جهة عمل... إلخ).\n"
            "• مدة الاستخراج: عادةً من 1 إلى 3 أيام عمل.\n"
            "• تأكد من ذكر الغرض بوضوح في الطلب لأن الصياغة تختلف حسب الجهة.\n"
            "📍 مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، أكاديمية السادات، المعادي."
        ),
    },
    {
        "triggers": ["التجنيد", "تاجيل تجنيد", "تأجيل تجنيد", "شهادة تجنيد", "شهادة موقف تجنيد", "شهادة لغرض التجنيد", "دفاع"],
        "answer": (
            "شهادة تأجيل التجنيد أو موقف التجنيد:\n"
            "• تُستخرَج من مكتب شؤون الطلاب بالكلية.\n"
            "• الأوراق المطلوبة:\n"
            "  - صورة بطاقة الرقم القومي.\n"
            "  - صورة بطاقة الطالب الجامعية.\n"
            "  - أحياناً يُطلَب نموذج من مكتب التجنيد لتملأه الكلية.\n"
            "• يجب أن يكون الطالب مقيداً ومنتظماً في الدراسة.\n"
            "• يُجدَّد التأجيل كل عام دراسي طالما الطالب مقيد.\n"
            "• مدة الاستخراج: عادةً 1 إلى 3 أيام عمل.\n"
            "📍 مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، أكاديمية السادات، المعادي."
        ),
    },
    {
        "triggers": ["كشف درجات", "ترانسكريبت", "transcript", "سجل اكاديمي", "سجل أكاديمي", "نتائج الدراسة", "كشف المواد"],
        "answer": (
            "كشف الدرجات الرسمي (Transcript):\n"
            "• يُستخرَج من مكتب شؤون الطلاب أو من إدارة الشؤون الأكاديمية.\n"
            "• الأوراق المطلوبة: صورة بطاقة الرقم القومي + صورة بطاقة الطالب.\n"
            "• يُقدَّم طلب كتابي مع تحديد الغرض (تحويل، دراسات عليا، سفارة... إلخ).\n"
            "• الكشف يتضمن: اسم الطالب، رقمه الجامعي، التخصص، المواد المدروسة، "
            "درجة كل مادة، المعدل الفصلي والتراكمي.\n"
            "• مدة الاستخراج: من 3 إلى 5 أيام عمل.\n"
            "• قد يحتاج إلى توقيع وكيل الكلية وختم رسمي للجهات الخارجية.\n"
            "📍 مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، أكاديمية السادات، المعادي."
        ),
    },
    {
        "triggers": ["شهادة التخرج", "شهادة البكالوريوس", "الشهادة", "دبلوما", "graduation certificate", "degree certificate"],
        "answer": (
            "شهادة التخرج (درجة البكالوريوس في الحاسبات والمعلومات):\n"
            "• تُمنَح بعد استيفاء جميع متطلبات التخرج وإقرار النتيجة من مجلس الكلية.\n"
            "• للحصول على شهادة مؤقتة قبل صدور الشهادة الأصلية:\n"
            "  - تُقدَّم طلباً لشؤون الطلاب بعد إعلان النتيجة الرسمية.\n"
            "  - الأوراق: صورة بطاقة الرقم القومي + صورة بطاقة الطالب + صور شخصية.\n"
            "• الشهادة الأصلية تصدر عادةً بعد عدة أشهر من إعلان النتائج.\n"
            "• في حال فقدان الشهادة يمكن استخراج بدل فاقد بطلب رسمي.\n"
            "📍 مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، أكاديمية السادات، المعادي."
        ),
    },
    {
        "triggers": ["بدل فاقد", "ضاعت شهادتي", "فقدت الشهادة", "استخراج بدل", "وثيقة مفقودة"],
        "answer": (
            "استخراج بدل فاقد لوثيقة رسمية (شهادة، بطاقة، إلخ):\n"
            "• تُقدَّم طلباً رسمياً لشؤون الطلاب مع توضيح الوثيقة المفقودة.\n"
            "• الأوراق المطلوبة عادةً:\n"
            "  - محضر شرطة يُثبت الفقدان (من أقرب قسم شرطة).\n"
            "  - صورة بطاقة الرقم القومي.\n"
            "  - صور شخصية حديثة.\n"
            "  - طلب كتابي موجَّه لعميد الكلية.\n"
            "• تخضع لرسوم استخراج تُحدَّدها إدارة الأكاديمية.\n"
            "📍 مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، أكاديمية السادات، المعادي."
        ),
    },
    {
        "triggers": ["شهادة للسفارة", "شهادة سفر", "فيزا", "تاشيرة", "تأشيرة", "visa", "شهادة باللغة الانجليزية", "شهادة باللغة الإنجليزية", "شهادة مترجمة"],
        "answer": (
            "شهادة لغرض السفارة أو السفر:\n"
            "• تُقدَّم طلباً لشؤون الطلاب مع تحديد السفارة أو الجهة المطلوب منها.\n"
            "• يمكن استخراج شهادة قيد أو كشف درجات أو خطاب رسمي من الكلية "
            "باللغة العربية أو الإنجليزية حسب طلب السفارة.\n"
            "• إذا احتجت ترجمة رسمية معتمدة، يُنصَح بالتوجه إلى مكتب ترجمة "
            "معتمد بعد الحصول على الشهادة من الكلية.\n"
            "• مدة الاستخراج: 1 إلى 3 أيام عمل.\n"
            "📍 مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، أكاديمية السادات، المعادي."
        ),
    },
    {
        "triggers": ["اجازة دراسية", "إجازة دراسية", "خطاب لجهة العمل", "خطاب رسمي", "study leave", "employer letter"],
        "answer": (
            "خطاب رسمي للكلية (لجهة عمل أو إجازة دراسية):\n"
            "• تُقدَّم طلباً كتابياً لشؤون الطلاب مع توضيح الجهة المطلوب منها والغرض بالتفصيل.\n"
            "• يصدر الخطاب موقَّعاً من وكيل الكلية ومختوماً بالختم الرسمي.\n"
            "• مدة الاستخراج: 1 إلى 3 أيام عمل.\n"
            "📍 مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، أكاديمية السادات، المعادي."
        ),
    },
    {
        "triggers": ["اوراق رسمية", "أوراق رسمية", "مستندات رسمية", "استخراج وثيقة", "استخراج مستند", "وثائق رسمية"],
        "answer": (
            "الأوراق والوثائق الرسمية المتاحة من خلال شؤون الطلاب تشمل: إثبات القيد، "
            "شهادات التجنيد، كشف الدرجات، شهادة التخرج، بدل فاقد، وخطابات السفارة أو جهة العمل. "
            "لتحديد المطلوب بدقة، قدّم طلباً كتابياً في مكتب شؤون الطلاب مع صورة بطاقة الرقم القومي "
            "وصورة بطاقة الطالب، واذكر الغرض من الوثيقة بوضوح.\n"
            "📍 مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، أكاديمية السادات، المعادي."
        ),
    },
    {
        "triggers": [
            "تظلم",
            "اعتراض على النتيجة",
            "مراجعة ورقة الإجابة",
            "مراجعة ورقة الاجابة",
            "غلط في نتيجتي",
            "النتيجة غلط",
            "appeal",
            "grade appeal",
            "مراجعة الدرجة",
            "اعتراض على الدرجة",
            "تظلم من الامتحان",
        ],
        "answer": (
            "التظلم من نتيجة الامتحان:\n"
            "- يحق لأي طالب الاعتراض على نتيجته خلال المدة المحددة بعد إعلان النتائج الرسمية "
            "(عادةً أسبوعان).\n"
            "- خطوات التظلم:\n"
            "  1. تقديم طلب تظلم كتابي لشؤون الطلاب موضحاً فيه المادة والسبب.\n"
            "  2. سداد رسوم المراجعة المقررة، وتُحدَّد من إدارة الأكاديمية.\n"
            "  3. تُحال الورقة إلى لجنة مراجعة مستقلة من الكلية.\n"
            "  4. تُعلَن النتيجة النهائية للتظلم خلال المدة المقررة.\n"
            "- إذا ثبت وجود خطأ تُصحَّح الدرجة وتُعاد احتساب المعدل.\n"
            "- التظلم لا يضمن تغيير الدرجة؛ القرار يعود للجنة المراجعة.\n"
            "- بعد انتهاء مدة التظلم لا يُقبَل أي اعتراض.\n"
            "📍 مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، أكاديمية السادات، المعادي."
        ),
    },
    {
        "triggers": [
            "النتيجة",
            "نتيجتي",
            "امتى النتايج",
            "امتى النتائج",
            "نتائج الترم",
            "ظهرت النتيجة",
            "متى تظهر النتائج",
            "results",
            "كيف أعرف نتيجتي",
            "كيف اعرف نتيجتي",
            "اعرف نتيجتي",
            "موعد النتيجة",
        ],
        "answer": (
            "الاستعلام عن النتيجة:\n"
            "- تُعلَن النتائج رسمياً بعد اعتمادها من مجلس الكلية.\n"
            "- يمكن الاستعلام عن النتيجة عبر:\n"
            "  - الموقع الرسمي لأكاديمية السادات: www.sams.edu.eg\n"
            "  - بوابة الطالب الإلكترونية إن توفرت.\n"
            "  - مكتب شؤون الطلاب بالكلية مباشرةً.\n"
            "- إذا لم تظهر نتيجتك أو وجدت مادة ناقصة، راجع شؤون الطلاب فوراً قبل انتهاء مدة التظلم.\n"
            "- لا تنتظر؛ مدة التظلم محدودة وتنتهي بعد أسبوعين من الإعلان.\n"
            "📍 مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، أكاديمية السادات، المعادي."
        ),
    },
    {
        "triggers": [
            "دفع المصروفات",
            "سداد الرسوم",
            "دفع الرسوم",
            "فين أدفع",
            "فين ادفع",
            "طريقة الدفع",
            "اونلاين دفع",
            "أونلاين دفع",
            "pay fees",
            "payment",
            "موعد الدفع",
            "مواعيد سداد الرسوم",
            "تقسيط الرسوم",
        ],
        "answer": (
            "دفع المصروفات الدراسية:\n"
            "- يتم دفع الرسوم في المواعيد المحددة قبل أو خلال أسبوع بداية التسجيل في كل فصل دراسي.\n"
            "- طرق الدفع المتاحة:\n"
            "  - الدفع المباشر في إدارة الشؤون المالية بالكلية.\n"
            "  - التحويل البنكي على الحساب الرسمي للأكاديمية، ويُستفسَر عن رقم الحساب من الإدارة المالية.\n"
            "  - عبر البوابة الإلكترونية إن كانت متاحة.\n"
            "- احتفظ بإيصال الدفع؛ فهو مطلوب لإتمام التسجيل.\n"
            "- لا يُمكَّن الطالب من التسجيل في المواد إلا بعد سداد الرسوم.\n"
            "- سياسة استرداد الرسوم عند الانسحاب:\n"
            "  - خلال الأسبوع الأول: يُردّ 100%.\n"
            "  - بعد الأسبوع الأول وقبل 3 أسابيع: يُردّ 70%.\n"
            "  - بعد 3 أسابيع وقبل المنتصف: يُردّ 40%.\n"
            "  - بعد الامتحانات النصفية: لا يُردّ شيء.\n"
            "📍 الإدارة المالية / مكتب شؤون الطلاب — أكاديمية السادات، المعادي."
        ),
    },
    {
        "triggers": [
            "شكوى",
            "شكاوى",
            "كيف أقدم شكوى",
            "كيف اقدم شكوى",
            "عايز أشتكي",
            "عايز اشتكي",
            "أشتكي فين",
            "اشتكي فين",
            "مين أشتكي عنده",
            "مين اشتكي عنده",
            "فين أقدم شكوى",
            "فين اقدم شكوى",
            "complaint",
            "مشكلة مع دكتور",
            "مشكلة في الكلية",
            "بلاغ",
            "تقرير عن مشكلة",
        ],
        "answer": (
            "تقديم شكوى رسمية:\n"
            "- يحق لكل طالب تقديم شكوى رسمية بشأن أي مشكلة أكاديمية أو إدارية.\n"
            "- خطوات تقديم الشكوى:\n"
            "  1. اكتب الشكوى كتابةً واضحةً مع ذكر التفاصيل والأدلة إن وجدت.\n"
            "  2. قدِّمها إلى مكتب شؤون الطلاب أو مباشرةً إلى وكيل الكلية.\n"
            "  3. في الشكاوى الجسيمة يمكن رفعها إلى عميد الكلية.\n"
            "- أنواع الشكاوى الشائعة وجهة تقديمها:\n"
            "  - مشكلة مع أستاذ أو مادة → وكيل الكلية لشؤون التعليم.\n"
            "  - مشكلة إدارية أو مالية → مكتب شؤون الطلاب.\n"
            "  - مشكلة تتعلق بنتيجة امتحان → طلب تظلم رسمي.\n"
            "  - مشكلة تتعلق بانتهاك أو تحرش → عميد الكلية مباشرةً.\n"
            "- جميع الشكاوى سرية ولا يُتخَذ أي إجراء انتقامي ضد مقدِّمها.\n"
            "📍 مكتب شؤون الطلاب / وكيل الكلية — كلية الحاسبات والمعلومات، المعادي."
        ),
    },
    {
        "triggers": [
            "التربية العسكرية",
            "تدريب عسكري",
            "المعسكر",
            "military training",
            "الكشف الطبي العسكري",
            "إعفاء من التربية العسكرية",
            "اعفاء من التربية العسكرية",
            "رسوب في التربية العسكرية",
        ],
        "answer": (
            "التربية العسكرية:\n"
            "- التربية العسكرية مقرر إلزامي لجميع الطلاب الذكور في مرحلة معينة من الدراسة "
            "وفق قرارات وزارة التعليم العالي.\n"
            "- تشمل عادةً:\n"
            "  - تدريبات عملية في معسكرات مخصصة.\n"
            "  - محاضرات نظرية في الوعي الوطني والإسعافات الأولية.\n"
            "- الغياب عن التربية العسكرية يُعامَل مثل الغياب عن أي مقرر آخر، والحد الأقصى 25%.\n"
            "- الإعفاء يُمنَح في حالات طبية موثَّقة بقرار من الجهة الطبية المختصة بالتنسيق مع الكلية.\n"
            "- لأي استفسار عن المواعيد أو الكشف الطبي أو الإعفاء:\n"
            "📍 مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، أكاديمية السادات، المعادي."
        ),
    },
    {
        "triggers": [
            "الانشطة",
            "الأنشطة",
            "انشطة طلابية",
            "أنشطة طلابية",
            "student activities",
            "what are the activities",
            "what activities",
            "activities in fci",
            "clubs",
            "club",
            "what clubs",
            "extracurricular",
            "events in fci",
            "hackathon",
            "competitions",
            "المسرح",
            "فرقة مسرحية",
            "رياضة",
            "نادي",
            "اتحاد الطلاب",
            "كيف أنضم لنشاط",
            "كيف انضم لنشاط",
            "فعاليات",
            "حفلات",
            "مهرجانات",
            "رحلات",
            "كمبيتيشن",
            "competition",
        ],
        "answer": (
            "الأنشطة الطلابية في FCI:\n"
            "تتيح الكلية مجموعة من الأنشطة والفعاليات للطلاب خارج إطار الدراسة:\n\n"
            "الأنشطة الثقافية والفنية:\n"
            "- فرقة المسرح الجامعي: تمثيل وإخراج وكتابة.\n"
            "- الأنشطة الموسيقية والغنائية.\n"
            "- نادي الخطابة والمناظرات.\n\n"
            "الأنشطة الرياضية:\n"
            "- بطولات كرة القدم، كرة الطائرة، كرة السلة.\n"
            "- بطولات ألعاب الطاولة والشطرنج.\n\n"
            "الأنشطة التقنية والأكاديمية:\n"
            "- نوادي البرمجة والذكاء الاصطناعي.\n"
            "- مسابقات Hackathon وتطوير التطبيقات.\n"
            "- نادي الأمن السيبراني والـ CTF.\n\n"
            "الفعاليات والرحلات:\n"
            "- رحلات ترفيهية وثقافية.\n"
            "- مهرجانات وأيام مفتوحة.\n"
            "- معارض مشاريع التخرج.\n\n"
            "للانضمام لأي نشاط أو الاستعلام عن المواعيد:\n"
            "📍 مكتب اتحاد الطلاب / مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، المعادي."
        ),
    },
    {
        "triggers": [
            "تدريب",
            "انترنشيب",
            "إنترنشيب",
            "internship",
            "تدريب صيفي",
            "تدريب ميداني",
            "summer training",
            "شركة تدريب",
            "كيف أحصل على تدريب",
            "كيف احصل على تدريب",
            "رسالة تدريب",
            "خطاب تدريب",
            "توصية تدريب",
            "شهادة تدريب",
            "تدريب في شركة",
        ],
        "answer": (
            "التدريب الصيفي / التدريب الميداني (Internship):\n"
            "- التدريب الصيفي متاح وموصى به لطلاب السنة الثانية والثالثة والرابعة.\n"
            "- قد يكون التدريب إلزامياً في بعض الخطط الدراسية؛ تحقق من خطتك مع مرشدك الأكاديمي.\n\n"
            "خطوات الحصول على التدريب:\n"
            "1. ابحث عن شركة أو جهة تقبل المتدربين في مجال تخصصك.\n"
            "2. اطلب خطاب تدريب رسمي من شؤون الطلاب بالكلية يُعرِّف بك كطالب مقيد.\n"
            "3. قدِّم الخطاب للشركة مع سيرتك الذاتية.\n"
            "4. بعد انتهاء التدريب احضر شهادة إتمام التدريب وسلِّمها لشؤون الطلاب أو المرشد الأكاديمي.\n\n"
            "مصادر تساعدك في إيجاد تدريب:\n"
            "- LinkedIn: ابحث عن internships في مصر في مجالك.\n"
            "- منصة WUZZUF و Forasna.\n"
            "- مجموعات الكلية على Facebook وWhatsApp.\n"
            "- التواصل المباشر مع أعضاء هيئة التدريس؛ كثير منهم لديهم علاقات بشركات وجهات بحثية.\n\n"
            "📍 لخطاب التدريب الرسمي: مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، المعادي."
        ),
    },
    {
        "triggers": [
            "مشروع تخرج",
            "graduation project",
            "بروجكت",
            "مشروع السنة الرابعة",
            "كيف أختار موضوع مشروع",
            "كيف اختار موضوع مشروع",
            "تسليم المشروع",
            "مناقشة المشروع",
            "دكتور مشرف",
        ],
        "answer": (
            "مشروع التخرج:\n"
            "- مشروع التخرج إلزامي لجميع طلاب السنة الرابعة.\n"
            "- يمتد على فصلين دراسيين، الفصل السابع والثامن.\n"
            "- يُقيَّم عملياً وشفهياً أمام لجنة من أعضاء هيئة التدريس.\n"
            "- يحق للطالب طلب تمديد لا يتجاوز 4 أسابيع بعد الامتحانات الكتابية بموافقة مجلس الكلية.\n"
            "- خطوات مشروع التخرج:\n"
            "  1. اختيار الفكرة والدكتور المشرف في بداية السنة الرابعة.\n"
            "  2. تسجيل موضوع المشروع مع شؤون الطلاب أو القسم العلمي.\n"
            "  3. تسليم تقارير دورية للمشرف خلال الفصلين.\n"
            "  4. تسليم التقرير النهائي وعرض المشروع أمام اللجنة.\n"
            "- نصيحة: ابدأ مبكراً واختر موضوعاً في مجال تخصصك أو شيئاً يُضاف لسيرتك الذاتية.\n"
            "📍 للاستفسار: القسم العلمي / مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، المعادي."
        ),
    },
    {
        "triggers": [
            "دراسات عليا",
            "ماجستير",
            "دكتوراه",
            "masters",
            "phd",
            "postgraduate",
            "بعد التخرج",
            "دبلوم دراسات عليا",
        ],
        "answer": (
            "الدراسات العليا بعد التخرج:\n"
            "- تُتيح أكاديمية السادات برامج دراسات عليا في بعض التخصصات.\n"
            "- للالتحاق ببرنامج الماجستير أو الدكتوراه في الحاسبات أو الإدارة:\n"
            "  - التقديم يكون بعد الحصول على درجة البكالوريوس.\n"
            "  - تُحدَّد شروط القبول والمواعيد من إدارة الدراسات العليا.\n"
            "- للاستعلام عن البرامج المتاحة حالياً ومتطلباتها:\n"
            "📍 إدارة الدراسات العليا — أكاديمية السادات، المعادي.\n"
            "www.sams.edu.eg"
        ),
    },
    {
        "triggers": [
            "نصيحة",
            "استشارة",
            "مش عارف أختار",
            "مش عارف اختار",
            "أي تخصص أختار",
            "اي تخصص اختار",
            "academic advice",
            "study tips",
            "مشكلة في الدراسة",
            "مذاكرة",
            "كيف أنجح",
            "كيف انجح",
            "أنا ضعيف في",
            "انا ضعيف في",
        ],
        "answer": (
            "نصائح أكاديمية عامة لطلاب FCI:\n"
            "- راجع مرشدك الأكاديمي قبل كل فصل لضمان اختيار المواد الصحيحة.\n"
            "- لا تتجاوز نسبة الغياب 25% في أي مادة؛ الحرمان يضر معدلك.\n"
            "- إذا شعرت بصعوبة في مادة، راجع الدكتور في ساعات مكتبه مبكراً.\n"
            "- لاختيار التخصص:\n"
            "  - CS: إذا كنت تحب النظرية والأنظمة والخوارزميات.\n"
            "  - AI: إذا كنت تحب التعلم الآلي والروبوتات واللغات الطبيعية.\n"
            "  - CSCS: إذا كنت تحب الأمن والاختراق الأخلاقي والتشفير.\n"
            "  - ISDS: إذا كنت تحب البيانات والإحصاء وذكاء الأعمال.\n"
            "  - SE: إذا كنت تحب بناء البرمجيات بشكل محترف ومنظم.\n"
            "- إذا كان معدلك في خطر، راجع قسم شؤون الطلاب لمعرفة خياراتك قبل أن يتحول الوضع لإنذار أكاديمي.\n"
            "📍 مكتب شؤون الطلاب / مرشدك الأكاديمي — كلية الحاسبات والمعلومات، المعادي."
        ),
    },
]


def arabic_department_direct_answer(question: str) -> Optional[str]:
    lowered = semantic_normalize(question)
    department_triggers = [
        ("cs", ["قسم علوم الحاسب", "علوم الحاسب", "علوم الحاسوب"]),
        ("isds", ["قسم نظم المعلومات", "نظم المعلومات", "علوم البيانات"]),
        ("se", ["قسم هندسة البرمجيات", "هندسة البرمجيات"]),
        ("ai", ["الذكاء الاصطناعي", "قسم الذكاء الاصطناعي"]),
        ("cscs", ["الامن السيبراني", "الأمن السيبراني", "قسم الامن السيبراني", "قسم الأمن السيبراني"]),
    ]
    if any(term in lowered for term in ["الاقسام", "التخصصات", "الدرجات العلمية", "اقسام الكلية", "تخصصات الكلية"]):
        return None
    for code, triggers in department_triggers:
        if any(semantic_normalize(trigger) in lowered for trigger in triggers):
            return ARABIC_DEPARTMENT_ANSWERS.get(code)
    return None


def arabic_policy_direct_answer(question: str) -> Optional[str]:
    variants = arabic_match_variants(question)
    best_item: Optional[Dict[str, Any]] = None
    best_score = -1
    for item in ARABIC_POLICY_ANSWERS:
        for trigger in item["triggers"]:
            normalized_trigger = semantic_normalize(trigger)
            trigger_variant = arabic_typo_normalize(trigger)
            if not normalized_trigger:
                continue
            exact_match = any(normalized_trigger in variant or trigger_variant in variant for variant in variants)
            fuzzy_match = any(
                len(normalized_trigger) >= 5
                and abs(len(variant) - len(normalized_trigger)) <= 4
                and SequenceMatcher(None, normalized_trigger, variant).ratio() >= 0.86
                for variant in variants
            )
            if (exact_match or fuzzy_match) and len(normalized_trigger) > best_score:
                best_item = item
                best_score = len(normalized_trigger)
    if best_item:
        return append_arabic_official_followup(str(best_item["answer"]), question)
    department_answer = arabic_department_direct_answer(question)
    if department_answer:
        return department_answer
    return None


ARABIC_SPECIFIC_CORRECTIONS = {
    "الصاريف": "المصاريف",
    "المصاريق": "المصاريف",
    "الغيآب": "الغياب",
    "الغياب": "الغياب",
    "نظان": "نظام",
    "نضام": "نظام",
    "التخصس": "التخصص",
    "الامتحانت": "الامتحانات",
    "الانزار": "الانذار",
}


def arabic_typo_normalize(text: str) -> str:
    normalized = semantic_normalize(text)
    for wrong, right in ARABIC_SPECIFIC_CORRECTIONS.items():
        normalized = re.sub(rf"\b{re.escape(semantic_normalize(wrong))}\b", semantic_normalize(right), normalized)
    normalized = normalized.replace("ة", "ه")
    normalized = normalized.replace("ء", "ا")
    normalized = re.sub(r"\bنظان\b", "نظام", normalized)
    normalized = re.sub(r"\bنضام\b", "نظام", normalized)
    return normalized


def arabic_match_variants(text: str) -> set[str]:
    base = semantic_normalize(text).strip(" /؟?!.")
    typo = arabic_typo_normalize(text).strip(" /؟?!.")
    variants = {base, typo}
    if "نظان" in base:
        variants.add(base.replace("نظان", "نظام"))
    if "نضام" in base:
        variants.add(base.replace("نضام", "نظام"))
    return {variant for variant in variants if variant}


def tools_answer_for_department_text(text: str) -> Optional[str]:
    lowered = semantic_normalize(text)
    if text_has_any(lowered, ["data science", "isds", "information systems", "علوم البيانات", "نظم المعلومات"]) or re.search(r"\bds\b", lowered):
        return TOOLS_ISDS_RESPONSE
    if text_has_any(lowered, ["cyber security", "cybersecurity", "cscs", "cs security", "cyber", "الامن السيبراني", "الأمن السيبراني"]):
        return TOOLS_CSCS_RESPONSE
    if text_has_any(lowered, ["software engineering", "software", "هندسه البرمجيات", "هندسة البرمجيات"]) or re.search(r"\bse\b", lowered):
        return TOOLS_SE_RESPONSE
    if re.search(r"\b(?:ai|artificial intelligence)\b", lowered) or text_has_any(lowered, ["الذكاء الاصطناعي", "ذكاء اصطناعي"]):
        return TOOLS_AI_RESPONSE
    if re.search(r"\bcs\b", lowered) or text_has_any(lowered, ["computer science", "computer sciences", "علوم الحاسب"]):
        return TOOLS_CS_RESPONSE
    return None


def is_tools_topic_query(text: str) -> bool:
    lowered = semantic_normalize(text)
    return bool(
        re.search(r"\btools?\b", lowered)
        or text_has_any(
            lowered,
            [
                "recommended tools",
                "students learn",
                "ادوات",
                "أدوات",
            ],
        )
    )


def english_hardcoded_topic_answer(question: str) -> Optional[str]:
    lowered = semantic_normalize(question).strip(" /?!.")
    if is_tools_topic_query(question):
        tools_answer = tools_answer_for_department_text(question)
        if tools_answer:
            return tools_answer
    if fci_department_code_from_text(question) and looks_like_bare_fci_department_query(question):
        return None
    priority_policy_map: Sequence[tuple[Sequence[str], str]] = [
        (
            [
                "what is the absence policy at fci",
                "absence policy",
                "attendance policy",
                "how many absences",
                "25 percent rule",
                "25% rule",
            ],
            ABSENCE_POLICY_EN_RESPONSE,
        ),
        (
            [
                "what is an academic warning and how do i avoid it",
                "academic warning",
                "academic warnings",
                "gpa below 2",
                "academic probation",
                "student warnings",
            ],
            ACADEMIC_WARNING_EN_RESPONSE,
        ),
        (
            [
                "what is the tuition fee refund policy",
                "tuition fee refund policy",
                "tuition fees",
                "tuition fee",
                "refund policy",
                "fees refund",
                "fee refund",
            ],
            TUITION_FEES_EN_RESPONSE,
        ),
        (
            [
                "how can i change my specialisation",
                "how can i change my specialization",
                "change major",
                "change specialisation",
                "change specialization",
                "switch department",
                "switch major",
            ],
            CHANGE_MAJOR_EN_RESPONSE,
        ),
        (
            [
                "what is the add/drop policy",
                "add/drop policy",
                "add drop policy",
                "add and drop policy",
                "add/drop period",
                "add drop period",
                "course add/drop",
                "course add drop",
                "add a course",
                "add course",
                "drop a course",
                "drop course",
                "drop courses",
                "withdraw from a course",
                "withdraw from course",
                "course withdrawal",
                "withdrawal rules",
            ],
            ADD_DROP_EN_RESPONSE,
        ),
    ]
    for triggers, answer in priority_policy_map:
        if any(trigger in lowered for trigger in triggers):
            return answer
    extended_answer = extended_topic_answer(question)
    if extended_answer:
        return extended_answer
    topic_map: Sequence[tuple[Sequence[str], str]] = [
        (
            [
                "fci policies",
                "fci policy",
                "what are the policies",
                "academic policies",
                "college policies",
                "policies",
                "rules and regulations",
                "regulations",
                "fci rules",
            ],
            FCI_POLICY_SUMMARY_RESPONSE,
        ),
        (
            [
                "tools for data science",
                "data science tools",
                "what tools for isds",
                "isds tools",
                "what should isds students learn",
                "recommended tools data science",
            ],
            TOOLS_ISDS_RESPONSE,
        ),
        (
            [
                "tools for cyber security",
                "cyber security tools",
                "what tools for cscs",
                "cscs tools",
                "what should cyber security students learn",
            ],
            TOOLS_CSCS_RESPONSE,
        ),
        (
            [
                "tools for computer science",
                "cs tools",
                "what should cs students learn",
                "recommended tools cs",
            ],
            TOOLS_CS_RESPONSE,
        ),
        (
            [
                "tools for software engineering",
                "se tools",
                "what should se students learn",
                "recommended tools se",
            ],
            TOOLS_SE_RESPONSE,
        ),
        (
            [
                "tools for ai",
                "ai tools",
                "tools for artificial intelligence",
                "what should ai students learn",
                "recommended tools ai",
            ],
            TOOLS_AI_RESPONSE,
        ),
        (
            [
                "student activities",
                "student union",
                "what are the activities",
                "what activities",
                "activities in fci",
                "clubs",
                "club",
                "what clubs",
                "extracurricular",
                "events in fci",
                "hackathon",
                "competitions",
            ],
            ACTIVITIES_EN_RESPONSE,
        ),
        (
            [
                "student affairs",
                "student services",
                "student exchange",
                "student rights",
                "official services",
                "campus services",
            ],
            STUDENT_AFFAIRS_CONTACT_EN,
        ),
        (["student discipline", "discipline", "disciplinary"], DISCIPLINE_EN_RESPONSE),
        (["student warnings", "academic warning", "academic warnings"], ACADEMIC_WARNING_EN_RESPONSE),
        (
            [
                "official documents",
                "student documents",
                "enrollment certificate",
                "transcript",
                "transcripts",
                "graduation certificate",
                "replacement certificate",
                "embassy letter",
                "employer letter",
            ],
            DOCUMENTS_EN_RESPONSE,
        ),
        (["internship", "internships", "summer training", "training letter"], INTERNSHIP_EN_RESPONSE),
        (["graduation project"], student_affairs_fallback(question)),
        (["military training"], STUDENT_AFFAIRS_CONTACT_EN),
        (["higher studies", "postgraduate"], STUDENT_AFFAIRS_CONTACT_EN),
    ]
    for triggers, answer in topic_map:
        if any(trigger in lowered for trigger in triggers):
            return answer
    return None


def compound_topic_answer(question: str) -> Optional[str]:
    lowered = semantic_normalize(question).strip(" /?!.؟")
    if is_tools_topic_query(question):
        tools_answer = tools_answer_for_department_text(question)
        if tools_answer:
            return tools_answer
        return TOOLS_CLARIFICATION_RESPONSE
    if not contains_arabic(question) and fci_department_code_from_text(question) and looks_like_bare_fci_department_query(question):
        return None
    if contains_arabic(question):
        extended_answer = extended_topic_answer(question)
        if extended_answer:
            return extended_answer
        if any(term in lowered for term in ["ادوات علوم البيانات", "أدوات علوم البيانات"]):
            return TOOLS_ISDS_RESPONSE
        if any(term in lowered for term in ["ادوات الامن السيبراني", "أدوات الأمن السيبراني"]):
            return TOOLS_CSCS_RESPONSE
        if any(phrase in lowered for phrase in ["انشطة الطلاب", "أنشطة الطلاب", "اتحاد الطلاب"]):
            return arabic_policy_direct_answer("الأنشطة") or STUDENT_AFFAIRS_CONTACT_AR
        if any(phrase in lowered for phrase in ["خدمات الطلاب", "شؤون الطلاب", "شئون الطلاب", "شوون الطلاب"]):
            return STUDENT_AFFAIRS_CONTACT_AR
        return None

    if any(phrase in lowered for phrase in ["class schedules", "class schedules and rooms", "room schedule"]):
        return SCHEDULE_CLARIFICATION_RESPONSE
    if any(phrase in lowered for phrase in ["what are the tools", "tools for", "recommended tools"]):
        topic_answer = english_hardcoded_topic_answer(question)
        if topic_answer:
            return topic_answer
        return TOOLS_CLARIFICATION_RESPONSE
    if is_english_intent_opener(question):
        topic_answer = english_hardcoded_topic_answer(question)
        if topic_answer:
            return topic_answer
        return GENERAL_CHAT_FALLBACK_RESPONSE
    match = re.search(r"\bstudent\s+(activities|union|services|affairs|discipline|warnings|exchange|rights)\b", lowered)
    if not match:
        return english_hardcoded_topic_answer(question)
    topic = match.group(1)
    if topic in {"activities", "union"}:
        return ACTIVITIES_EN_RESPONSE
    if topic in {"services", "affairs", "exchange", "rights"}:
        return STUDENT_AFFAIRS_CONTACT_EN
    if topic == "discipline":
        return DISCIPLINE_EN_RESPONSE
    if topic == "warnings":
        return ACADEMIC_WARNING_EN_RESPONSE
    return None


def is_english_intent_opener(text: str) -> bool:
    lowered = semantic_normalize(text).strip(" .?!")
    return bool(
        re.match(
            r"^(i want to|i need to|i would like to|i'd like to|im trying to|i'm trying to|"
            r"im looking to|i'm looking to|im hoping to|i'm hoping to|i wish to|"
            r"im struggling to|i'm struggling to|i can't seem to|i cant seem to|"
            r"help me to|help me with|can you help me|how do i|how can i|how should i|"
            r"what should i|what can i|where do i|i don't know how to|i dont know how to|"
            r"i'm not sure how to|im not sure how to|is it possible to|is there a way to)\b",
            lowered,
        )
    )


def dispatch_compound_topic_answer(
    dispatcher: CollectingDispatcher,
    text: str,
    tracker: Optional[Tracker] = None,
) -> Optional[List[Dict[Text, Any]]]:
    answer = compound_topic_answer(text)
    if not answer:
        return None
    events: List[Dict[Text, Any]] = [
        SlotSet("last_query_scope", "knowledge"),
        SlotSet("last_topic", semantic_normalize(text)[:80]),
        SlotSet("last_entity_type", "topic"),
        SlotSet("last_conversation_topic", conversation_topic_for_text(text, answer)),
    ]
    if answer == TOOLS_CLARIFICATION_RESPONSE:
        events.append(SlotSet("last_clarification_topic", "tools_by_dept"))
    dispatcher.utter_message(text=with_duplicate_prompt(answer, text, tracker))
    return events


def append_arabic_official_followup(answer: str, question: str) -> str:
    """Add office guidance for exact amounts, dates, and paperwork questions."""

    lowered = semantic_normalize(question)
    additions: List[str] = []

    fee_amount_terms = [
        "كم",
        "كام",
        "قد ايه",
        "هدفع",
        "قيمة",
        "مبلغ",
        "المبلغ",
        "مصروفات",
        "المصروفات",
        "الرسوم",
        "رسوم",
        "دفع",
        "سداد",
        "تقسيط",
        "payment",
        "pay fees",
    ]
    exact_date_terms = [
        "امتى",
        "متى",
        "موعد",
        "مواعيد",
        "تاريخ",
        "اخر موعد",
        "آخر موعد",
        "deadline",
        "deadlines",
        "ينتهي",
        "تنتهي",
        "متى تظهر",
    ]
    paperwork_terms = [
        "نموذج",
        "استمارة",
        "طلب",
        "اوراق",
        "أوراق",
        "مستند",
        "وثيقة",
        "شهادة",
        "خطاب",
        "اثبات",
        "إثبات",
        "قيد",
        "بدل فاقد",
        "سفارة",
        "transcript",
        "ترانسكريبت",
    ]

    if any(semantic_normalize(term) in lowered for term in fee_amount_terms):
        additions.append("للاستعلام عن المبلغ الدقيق: 📍 الإدارة المالية، أكاديمية السادات.")
    if any(semantic_normalize(term) in lowered for term in exact_date_terms):
        additions.append("للاطلاع على المواعيد الدقيقة لهذا الفصل: 📍 مكتب شؤون الطلاب.")
    has_location_reference = any(
        marker in answer
        for marker in [
            "📍 مكتب شؤون الطلاب",
            "📍 الإدارة المالية",
            "📍 ادارة شؤون الطلاب",
            "مكتب شؤون الطلاب —",
            "مكتب شؤون الطلاب -",
        ]
    )
    if any(semantic_normalize(term) in lowered for term in paperwork_terms) and not has_location_reference:
        additions.append("📍 مكتب شؤون الطلاب — كلية الحاسبات والمعلومات، المعادي.")

    final = answer.rstrip()
    for line in additions:
        if line not in final:
            final = f"{final}\n{line}"
    return final


ARABIC_HARDCODED_ONLY_TERMS = [
    "الغياب",
    "التخصص",
    "الرسوم",
    "المصروفات",
    "المصاريف",
    "مصروفات",
    "مصاريف",
    "الامتحانات",
    "الانذار",
    "الرسوب",
    "التسجيل",
    "الانسحاب",
    "العبء",
    "نظام",
    "الساعات",
    "ساعات",
    "الارشاد",
    "التاديب",
    "التأديب",
    "الاقسام",
    "الرؤية",
    "الروية",
    "الرسالة",
    "الاهداف",
    "الأهداف",
    "مبررات",
    "الخلفية",
    "وقف",
    "تظلم",
    "التظلم",
    "اعتراض",
    "مراجعة",
    "النتيجة",
    "نتيجتي",
    "النتايج",
    "شكوى",
    "شكاوى",
    "العسكرية",
    "التربية",
    "انشطة",
    "أنشطة",
    "مسرح",
    "رياضة",
    "تدريب",
    "انترنشيب",
    "إنترنشيب",
    "internship",
    "مشروع",
    "تخرج",
    "ماجستير",
    "دكتوراه",
    "دراسات",
    "دراسات عليا",
    "استشارة",
    "نصيحة",
    "ادوات",
    "أدوات",
    "اثبات",
    "قيد",
    "تجنيد",
    "شهادة",
    "ترانسكريبت",
    "درجات",
    "بدل",
    "فاقد",
    "سفارة",
    "دفع",
    "سداد",
    "فلوس",
    "مصاريف",
    "الكلية",
    "الاكاديمية",
]


def is_arabic_hardcoded_only_query(text: str) -> bool:
    if not contains_arabic(text):
        return False
    variants = arabic_match_variants(text)
    tokens = []
    for variant in variants:
        tokens.extend(re.findall(r"[a-z0-9]+|[\u0621-\u063a\u0641-\u064a]+", variant))
    token_set = set(tokens)
    for term in ARABIC_HARDCODED_ONLY_TERMS:
        normalized_values = {semantic_normalize(term).strip(), arabic_typo_normalize(term).strip()}
        for normalized in normalized_values:
            if not normalized:
                continue
            if " " in normalized:
                if any(normalized in variant for variant in variants):
                    return True
            elif normalized in token_set:
                return True
    return False


def clean_arabic_rag_answer(answer: str, question: str = "") -> str:
    cleaned = normalize_arabic_text(answer or "").strip()
    direct = arabic_policy_direct_answer(question)
    if direct:
        return direct
    cleaned = re.sub(r"(?im)\bPage\s+\d+\b", "", cleaned)
    cleaned = re.sub(r"(?im)\bصفحة\s+\d+\b", "", cleaned)
    cleaned = re.sub(r"(?is)\bالمادة\s+رقم\s*\(?\s*\d+\s*\)?", "", cleaned)
    cleaned = re.sub(r"(?is)\bEnglish\s+translation\s+pending\b.*?(?=$|\n|\.|،)", "", cleaned)
    cleaned = re.sub(r"(?is)\bUse\s+the\s+paired\s+Arabic.*?(?=$|\n|\.|،)", "", cleaned)
    cleaned = re.sub(r"(?is)^\s*حسب\s+(?:المصدر|اللايحة|اللائحة|دليل|ملف|وثيقة)[^:：\n]{0,160}\s*:?\s*", "", cleaned)
    cleaned = re.sub(r"(?is)\bالرسمي\s*:\s*", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*(?:المصدر|مصدر|Source|Sources)\s*:.*$", "", cleaned)
    cleaned = re.sub(r"(?is)\s*(?:المصدر|مصدر|Source|Sources)\s*:\s*.*$", "", cleaned)
    cleaned = re.sub(r"(?is)Question\s+\d+\s*\([A-Z]{2}\)\s*Question:\s*.*?\bAnswer:\s*", "", cleaned)
    cleaned = re.sub(r"(?is)سؤال\s+\d+\s*\([A-Z]{2}\)\s*السؤال:\s*.*?الإجابة:\s*", "", cleaned)
    cleaned = re.sub(r"(?is)\b(?:السؤال|Question)\s*:\s*.*?(?:الإجابة|Answer)\s*:\s*", "", cleaned)
    cleaned = re.sub(r"(?is)^.*?[؟?]\s*", "", cleaned)
    cleaned = re.sub(
        r"(?is)^\s*(?:ممكن\s+توضح|ما\s+هو|ما\s+هي|من\s+يحدد|ما\s+نسبة|من\s+يضع|ما\s+الحد|ايه\s+هي|ايه\s+هو|هل)\s+",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\b25\s*٪\s*25\s*%\b", "25%", cleaned)
    cleaned = re.sub(r"\b25\s*%\s*25\s*٪\b", "25%", cleaned)
    cleaned = re.sub(r"\s*[-–]\s*اساسيات.*$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .،\n\t")
    if re.search(r"(?i)\bpage\s+\d+\b|english translation pending|source\s*:", cleaned):
        return student_affairs_fallback(question)
    if re.search(r"المادة\s+رقم|المصدر\s*:|سؤال\s+\d+", cleaned):
        return student_affairs_fallback(question)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .،\n\t")
    if "؟" in cleaned:
        cleaned = re.sub(r"[^.؟!]*؟\s*", "", cleaned).strip()
    return cleaned or student_affairs_fallback(question)


def conversationalize_rag_answer(answer: str, question: str = "") -> str:
    """Hide retrieval/source boilerplate unless the user explicitly asks for it."""

    cleaned = (answer or "").strip()
    if not cleaned:
        return unconfirmed_fallback(question)

    cleaned = re.sub(
        r"(?is)^\s*(according to|based on)\s+(?:the\s+)?(?:fci\s+)?(?:official\s+)?academic\s+polic(?:y|ies)\s*:?\s*",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"(?is)^\s*(according to|based on)\s+(?:the\s+)?(?:fci\s+)?(?:bilingual\s+)?(?:official\s+)?(?:policy\s+)?(?:q&a\s+)?(?:source|document|file|student guide|attached file)\s*:?\s*",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"(?is)^\s*حسب\s+(?:مصدر\s+)?(?:الأسئلة\s+والأجوبة\s+)?(?:الرسمي\s+)?(?:لكلية\s+الحاسبات\s+والمعلومات|دليل\s+الطالب|دليل\s+الكلية)\s*:?\s*",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"(?is)^\s*حسب\s+(?:دليل|ملف|وثيقة|مصدر)\s+[^:：\n]{0,120}\s*:?\s*",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"(?is)\bQuestion\s+\d+\s*\([A-Z]{2}\)\s*Question:\s*",
        "",
        cleaned,
    )
    cleaned = re.sub(r"(?is)\bQuestion:\s*", "", cleaned)
    cleaned = re.sub(r"(?is)\bAnswer:\s*", "", cleaned)
    cleaned = re.sub(r"(?is)\bسؤال\s+\d+\s*\([A-Z]{2}\)\s*السؤال:\s*", "", cleaned)
    cleaned = re.sub(r"(?is)\bالسؤال:\s*", "", cleaned)
    cleaned = re.sub(r"(?is)\bالإجابة:\s*", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*(?:Source|Sources|المصدر|مصدر)\s*:.*(?:\n|$)", "", cleaned)
    cleaned = re.sub(r"(?is)\s*(?:Source|Sources|المصدر|مصدر)\s*:\s*(?:FCI_Bilingual|Q&A|Dataset|[^.\n]*(?:\.docx|\.pdf)).*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*-\s+.*(?:FCI_Bilingual|Q&A|Dataset|\.docx|\.pdf).*(?:\n|$)", "", cleaned)
    if contains_arabic(question) or contains_arabic(cleaned):
        cleaned = clean_arabic_rag_answer(cleaned, question)
        if re.search(r"لم\s+اجد|لم\s+أجد", cleaned):
            return unconfirmed_fallback(question)
        return cleaned
    question_words = (
        "what|who|when|where|which|how|why|can|does|do|is|are|"
        "من|ما|متى|اين|أين|ايه|هل|كم|كيف|لماذا|ماذا|مين"
    )
    cleaned = re.sub(rf"(?is)(^|\s)(?:{question_words})\b[^?؟\n]{{0,260}}[?؟]\s*", " ", cleaned)
    cleaned = re.sub(r"(?is)\n{3,}", "\n\n", cleaned).strip()
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    if re.search(r"(?i)i\s+could\s+not\s+find|couldn'?t\s+find|لم\s+اجد|لم\s+أجد", cleaned):
        return unconfirmed_fallback(question)
    if not cleaned:
        return unconfirmed_fallback(question)
    return cleaned


def rag_payload_is_confident(payload: Dict[str, Any], question: str) -> bool:
    answer = str((payload or {}).get("answer") or "").strip()
    if not answer:
        return False
    if re.search(r"(?i)i\s+couldn'?t\s+find|could\s+not\s+find|no\s+relevant|not\s+found", answer):
        return False
    if re.search(r"لم\s+اجد|لم\s+أجد|لا\s+توجد", answer):
        return False

    scores: List[float] = []

    def collect_scores(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                key_lower = str(key).lower()
                if key_lower in {"score", "similarity", "similarity_score", "confidence", "relevance", "relevance_score"}:
                    try:
                        numeric = float(nested)
                    except (TypeError, ValueError):
                        numeric = None
                    if numeric is not None:
                        scores.append(numeric)
                elif isinstance(nested, (dict, list)):
                    collect_scores(nested)
        elif isinstance(value, list):
            for item in value:
                collect_scores(item)

    collect_scores(payload)
    if scores and max(scores) < 0.75:
        return False

    return True


def query_rag_service(question: str) -> str:
    if is_abusive_input(question):
        return abuse_response(question)
    if is_question_opener(question):
        return question_opener_response(question)
    if is_status_check(question):
        return status_response(question)
    if is_thanks(question):
        return thanks_response(question)
    if is_greeting(question):
        return greeting_response(question)
    if is_gibberish(question):
        return gibberish_response(question)
    if is_conversation_continuation_reply(question):
        return continuation_answer_for_topic("general_chat")
    if is_bot_identity_question(question):
        return BOT_IDENTITY_RESPONSE
    if is_fci_identity_query(question):
        return FCI_IDENTITY_RESPONSE
    compound_answer = compound_topic_answer(question)
    if compound_answer:
        return compound_answer
    if is_unfiltered_schedule_query(question):
        return SCHEDULE_CLARIFICATION_RESPONSE
    english_answer = english_hardcoded_topic_answer(question)
    if english_answer:
        return english_answer
    if contains_arabic(question):
        direct = arabic_policy_direct_answer(question)
        if direct:
            return direct
        if is_arabic_hardcoded_only_query(question):
            return student_affairs_fallback(question)
    if looks_like_unrecognized_policy_request(question):
        return student_affairs_fallback(question)

    response = requests.post(
        RAG_URL,
        json={"question": question},
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    if not rag_payload_is_confident(payload, question):
        return student_affairs_fallback(question)
    answer = payload.get("answer", "I couldn't find relevant information.")
    sources = payload.get("sources") or []
    source_requested = bool(
        re.search(
            r"\b(source|sources|where did you get|is this official|reference|references)\b",
            semantic_normalize(question),
        )
        or re.search(r"(المصدر|مصدر|جبتها منين|منين المعلومة|هل\s+.*رسمي)", semantic_normalize(question))
    )
    answer = conversationalize_rag_answer(str(answer or ""), question)
    source_lines = []
    for source in sources:
        url = source.get("source_url")
        title = source.get("title") or source.get("page_title")
        if url and source.get("official_source"):
            label = title or "Official FCI website"
            line = f"- {label}: {url}"
            if line not in source_lines:
                source_lines.append(line)
        if len(source_lines) >= 3:
            break
    if source_requested and source_lines:
        answer = f"{answer}\n\nSources:\n" + "\n".join(source_lines)
    return answer


def sql_engine_payload(question: str, tracker: Tracker) -> Dict[str, Any]:
    return {
        "question": question,
        "context": {
            "student_id": tracker.get_slot("student_id"),
            "student_name": tracker.get_slot("student_name"),
            "course_code": tracker.get_slot("course_code"),
            "course_name": tracker.get_slot("course_name"),
            "department_code": tracker.get_slot("department_code"),
            "group_code": tracker.get_slot("group_code"),
            "academic_year": tracker.get_slot("academic_year"),
            "year_level": tracker.get_slot("year_level"),
            "semester": tracker.get_slot("semester"),
            "day": tracker.get_slot("day"),
            "time": tracker.get_slot("time"),
            "last_domain": tracker.get_slot("last_query_scope"),
            "last_topic": tracker.get_slot("last_topic"),
            "last_entity_type": tracker.get_slot("last_entity_type"),
            "instructor_name": tracker.get_slot("instructor_name"),
            "last_result_rows": tracker.get_slot("sql_result_cache") or [],
            "last_result_plan": tracker.get_slot("sql_result_plan"),
            "last_result_offset": int(tracker.get_slot("sql_result_offset") or 0),
            "last_result_page_size": int(tracker.get_slot("sql_result_page_size") or 10),
            "pending_candidates": tracker.get_slot("pending_student_candidates") or [],
            "pending_question": tracker.get_slot("pending_sql_question"),
        },
        "debug": False,
    }


def continuation_replay_question(tracker: Tracker) -> Optional[str]:
    def replay_for_department(department_code: Optional[str], group_code: Optional[str] = None) -> Optional[str]:
        if department_code == "ISDS" or group_code in {"DS", "DS1", "DS2", "ISDS", "ISDS1", "ISDS2"}:
            return "give me 50 students in data science"
        if department_code == "SE":
            return "give me 50 students in software engineering"
        if department_code in {"CS", "CSCS"}:
            return "give me 50 students in cyber security"
        if department_code == "AI":
            return "give me 50 students in artificial intelligence"
        if group_code:
            return f"give me 50 students in {group_code}"
        return None

    plan = tracker.get_slot("sql_result_plan") or {}
    if not isinstance(plan, dict) or plan.get("domain") != "student" or plan.get("operation") != "list":
        department_code = tracker.get_slot("department_code")
        group_code = tracker.get_slot("group_code")
        replay = replay_for_department(department_code, group_code)
        if replay:
            return replay
        for event in reversed(tracker.events or []):
            if event.get("event") != "user":
                continue
            text = event.get("text") or ""
            if looks_like_result_continuation(text):
                continue
            lowered = semantic_normalize(text)
            if "student" not in lowered and "students" not in lowered and not any(term in lowered for term in ["طالب", "طلاب", "طلبة"]):
                continue
            department_from_text = fci_department_code_from_text(text)
            group_from_text = fci_extract_group_code(text)
            replay = replay_for_department(department_from_text, group_from_text)
            if replay:
                return replay
        return None

    filters = plan.get("filters") or {}
    department_code = filters.get("department_code") or tracker.get_slot("department_code")
    group_code = filters.get("group_code") or tracker.get_slot("group_code")
    replay = replay_for_department(department_code, group_code)
    if replay:
        return replay
    for event in reversed(tracker.events or []):
        if event.get("event") != "user":
            continue
        text = event.get("text") or ""
        if looks_like_result_continuation(text):
            continue
        replay = replay_for_department(fci_department_code_from_text(text), fci_extract_group_code(text))
        if replay:
            return replay
    return None


def wants_all_continuation(text: str) -> bool:
    lowered = semantic_normalize(text).strip(" .?!؟")
    return bool(
        re.fullmatch(
            r"(?:all\s+of\s+them|al\s+of\s+them|all\s+of\s+the|al\s+of\s+the|"
            r"alll|all|the\s+rest|and\s+the\s+rest|rest\s+of\s+them|remaining|"
            r"show\s+the\s+rest|show\s+all|show\s+al|all\s+results|"
            r"i\s+want\s+all|want\s+all|give\s+me\s+all)",
            lowered,
        )
    ) or lowered in {
        "كلهم",
        "الكل",
        "كله",
        "باقيهم",
        "الباقي",
        "والباقي",
        "والبقية",
        "الباقين",
    }


def course_catalog_cache_events(
    courses: Sequence[Dict[str, Any]],
    header: str,
    offset: int,
    page_size: int,
) -> List[Dict[Text, Any]]:
    return [
        SlotSet("last_query_scope", "course_catalog"),
        SlotSet("sql_result_cache", list(courses)),
        SlotSet(
            "sql_result_plan",
            {
                "domain": "course_catalog",
                "operation": "list",
                "header": header,
                "page_size": page_size,
            },
        ),
        SlotSet("sql_result_offset", offset),
        SlotSet("sql_result_page_size", page_size),
    ]


def cached_continuation_result(question: str, tracker: Tracker) -> Optional[Dict[str, Any]]:
    if not looks_like_result_continuation(question):
        return None
    rows = tracker.get_slot("sql_result_cache") or []
    plan = tracker.get_slot("sql_result_plan") or {}
    if not rows or not isinstance(plan, dict):
        return None
    if plan.get("domain") == "course_catalog" and plan.get("operation") == "list":
        total = len(rows)
        offset = max(int(tracker.get_slot("sql_result_offset") or 0), 0)
        page_size = max(int(tracker.get_slot("sql_result_page_size") or plan.get("page_size") or 5), 1)
        show_all = wants_all_continuation(question)
        if offset >= total:
            return {
                "handled": True,
                "answer": "You are already at the end of those course results.",
                "domain": "course_catalog",
                "operation": "list",
                "confidence": 0.95,
                "context_updates": {
                    "last_domain": "course_catalog",
                    "last_result_rows": rows,
                    "last_result_plan": plan,
                    "last_result_offset": offset,
                    "last_result_page_size": page_size,
                },
                "row_count": 0,
            }

        max_results = total - offset if show_all else page_size
        end = min(offset + max_results, total)
        answer = format_fci_catalog_course_matches(
            str(plan.get("header") or "Course results:"),
            rows,
            max_results=max_results,
            offset=offset,
        )
        if show_all:
            dept_code = ""
            header_match = re.search(r"\bCourses\s+for\s+([A-Z]{2,4})\b", str(plan.get("header") or ""))
            if header_match:
                dept_code = header_match.group(1).upper()
            elif rows and isinstance(rows[0], dict):
                dept_code = str(rows[0].get("dept") or rows[0].get("DepartmentCode") or "").upper()
            dept_name = ""
            if dept_code and get_department:
                department = get_department(dept_code)
                dept_name = str((department or {}).get("name") or dept_code)
            if dept_name:
                answer = f"{answer}\n\nThat's all {total} courses for {dept_name}."
            else:
                answer = f"{answer}\n\nThat's all {total} matching courses."
        return {
            "handled": True,
            "answer": answer,
            "domain": "course_catalog",
            "operation": "list",
            "confidence": 0.98,
            "context_updates": {
                "last_domain": "course_catalog",
                "last_result_rows": rows,
                "last_result_plan": plan,
                "last_result_offset": end,
                "last_result_page_size": page_size,
            },
            "row_count": end - offset,
        }
    if plan.get("domain") != "student" or plan.get("operation") != "list":
        return None

    total = len(rows)
    offset = max(int(tracker.get_slot("sql_result_offset") or 0), 0)
    page_size = max(int(tracker.get_slot("sql_result_page_size") or plan.get("page_size") or 10), 1)
    show_all = wants_all_continuation(question)
    if offset >= total:
        return {
            "handled": True,
            "answer": "You are already at the end of those results.",
            "domain": "student",
            "operation": "list",
            "confidence": 0.95,
            "context_updates": {
                "last_result_rows": rows,
                "last_result_plan": plan,
                "last_result_offset": offset,
                "last_result_page_size": page_size,
            },
            "row_count": 0,
        }

    page_rows = rows[offset:] if show_all else rows[offset : offset + page_size]
    start = offset + 1
    end = offset + len(page_rows)
    lines = [f"Showing results {start}-{end} of {total}."]
    for row in page_rows:
        lines.append(
            f"- {row.get('FullName', 'unknown')} (StudentID {row.get('StudentID', 'unknown')}), "
            f"group {row.get('GroupCode', 'unknown')}, {row.get('DepartmentName', 'unknown')}"
        )
    if end < total:
        lines.append('Say "next" or "show more" to continue, or "all of them" to show the rest.')
    next_offset = min(end, total)
    return {
        "handled": True,
        "answer": "\n".join(lines),
        "domain": "student",
        "operation": "list",
        "confidence": 0.98,
        "context_updates": {
            "last_domain": "student",
            "last_result_rows": rows,
            "last_result_plan": plan,
            "last_result_offset": next_offset,
            "last_result_page_size": page_size,
        },
        "row_count": len(page_rows),
    }


def query_local_sql_engine(question: str, tracker: Tracker) -> Optional[Dict[str, Any]]:
    global _LOCAL_SQL_ENGINE
    if SQL_ENGINE_LOCAL_PATH and SQL_ENGINE_LOCAL_PATH not in sys.path:
        sys.path.append(SQL_ENGINE_LOCAL_PATH)
    from sql_engine.models import ContextPayload, QueryRequest
    from sql_engine.service import SqlEngineService

    if _LOCAL_SQL_ENGINE is None:
        _LOCAL_SQL_ENGINE = SqlEngineService()

    payload = sql_engine_payload(question, tracker)
    context = ContextPayload(**payload["context"])
    result = _LOCAL_SQL_ENGINE.answer(QueryRequest(question=question, context=context, debug=False))
    return result.dict()


def stale_sql_engine_result(question: str, result: Dict[str, Any]) -> bool:
    """Detect old SQL-engine responses so Rasa can use the updated local engine."""

    if not result or not result.get("handled"):
        return False
    lowered = semantic_normalize(question)
    answer = str(result.get("answer") or "").lower()
    domain = str(result.get("domain") or "")
    operation = str(result.get("operation") or "")
    is_student_list = domain == "student" and operation == "list"
    asks_student_list = "student" in lowered or "students" in lowered or "طالب" in lowered or "طلاب" in lowered or "طلبة" in lowered
    missing_pagination_hint = "show more" not in answer and "next" not in answer and "all of them" not in answer
    old_preview_shape = "i found 20 matching students" in answer and "first 10" in answer
    broad_request = bool(re.search(r"\ball\s+(?:the\s+)?students?\b", lowered)) or "all of them" in lowered
    old_schedule_shape = domain == "schedule" and any(
        label in answer
        for label in [
            "day:",
            "start time:",
            "end time:",
            "course code:",
            "section type:",
            "target group:",
        ]
    )
    old_gpa_shape = domain == "gpa" and "matching students" in answer and "academic year:" in answer
    return (
        (is_student_list and asks_student_list and missing_pagination_hint and (old_preview_shape or broad_request))
        or old_schedule_shape
        or old_gpa_shape
    )


def query_sql_engine_service(question: str, tracker: Tracker, timeout: int = 8) -> Optional[Dict[str, Any]]:
    cached_result = cached_continuation_result(question, tracker)
    if cached_result:
        return cached_result

    if SQL_ENGINE_DISABLED:
        return query_local_sql_engine(question, tracker)

    if looks_like_result_continuation(question) and not tracker.get_slot("sql_result_cache"):
        replay_question = continuation_replay_question(tracker)
        if replay_question:
            result = query_local_sql_engine(replay_question, tracker)
            if result and result.get("handled"):
                return result

    payload = sql_engine_payload(question, tracker)
    try:
        response = requests.post(SQL_ENGINE_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        if stale_sql_engine_result(question, result):
            local_result = query_local_sql_engine(question, tracker)
            if local_result:
                return local_result
        return result
    except Exception:
        return query_local_sql_engine(question, tracker)


def sql_engine_events(result: Dict[str, Any]) -> List[Dict[Text, Any]]:
    updates = result.get("context_updates") or {}
    events: List[Dict[Text, Any]] = []
    last_domain = updates.get("last_domain") or result.get("domain")
    if last_domain:
        events.append(SlotSet("last_query_scope", str(last_domain)))
    if updates.get("student_id"):
        events.append(SlotSet("student_id", str(updates["student_id"])))
    if updates.get("student_name"):
        events.append(SlotSet("student_name", str(updates["student_name"])))
    if updates.get("course_code"):
        events.append(SlotSet("course_code", str(updates["course_code"])))
    if updates.get("course_name"):
        events.append(SlotSet("course_name", str(updates["course_name"])))
    if updates.get("department_code"):
        events.append(SlotSet("department_code", str(updates["department_code"])))
    if updates.get("instructor_name"):
        events.append(SlotSet("instructor_name", str(updates["instructor_name"])))
    if updates.get("last_topic"):
        events.append(SlotSet("last_topic", str(updates["last_topic"])))
    if updates.get("last_entity_type"):
        events.append(SlotSet("last_entity_type", str(updates["last_entity_type"])))
    if updates.get("group_code"):
        events.append(SlotSet("group_code", str(updates["group_code"])))
    if updates.get("academic_year"):
        events.append(SlotSet("academic_year", str(updates["academic_year"])))
    if updates.get("year_level"):
        events.append(SlotSet("year_level", str(updates["year_level"])))
    if updates.get("semester"):
        events.append(SlotSet("semester", str(updates["semester"])))
    if updates.get("day"):
        events.append(SlotSet("day", str(updates["day"])))
    if updates.get("time"):
        events.append(SlotSet("time", str(updates["time"])))
    if "pending_candidates" in updates:
        pending = updates.get("pending_candidates") or None
        events.append(SlotSet("pending_student_candidates", pending))
    if "pending_question" in updates:
        events.append(SlotSet("pending_sql_question", updates.get("pending_question")))
    if "last_result_rows" in updates:
        events.append(SlotSet("sql_result_cache", updates.get("last_result_rows") or []))
    if "last_result_plan" in updates:
        events.append(SlotSet("sql_result_plan", updates.get("last_result_plan")))
    if "last_result_offset" in updates:
        events.append(SlotSet("sql_result_offset", updates.get("last_result_offset") or 0))
    if "last_result_page_size" in updates:
        events.append(SlotSet("sql_result_page_size", updates.get("last_result_page_size") or 10))
    return events


def utter_sql_engine_result(
    dispatcher: CollectingDispatcher,
    result: Dict[str, Any],
    question: str = "",
    tracker: Optional[Tracker] = None,
) -> None:
    text = result.get("answer", "I could not answer that SQL question yet.")
    lowered = str(text or "").lower()
    if (
        "spelling mistake" in lowered
        or "i could not find matching data" in lowered
        or "could not find matching data" in lowered
        or "i couldn't find matching data" in lowered
        or "i could not answer" in lowered
        or "could not answer" in lowered
        or "not available in the current database" in lowered
    ):
        text = unanswered_question_fallback(question)
    text = with_duplicate_prompt(str(text or ""), question, tracker)
    attachments = result.get("attachments") or []
    if attachments:
        dispatcher.utter_message(text=text, json_message={"attachments": attachments})
    else:
        dispatcher.utter_message(text=text)


def has_pending_sql_clarification(tracker: Tracker) -> bool:
    return bool(tracker.get_slot("pending_student_candidates") and tracker.get_slot("pending_sql_question"))


def try_sql_probe_before_fallback(
    dispatcher: CollectingDispatcher,
    tracker: Tracker,
    user_message: str,
) -> Optional[List[Dict[Text, Any]]]:
    route_name = hybrid_route(user_message, tracker).get("route")
    if route_name != "structured_sql":
        return None
    try:
        result = query_sql_engine_service(user_message, tracker)
    except Exception:
        return None
    if not result:
        return None
    if result.get("needs_clarification") or (
        result.get("handled") and int(result.get("row_count") or 0) > 0
    ):
        utter_sql_engine_result(dispatcher, result, user_message, tracker)
        return sql_engine_events(result)
    return None


def recent_conversation_context(tracker: Tracker, limit: int = 6) -> str:
    lines = []
    for event in reversed(tracker.events or []):
        if event.get("event") == "user":
            text = event.get("text")
            if text:
                lines.append(f"Student: {text}")
        elif event.get("event") == "bot":
            text = event.get("text") or (event.get("data") or {}).get("text")
            if text:
                lines.append(f"BuddyBot: {text}")
        if len(lines) >= limit:
            break
    return "\n".join(reversed(lines))


def general_conversation_answer(message: str, tracker: Tracker) -> str:
    if not message.strip():
        return GENERAL_CHAT_FALLBACK_RESPONSE
    if is_abusive_input(message):
        return abuse_response(message)
    if is_question_opener(message):
        return question_opener_response(message)
    if is_status_check(message):
        return status_response(message)
    if is_thanks(message):
        return thanks_response(message)
    if is_greeting(message):
        return greeting_response(message)
    support_answer = emotional_support_answer(message)
    if support_answer:
        return support_answer
    if is_gibberish(message):
        return gibberish_response(message)
    if is_bot_identity_question(message):
        return BOT_IDENTITY_RESPONSE
    if is_fci_identity_query(message):
        return FCI_IDENTITY_RESPONSE
    academy_answer = sadat_academy_answer(message)
    if academy_answer:
        return academy_answer
    compound_answer = compound_topic_answer(message)
    if compound_answer:
        return compound_answer
    student_id = tracker.get_slot("student_id")
    last_scope = tracker.get_slot("last_query_scope")
    context = recent_conversation_context(tracker)
    student_context = (
        f"The current student context is StudentID {student_id}."
        if student_id and last_scope == "student"
        else "There is no active student record context."
    )

    prompt = f"""
You are BuddyBot, a friendly campus assistant for university students.

Your normal conversation role:
- Talk naturally and supportively, like a helpful university buddy.
- Give practical advice about studying, planning, motivation, stress, focus, campus life, and asking for help.
- Keep replies short: usually 2 to 5 sentences.
- Ask one useful follow-up question when it helps the conversation continue.

Boundaries:
- Do not invent student database facts, campus policies, fees, dates, schedules, staff names, or grades.
- If the student asks for student records or calculations, guide them to give a StudentID or a metric.
- If the student asks for official campus information, say you can check campus-service info if available.
- If the student mentions self-harm, immediate danger, or a crisis, be supportive and tell them to contact emergency services or a trusted person now.

{student_context}

Recent conversation:
{context}

Student message: {message}

BuddyBot reply:
"""

    try:
        answer = call_ollama(prompt, timeout=120)
    except Exception:
        return GENERAL_CHAT_FALLBACK_RESPONSE

    answer = re.sub(r"^(buddybot|assistant|bot)\s*:\s*", "", answer.strip(), flags=re.IGNORECASE)
    if not answer:
        return GENERAL_CHAT_FALLBACK_RESPONSE
    if len(answer) > 900:
        answer = answer[:900].rsplit(" ", 1)[0].strip() + "..."
    return answer


def is_bot_identity_question(text: str) -> bool:
    lowered = semantic_normalize(text).strip(" ?.!؟")
    return lowered in {
        "who are you",
        "what are you",
        "what are u",
        "who r u",
        "what r u",
        "what is buddybot",
        "what's buddybot",
        "whats buddybot",
        "مين انت",
        "من انت",
        "انت مين",
        "انتي مين",
        "ما انت",
        "ما أنت",
        "ما هو انت",
        "ما هو بوديبوت",
        "ايه انت",
        "إيه أنت",
    }


def is_fci_identity_query(text: str) -> bool:
    lowered = semantic_normalize(text).strip(" ?.!؟")
    return lowered in {
        "what is fci",
        "whats fci",
        "what's fci",
        "tell me about fci",
        "what is the faculty",
        "what's the faculty",
        "whats the faculty",
        "fci",
    }


def dispatch_fci_identity_answer(
    dispatcher: CollectingDispatcher,
    text: str,
) -> Optional[List[Dict[Text, Any]]]:
    if not is_fci_identity_query(text):
        return None
    dispatcher.utter_message(text=FCI_IDENTITY_RESPONSE)
    return [
        SlotSet("last_query_scope", "knowledge"),
        SlotSet("last_topic", "fci"),
        SlotSet("last_entity_type", "faculty"),
        SlotSet("last_conversation_topic", "general_chat"),
    ]


def sadat_academy_answer(text: str) -> Optional[str]:
    lowered = semantic_normalize(text)
    if any(
        term in lowered
        for term in [
            "how to get",
            "location",
            "address",
            "transport",
            "metro",
            "مواصلات",
            "كيف اوصل",
            "فين بالظبط",
        ]
    ):
        return None
    if (
        "sadat academy" not in lowered
        and "sams" not in lowered
        and "اكاديمية السادات" not in lowered
        and "سادات اكاديمي" not in lowered
        and "عن الاكاديمية" not in lowered
    ):
        return None
    if contains_arabic(text):
        return (
            "أكاديمية السادات للعلوم الإدارية مؤسسة تعليمية حكومية مصرية تأسست عام 1981،\n"
            "وسُمِّيت تيمُّناً بالرئيس أنور السادات. تقع في المعادي بالقاهرة وتتبع\n"
            "وزارة التعليم العالي المصرية.\n"
            "كلياتها ومعاهدها:\n"
            "• كلية علوم الإدارة — إدارة الأعمال والمحاسبة والاقتصاد.\n"
            "• كلية الحاسبات والمعلومات — علوم الحاسب والذكاء الاصطناعي والأمن السيبراني\n"
            "  وعلوم البيانات وهندسة البرمجيات.\n"
            "• كلية الفنون التطبيقية — التصميم والفنون الإبداعية.\n"
            "• كلية الأعمال الدولية والإنسانيات — اللغات الأجنبية والدراسات الدولية.\n"
            "• المعهد العالي للعلوم الإدارية — الإدارة العامة والسياسات.\n"
            "كلية الحاسبات والمعلومات تمنح درجة البكالوريوس في خمسة تخصصات:\n"
            "علوم الحاسب، الذكاء الاصطناعي، الأمن السيبراني،\n"
            "نظم المعلومات وعلوم البيانات، وهندسة البرمجيات."
        )
    return (
        "Sadat Academy for Management Sciences (SAMS) is an Egyptian public\n"
        "higher-education institution founded in 1981 and named after President\n"
        "Anwar El-Sadat. Located in Maadi, Cairo, it operates under the Egyptian\n"
        "Ministry of Higher Education.\n"
        "Faculties and institutes:\n"
        "• Faculty of Management Sciences — business administration, accounting, economics.\n"
        "• Faculty of Computers and Information (FCI) — computer science, AI, cyber\n"
        "  security, data science, and software engineering.\n"
        "• Faculty of Applied Arts — design and creative arts.\n"
        "• Faculty of International Business and Humanities — foreign languages,\n"
        "  international studies.\n"
        "• Higher Institute of Administrative Sciences — public administration and policy.\n"
        "FCI offers a 4-year bachelor's degree across five specialisations:\n"
        "Computer Sciences, Artificial Intelligence, Cyber Security,\n"
        "Information Systems & Data Science, and Software Engineering.\n"
        "BuddyBot serves the FCI community at the Maadi campus."
    )


def dispatch_sadat_academy_answer(
    dispatcher: CollectingDispatcher,
    text: str,
) -> Optional[List[Dict[Text, Any]]]:
    answer = sadat_academy_answer(text)
    if not answer:
        return None
    dispatcher.utter_message(text=answer)
    return [
        SlotSet("last_query_scope", "knowledge"),
        SlotSet("last_topic", "sadat_academy"),
        SlotSet("last_entity_type", "institution"),
        SlotSet("last_conversation_topic", "general_chat"),
    ]


def dispatch_arabic_policy_answer(
    dispatcher: CollectingDispatcher,
    text: str,
    tracker: Optional[Tracker] = None,
) -> Optional[List[Dict[Text, Any]]]:
    if not contains_arabic(text):
        return None
    try:
        answer = query_rag_service(text)
    except Exception:
        answer = student_affairs_fallback(text)
    if not (answer or "").strip():
        answer = student_affairs_fallback(text)
    dispatcher.utter_message(text=with_duplicate_prompt(answer, text, tracker))
    return [
        SlotSet("last_query_scope", "knowledge"),
        SlotSet("last_topic", semantic_normalize(text)[:80]),
        SlotSet("last_entity_type", "policy"),
        SlotSet("last_conversation_topic", conversation_topic_for_text(text, answer)),
    ]


def unconfirmed_fallback(text: str) -> str:
    return student_affairs_fallback(text)


def database_no_match_fallback(text: str) -> str:
    return student_affairs_fallback(text)


def student_affairs_fallback(text: str = "") -> str:
    return STUDENT_AFFAIRS_AR_FALLBACK if contains_arabic(text) else STUDENT_AFFAIRS_EN_FALLBACK


def previous_user_message(tracker: Optional[Tracker], current_text: str = "") -> Optional[str]:
    if not tracker:
        return None
    current = semantic_normalize(current_text).strip()
    skipped_current = False
    for event in reversed(tracker.events or []):
        if event.get("event") != "user":
            continue
        text = str(event.get("text") or "").strip()
        if not text:
            continue
        normalized = semantic_normalize(text).strip()
        if not skipped_current and normalized == current:
            skipped_current = True
            continue
        return text
    return None


def is_exact_repeat_message(tracker: Optional[Tracker], current_text: str) -> bool:
    previous = previous_user_message(tracker, current_text)
    return bool(previous and semantic_normalize(previous).strip() == semantic_normalize(current_text).strip())


def with_duplicate_prompt(answer: str, current_text: str, tracker: Optional[Tracker]) -> str:
    if not answer or not is_exact_repeat_message(tracker, current_text):
        return answer
    prompt = "هل تحتاج مزيداً من التفاصيل؟" if contains_arabic(current_text) else "Do you need more details?"
    if prompt in answer:
        return answer
    return f"{answer.rstrip()}\n{prompt}"


def student_not_found_fallback(name_or_id: str, text: str = "") -> str:
    if contains_arabic(text):
        return (
            f"لا يتوفر لديّ سجل طالب مطابق لـ {name_or_id} في النظام الحالي. "
            "للمزيد من المساعدة، يُرجى التوجه إلى مكتب شؤون الطلاب في كلية الحاسبات والمعلومات، فرع المعادي."
        )
    return (
        f"I don't have a student record matching {name_or_id} in the current system. "
        "For further help, please visit the Student Affairs office at FCI, Maadi Campus."
    )


def instructor_not_found_fallback(name: str, text: str = "") -> str:
    if contains_arabic(text):
        return (
            f"لم أجد محاضرا باسم {name} في نظام الكلية. يُرجى التوجه إلى مكتب شؤون الطلاب "
            "في كلية الحاسبات والمعلومات، فرع المعادي للحصول على المعلومة الصحيحة."
        )
    return (
        f"I couldn't find an instructor named {name} in the FCI system. Please visit the Student "
        "Affairs office at FCI, Maadi Campus for the correct information."
    )


def schedule_not_found_fallback(topic: str, text: str = "") -> str:
    if contains_arabic(text):
        return (
            f"لم أجد جدولا خاصا بـ {topic} في النظام. قد لا يكون الجدول قد تم رفعه بعد - "
            "يُرجى مراجعة مكتب شؤون الطلاب في كلية الحاسبات والمعلومات، فرع المعادي."
        )
    return (
        f"I couldn't find a schedule for {topic} in the system. Schedules may not have been "
        "uploaded yet - please check with the Student Affairs office at FCI, Maadi Campus."
    )


def extract_room_name(text: str) -> Optional[str]:
    invalid_suffixes = {"schedule", "schedules", "class", "classes", "lecture", "lectures", "lab", "labs", "on", "in", "for"}
    matches = list(re.finditer(r"\b(lab|room|hall)\b\s*[-#]?\s*([a-z0-9]+)\b", text or "", flags=re.I))
    matches.extend(re.finditer(r"\b(lab|room|hall)(\d+[a-z]?)\b", text or "", flags=re.I))
    for match in reversed(matches):
        if match.group(2).lower() in invalid_suffixes:
            continue
        return f"{match.group(1).title()} {match.group(2).upper()}"
    arabic_match = re.search(r"(?:معمل|قاعة|مدرج)\s*([0-9A-Za-z]+)", text or "")
    if arabic_match:
        return arabic_match.group(0).strip()
    return None


def has_specific_schedule_filter(text: str) -> bool:
    lowered = semantic_normalize(text)
    if extract_student_id(text) or fci_extract_course_code(text) or fci_department_code_from_text(text):
        return True
    if fci_extract_group_code(text) or fci_extract_day(text) or fci_extract_academic_year(text) or fci_extract_year_level(text):
        return True
    if extract_room_name(text):
        return True
    if extract_fci_instructor_name(text) or extract_instructor_course_query_name(text):
        return True
    course_phrase = fci_course_phrase_from_question(text)
    if course_phrase and not text_has_any(semantic_normalize(course_phrase), ["schedule", "timetable", "class schedules", "room schedule"]):
        return True
    if re.search(r"\b(?:dr|doctor|prof|professor)\.?\s+[a-z]", lowered):
        return True
    return False


def is_unfiltered_schedule_query(text: str) -> bool:
    lowered = semantic_normalize(text)
    schedule_terms = [
        "schedule",
        "timetable",
        "class schedules",
        "class schedule",
        "room schedule",
        "جدول",
        "محاضرات",
        "سكاشن",
    ]
    if not text_has_any(lowered, schedule_terms):
        return False
    if text_has_any(lowered, ["exam schedule", "exam dates", "امتحان", "امتحانات"]):
        return False
    return not has_specific_schedule_filter(text)


def dispatch_schedule_clarification(
    dispatcher: CollectingDispatcher,
    text: str,
    tracker: Optional[Tracker] = None,
) -> Optional[List[Dict[Text, Any]]]:
    if not is_unfiltered_schedule_query(text):
        return None
    dispatcher.utter_message(text=with_duplicate_prompt(SCHEDULE_CLARIFICATION_RESPONSE, text, tracker))
    return [SlotSet("last_query_scope", "schedule"), SlotSet("last_clarification_topic", "schedule_filter")]


def gpa_not_found_fallback(student: str, text: str = "") -> str:
    if contains_arabic(text):
        return (
            f"لم يتم تسجيل سجلات GPA الخاصة بـ {student} في النظام حتى الآن. يُرجى التوجه إلى "
            "مكتب شؤون الطلاب في كلية الحاسبات والمعلومات، فرع المعادي للحصول على بيان رسمي."
        )
    return (
        f"GPA records for {student} haven't been recorded yet in the system. Please visit "
        "the Student Affairs office at FCI, Maadi Campus for your official transcript."
    )


def unanswered_question_fallback(text: str) -> str:
    lowered = semantic_normalize(text)
    if text_has_any(lowered, ["schedule", "timetable", "lecture", "lectures", "class", "classes", "lab", "labs", "جدول", "محاضرة", "سكشن"]):
        topic = re.sub(r"\b(schedule|timetable|lecture|lectures|class|classes|lab|labs|when|where|for|of|what|is|the)\b", " ", normalize_question(text), flags=re.I)
        topic = re.sub(r"\s+", " ", topic).strip(" ?.!/") or "that request"
        return schedule_not_found_fallback(topic, text)
    if text_has_any(lowered, ["gpa", "cgpa", "معدل", "المعدل"]):
        return gpa_not_found_fallback("that student", text)
    if text_has_any(lowered, ["student", "students", "طالب", "طلاب", "طلبة"]):
        return student_not_found_fallback(extract_student_id(text) or "that name", text)
    if text_has_any(lowered, ["instructor", "teacher", "professor", "dr ", "doctor", "teaches", "محاضر", "دكتور"]):
        name = extract_instructor_course_query_name(text) or extract_fci_instructor_name(text) or "that name"
        return instructor_not_found_fallback(name, text)
    return student_affairs_fallback(text)


def resolve_student_id(raw_input: str) -> Optional[str]:
    digits = re.sub(r"\D", "", raw_input or "")
    if not digits:
        return None
    if len(digits) == 7 and digits.startswith("212"):
        return digits
    if len(digits) == 3:
        return "2122" + digits
    if len(digits) == 4:
        return "212" + digits
    if len(digits) == 5:
        return "21" + digits
    return None


def extract_student_id(text: str) -> Optional[str]:
    stripped = (text or "").strip()
    stripped = re.sub(r"^(?:or|maybe|try)\s+", "", stripped, flags=re.IGNORECASE).strip()
    if re.fullmatch(r"\d{4,12}", stripped):
        return resolve_student_id(stripped) or stripped
    patterns = [
        r"\b(?:student\s*)?(?:id|code|number|no\.?|#)\s*(?:of|is|=|:|-)?\s*(\d{1,12})\b",
        r"\bstudent[\s_-]*(?:id|number|no\.?|#)\s*[:#-]?\s*(\d{1,12})\b",
        r"\bstudent\s+(\d{1,12})\b",
        r"\bstudentid\s*[:#-]?\s*(\d{1,12})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            digits = match.group(1)
            return resolve_student_id(digits) or digits
    return None


def normalize_question(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.translate(
        str.maketrans(
            {
                "’": "'",
                "‘": "'",
                "`": "'",
                "´": "'",
                "“": '"',
                "”": '"',
                "–": "-",
                "—": "-",
            }
        )
    )
    lowered = normalized.lower()
    for typo, correction in TYPO_NORMALIZATIONS.items():
        lowered = re.sub(rf"\b{re.escape(typo)}\b", correction, lowered)
    return lowered


def contains_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06ff]", text or ""))


def normalize_arabic_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"[\u064b-\u065f\u0670]", "", text)
    text = text.replace("\u0640", "")
    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def semantic_normalize(text: str) -> str:
    return normalize_arabic_text(normalize_question(text)).strip()


def strip_filler_prefix(text: str) -> str:
    fillers = [
        "by the way",
        "you know",
        "i mean",
        "i guess",
        "anyway",
        "basically",
        "actually",
        "honestly",
        "literally",
        "also",
        "btw",
        "just",
        "or",
        "okay",
        "well",
        "like",
        "look",
        "listen",
        "right",
        "yeah",
        "yep",
        "hey",
        "ok",
        "so",
    ]
    cleaned = (text or "").strip()
    changed = True
    while changed:
        changed = False
        for filler in fillers:
            pattern = r"^\s*" + re.escape(filler) + r"[\s,\.!?:;-]+"
            next_text = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE).strip()
            if next_text != cleaned:
                cleaned = next_text
                changed = True
                break
    return cleaned


def text_has_any(text: str, terms: Sequence[str]) -> bool:
    return any(term in text for term in terms)


def has_fci_lookup_verb(text: str) -> bool:
    lowered = semantic_normalize(text)
    lookup_terms = [
        "show",
        "list",
        "give",
        "get",
        "find",
        "search",
        "return",
        "count",
        "number of",
        "how many",
        "students",
        "student",
        "schedule",
        "timetable",
        "course",
        "courses",
        "subjects",
        "teacher",
        "teaches",
        "instructor",
        "اعرض",
        "هات",
        "جيب",
        "كم",
        "كام",
        "عدد",
        "طلاب",
        "طلبة",
        "الطلاب",
        "جدول",
        "مواد",
        "مقررات",
        "يدرس",
    ]
    return text_has_any(lowered, lookup_terms)


def looks_like_bare_fci_department_query(text: str) -> bool:
    lowered = semantic_normalize(text).strip(" .?!؟")
    if not lowered or not fci_department_code_from_text(lowered):
        return False
    department_names = [
        "data science",
        "information systems",
        "software engineering",
        "computer science",
        "cyber security",
        "cybersecurity",
        "artificial intelligence",
        "داتا ساينس",
        "علم البيانات",
        "علوم البيانات",
        "نظم المعلومات",
        "هندسة البرمجيات",
        "علوم الحاسب",
        "علوم الكمبيوتر",
        "الذكاء الاصطناعي",
        "الامن السيبراني",
        "امن سيبراني",
    ]
    explanatory_prefixes = ("what is ", "what's ", "whats ", "tell me about ", "explain ", "ما هو ", "ما هي ", "ايه ", "اشرح ", "قسم ")
    if lowered in department_names:
        return True
    if any(lowered == f"{prefix}{name}".strip() for prefix in explanatory_prefixes for name in department_names):
        return True
    return not has_fci_lookup_verb(lowered)


def extract_fci_instructor_name(text: str) -> Optional[str]:
    original = re.sub(r"\s+", " ", (text or "").strip())
    if not original:
        return None
    patterns = [
        r"\bwho(?:'s|\s+is)\s+(?:the\s+)?(?:(?:dr|prof|professor|doctor)\.?\s+)?([a-z][a-z\s.'-]{2,})\??$",
        r"\btell\s+me\s+about\s+(?:(?:dr|prof|professor|doctor)\.?\s+)?([a-z][a-z\s.'-]{2,})\??$",
        r"\b(?:dr|prof|professor|doctor)\.?\s+([a-z][a-z\s.'-]{2,})\??$",
        r"(?:من هو|مين|عن)\s+(?:(?:د|د\.|دكتور|استاذ|أستاذ)\s+)?([\u0600-\u06ff\s]{2,})\??$",
        r"(?:د|د\.|دكتور|استاذ|أستاذ)\s+([\u0600-\u06ff\s]{2,})\??$",
    ]
    stop_words = {"teacher", "instructor", "professor", "doctor", "dr", "prof", "course", "class", "schedule", "the", "of", "for"}
    for pattern in patterns:
        match = re.search(pattern, original, flags=re.I)
        if not match:
            continue
        candidate = re.sub(r"[?.!]+$", "", match.group(1)).strip()
        if any(term in semantic_normalize(candidate) for term in ["عميد", "الكلية", "كلية"]):
            continue
        tokens = [token for token in re.split(r"\s+", candidate) if token]
        while tokens and tokens[-1].lower().strip(".") in stop_words:
            tokens.pop()
        while tokens and tokens[0].lower().strip(".") in {"dr", "prof", "doctor", "professor", "د", "دكتور", "استاذ", "أستاذ"}:
            tokens.pop(0)
        candidate = " ".join(tokens).strip()
        if semantic_normalize(candidate).strip(" ?.!؟") in {"انت", "انتي", "حضرتك", "مين انت", "من انت", "انت مين"}:
            continue
        if len(candidate) >= 3 and not fci_department_code_from_text(candidate):
            return candidate
    return None


def is_greeting(text: str) -> bool:
    lowered = semantic_normalize(text).strip(" .?!؟")
    greetings = {
        "hi",
        "hello",
        "hey",
        "hey there",
        "hello there",
        "good morning",
        "good evening",
        "good afternoon",
        "salam",
        "salaam",
        "ahlan",
        "هاي",
        "هلو",
        "اهلا",
        "أهلاً",
        "اهلا بيك",
        "ازيك",
        "عامل ايه",
        "عاملة ايه",
        "اخبارك",
        "هلا",
        "مرحبا",
        "مرحباً",
        "السلام عليكم",
        "وعليكم السلام",
        "صباح الخير",
        "صباح النور",
        "مساء الخير",
    }
    return lowered in greetings


def greeting_response(text: str) -> str:
    return GREETING_AR_RESPONSE if contains_arabic(text) else GREETING_EN_RESPONSE


def status_response(text: str) -> str:
    return STATUS_AR_RESPONSE if contains_arabic(text) else STATUS_EN_RESPONSE


def is_status_check(text: str) -> bool:
    lowered = semantic_normalize(text).strip(" .?!؟")
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered in {
        "hru",
        "hr u",
        "how are you",
        "how r u",
        "how are u",
        "how's it going",
        "hows it going",
        "whats up",
        "what's up",
        "sup",
        "wassup",
        "how do you do",
        "how you doing",
        "how are you doing",
        "كيف حالك",
        "عامل ايه",
        "عاملة ايه",
        "اخبارك",
        "ازيك",
        "ازيك",
        "كيفك",
        "تمام ولا ايه",
    }


def looks_like_schedule_file_request(text: str) -> bool:
    lowered = semantic_normalize(text)
    schedule_terms = ["schedule", "timetable", "جدول"]
    file_terms = ["file", "pdf", "download", "attach", "attachment", "send", "official", "original", "excel", "xlsx", "ملف", "ابعت", "ابعث", "حمل", "تحميل"]
    return text_has_any(lowered, schedule_terms) and text_has_any(lowered, file_terms)


def camelbert_route_hint(text: str) -> Optional[Dict[str, Any]]:
    if os.getenv("BUDDYBOT_ENABLE_CAMELBERT_ARABIC_ROUTER", "1") == "0":
        return None
    try:
        from actions.arabic_camelbert_router import predict_arabic_route

        return predict_arabic_route(text)
    except Exception:
        return None


def looks_like_policy_rag_request(text: str) -> bool:
    lowered = semantic_normalize(text)
    english_terms = [
        "academic warning",
        "warning system",
        "attendance policy",
        "attendance rule",
        "attendance rules",
        "absence policy",
        "absence rule",
        "withdrawal rules",
        "withdrawal",
        "add/drop",
        "registration rules",
        "credit hours system",
        "gpa system",
        "grading system",
        "honors requirements",
        "honours requirements",
        "disciplinary",
        "discipline rules",
        "exam schedule",
        "exam dates",
        "midterm exam",
        "final exam",
        "exam rules",
        "examination system",
        "results announced",
        "student guide",
        "regulation",
        "regulations",
        "bylaw",
        "bylaws",
        "admission requirements",
        "admission documents",
        "required documents",
        "transfer student",
        "transfer requirements",
        "change specialization",
        "change major",
        "study plan",
        "graduation requirements",
        "tuition fees",
        "academic load",
    ]
    arabic_terms = [
        "الغياب",
        "غياب",
        "الحضور",
        "المواظبة",
        "انذار الغياب",
        "الانذار الاكاديمي",
        "انذار اكاديمي",
        "الانسحاب",
        "الحذف",
        "الاضافة",
        "التسجيل",
        "الارشاد",
        "الساعات المعتمدة",
        "نظام الساعات",
        "المعدل التراكمي",
        "التقديرات",
        "الرسوب",
        "غير مكتمل",
        "مرتبة الشرف",
        "تاديب",
        "التاديب",
        "اللائحة",
        "لائحة",
        "قواعد",
        "جدول الامتحانات",
        "مواعيد الامتحانات",
        "امتي الامتحانات",
        "امتى الامتحانات",
        "الميد تيرم",
        "الفاينل",
        "نظام الامتحانات",
        "قواعد الامتحانات",
        "النتايج",
        "شروط القبول",
        "اوراق القبول",
        "الأوراق المطلوبة",
        "الاوراق المطلوبة",
        "التحويل",
        "تغيير التخصص",
        "تغيير المسار",
        "تغيير القسم",
        "التخصص",
        "نظام التخصص",
        "خطة الدراسة",
        "متطلبات التخرج",
        "العبء الدراسي",
        "الرسوم الدراسية",
    ]
    return text_has_any(lowered, english_terms) or text_has_any(lowered, arabic_terms)


def looks_like_unrecognized_policy_request(text: str) -> bool:
    lowered = semantic_normalize(text)
    official_terms = [
        "policy",
        "policies",
        "official form",
        "official forms",
        "complaint",
        "complaints",
        "appeal",
        "appeals",
        "deadline",
        "deadlines",
        "registration deadline",
        "fee",
        "fees",
        "tuition",
        "graduation",
        "graduation requirement",
        "graduation requirements",
        "complain",
        "transfer request",
        "transfer requests",
        "سياسة",
        "سياسات",
        "نموذج",
        "نماذج",
        "شكوى",
        "شكاوى",
        "تظلم",
        "تظلمات",
        "موعد نهائي",
        "مواعيد",
        "رسوم",
        "تخرج",
        "تحويل",
    ]
    return text_has_any(lowered, official_terms) and not looks_like_policy_rag_request(text)


def looks_like_educational_rag_request(text: str) -> bool:
    lowered = semantic_normalize(text)
    if looks_like_bare_fci_department_query(text):
        return True
    department_or_concept_terms = [
        "data science",
        "software engineering",
        "artificial intelligence",
        "cyber security",
        "cybersecurity",
        "computer science",
        "information systems",
        "machine learning",
        "deep learning",
        "rag",
        "docker",
        "github",
        "api",
        "apis",
        "linux",
        "backend",
        "frontend",
    ]
    arabic_department_or_concept_terms = [
        "علم البيانات",
        "الداتا ساينس",
        "هندسة البرمجيات",
        "الذكاء الاصطناعي",
        "الامن السيبراني",
        "علوم الحاسب",
        "نظم المعلومات",
    ]
    educational_verbs = [
        "what is",
        "what's",
        "whats",
        "explain",
        "explain me",
        "tell me about",
        "tell about",
        "define",
        "meaning of",
        "difference between",
        "roadmap",
        "career path",
        "skills",
        "tools should",
        "should learn",
        "should i take",
        "should take",
        "what should i take",
        "what courses should",
        "courses should i take",
        "courses to take",
        "recommended courses",
        "recommend courses",
        "what do students study",
        "what does a student study",
        "what does",
        "study plan",
        "study roadmap",
        "learn for",
        "about the major",
        "about major",
    ]
    arabic_educational_verbs = [
        "ما هو",
        "ما هي",
        "ايه",
        "ايه هو",
        "اشرح",
        "شرح",
        "عرف",
        "يعني ايه",
        "قسم",
        "عن قسم",
        "الفرق بين",
        "ماذا ادرس",
        "ادرس ايه",
        "اخد ايه",
        "مواد ايه",
        "خطة",
        "مسار",
        "كورسات",
    ]
    asks_about_known_topic = text_has_any(lowered, department_or_concept_terms) or text_has_any(
        lowered, arabic_department_or_concept_terms
    )
    educational_patterns = [
        r"\bwhat\s+courses?\s+should\s+i\s+take\b",
        r"\bwhat\s+should\s+i\s+take\b",
        r"\bcourses?\s+(?:to\s+take|should\s+i\s+take|for\s+(?:a\s+)?(?:data science|software engineering|computer science|cyber security|cybersecurity|artificial intelligence|information systems))\b",
        r"\b(?:roadmap|career|skills?|tools?|study\s+plan)\s+(?:for|in)\b",
        r"\bwhat\s+does\s+.*\s+study\b",
    ]
    if asks_about_known_topic and any(re.search(pattern, lowered) for pattern in educational_patterns):
        return True
    if asks_about_known_topic and (
        text_has_any(lowered, educational_verbs) or text_has_any(lowered, arabic_educational_verbs)
    ):
        return True
    if re.search(r"\b(give|show|list|tell)\s+(me\s+)?(the\s+)?(majors?|departments?|specializations?|tracks?)\b", lowered):
        return True
    if re.search(r"\b(what|which)\s+(majors?|departments?|specializations?|tracks?)\b", lowered):
        return True
    if re.search(r"(ما|ايه)\s+(هي\s+)?(اقسام|تخصصات|مسارات)\s+الكلية", lowered):
        return True
    if lowered in {"الاقسام", "الأقسام", "اقسام", "أقسام", "التخصصات", "تخصصات"}:
        return True
    if fci_department_code_from_text(text) and text_has_any(lowered, arabic_educational_verbs + educational_verbs):
        return True
    return False


def has_hard_database_signal(text: str) -> bool:
    lowered = semantic_normalize(text)
    if not lowered:
        return False
    if text_has_any(lowered, ["exam schedule", "exam dates", "midterm exam", "final exam", "exam rules"]):
        return False
    if extract_student_id(text) or fci_extract_course_code(text):
        return True
    if re.search(r"\b(?:student|students|student id|student code)\b", lowered) or text_has_any(lowered, ["طالب", "طلاب", "طلبة", "كود الطالب"]):
        return True
    if text_has_any(lowered, ["gpa", "cgpa", "his gpa", "her gpa", "معدل", "المعدل"]):
        return True
    if text_has_any(lowered, ["schedule", "timetable", "lecture", "lectures", "lab", "labs", "class", "classes", "when is", "where is", "جدول", "محاضرة", "سكشن", "معمل"]):
        return True
    if text_has_any(lowered, ["room", "rooms", "hall", "free room", "available room", "قاعة", "مدرج"]):
        return True
    if text_has_any(lowered, ["who teaches", "teaches", "teacher of", "instructor of", "what courses", "courses by", "subjects by", "مين بيدرس", "بيشرح"]):
        return True
    if fci_department_code_from_text(text) and text_has_any(lowered, ["courses", "subjects", "students", "student", "schedule", "classes", "مواد", "مقررات", "طلاب", "جدول"]):
        return True
    return False


def looks_like_structured_sql_request(text: str) -> bool:
    lowered = semantic_normalize(text)
    if has_hard_database_signal(text):
        return True
    if looks_like_policy_rag_request(text) or looks_like_educational_rag_request(text):
        return False
    if looks_like_result_continuation(text):
        return True
    if extract_student_id(text) or fci_extract_course_code(text):
        return True
    if extract_fci_instructor_name(text):
        return True

    student_terms = ["student", "students", "student records", "student profile", "طالب", "طلبة", "طلاب", "الطلبة", "الطلاب"]
    student_actions = [
        "show",
        "list",
        "give",
        "get",
        "find",
        "search",
        "return",
        "who is in",
        "who's in",
        "how many",
        "count",
        "number of",
        "هات",
        "اعرض",
        "اظهر",
        "جيب",
        "كام طالب",
        "كم طالب",
        "كام",
        "كم",
        "عدد",
    ]
    if text_has_any(lowered, student_terms) and text_has_any(lowered, student_actions):
        return True

    schedule_terms = [
        "schedule",
        "timetable",
        "lecture",
        "lectures",
        "lab",
        "labs",
        "class",
        "classes",
        "محاضرات",
        "سكاشن",
        "جدول",
        "معمل",
    ]
    if text_has_any(lowered, schedule_terms):
        return True

    if text_has_any(lowered, ["free room", "free rooms", "available room", "rooms free", "room", "rooms", "hall"]):
        return True

    if text_has_any(lowered, ["gpa", "cgpa", "my gpa", "his gpa", "her gpa", "student gpa", "معدله", "معدلي"]) and not text_has_any(lowered, ["system", "نظام"]):
        return True

    if text_has_any(lowered, ["my attendance", "attendance record", "absence record", "attendance percentage", "classes did i miss", "حضوري", "سجل حضوري", "كام مرة غبت"]):
        return True

    if text_has_any(lowered, ["grade", "grades", "failed", "fail", "marks", "score", "reset", "repeated", "درجات", "راسب", "رسوب"]):
        return True

    if text_has_any(lowered, ["who teaches", "teacher of", "instructor of", "instructor for", "teaches", "مين بيدرس", "دكتور مادة"]):
        return True

    if text_has_any(lowered, ["courses for", "courses in", "subjects for", "subjects in", "مواد", "مقررات"]):
        return True

    if fci_department_code_from_text(text) and text_has_any(lowered, ["students", "student", "طلبة", "طلاب", "schedule", "جدول", "courses", "مواد"]):
        return True

    return False


def hybrid_route(text: str, tracker: Optional[Tracker] = None) -> Dict[str, Any]:
    if is_gibberish(text):
        return {"route": "conversational", "confidence": 1.0, "reason": "pre-router gibberish guard"}
    if is_greeting(text):
        return {"route": "conversational", "confidence": 1.0, "reason": "pre-router greeting guard"}
    if is_thanks(text):
        return {"route": "conversational", "confidence": 1.0, "reason": "pre-router thank-you guard"}
    if is_conversation_continuation_reply(text):
        return {"route": "conversational", "confidence": 1.0, "reason": "pre-router continuation guard"}
    if is_bot_identity_question(text) or is_fci_identity_query(text):
        return {"route": "conversational", "confidence": 1.0, "reason": "pre-router identity guard"}
    if compound_topic_answer(text) or english_hardcoded_topic_answer(text):
        return {"route": "policy_rag", "confidence": 0.99, "reason": "protected compound/topic phrase"}
    if is_english_intent_opener(text):
        return {"route": "conversational", "confidence": 0.99, "reason": "protected intent opener"}
    if is_unfiltered_schedule_query(text):
        return {"route": "conversational", "confidence": 0.99, "reason": "schedule query needs a filter"}

    if looks_like_result_continuation(text):
        return {"route": "structured_sql", "confidence": 0.98, "reason": "pagination continuation"}

    if looks_like_schedule_file_request(text):
        return {"route": "structured_sql", "confidence": 0.96, "reason": "schedule file request"}

    pending = bool(tracker and has_pending_sql_clarification(tracker))
    if pending and not looks_like_structured_sql_request(text) and not looks_like_policy_rag_request(text) and not looks_like_educational_rag_request(text):
        return {"route": "clarification", "confidence": 0.9, "reason": "pending SQL clarification"}

    if has_hard_database_signal(text):
        return {"route": "structured_sql", "confidence": 0.97, "reason": "hard database/catalog signal"}

    camelbert_hint = camelbert_route_hint(text)
    if camelbert_hint and float(camelbert_hint.get("confidence") or 0.0) >= 0.75:
        return {
            "route": camelbert_hint["route"],
            "confidence": float(camelbert_hint.get("confidence") or 0.0),
            "reason": f"CAMeL-BERT Arabic intent classifier predicted {camelbert_hint.get('label')}",
        }

    if looks_like_policy_rag_request(text):
        return {"route": "policy_rag", "confidence": 0.96, "reason": "policy/regulation language"}
    if looks_like_educational_rag_request(text):
        return {"route": "educational_rag", "confidence": 0.94, "reason": "educational concept/department explanation"}
    if looks_like_structured_sql_request(text):
        return {"route": "structured_sql", "confidence": 0.9, "reason": "structured database language"}
    if camelbert_hint:
        return {
            "route": camelbert_hint["route"],
            "confidence": float(camelbert_hint.get("confidence") or 0.0),
            "reason": f"Low-confidence CAMeL-BERT fallback predicted {camelbert_hint.get('label')}",
        }
    if looks_like_knowledge_question(text):
        return {"route": "educational_rag", "confidence": 0.72, "reason": "knowledge-base language"}
    if looks_like_general_conversation_request(text):
        return {"route": "conversational", "confidence": 0.75, "reason": "general conversation"}
    return {"route": "conversational", "confidence": 0.4, "reason": "safe fallback"}


def looks_like_official_knowledge_request(text: str) -> bool:
    if looks_like_policy_rag_request(text):
        return True
    lowered = semantic_normalize(text)
    arabic_terms = [
        "عميد",
        "الكلية",
        "اقسام",
        "قبول",
        "انذار",
        "لائحة",
        "قواعد",
        "انسحاب",
        "حضور",
        "غياب",
        "الغياب",
        "المواظبة",
        "الساعات المعتمدة",
        "موقع",
        "دليل الطالب",
    ]
    english_terms = [
        "dean",
        "official website",
        "website",
        "student guide",
        "bylaw",
        "bylaws",
        "regulation",
        "regulations",
        "official rules",
        "admission system",
        "withdrawal rules",
        "attendance rules",
        "academic warning",
        "credit hours system",
        "faculty services",
        "faculty of computers",
    ]
    if contains_arabic(text) and any(term in lowered for term in arabic_terms):
        return True
    return any(term in lowered for term in english_terms)


def looks_like_result_continuation(text: str) -> bool:
    lowered = semantic_normalize(text).strip(" .?!؟")
    if not lowered:
        return False

    # A fresh query like "show me all students in data science" is not a
    # pagination continuation. Continuation phrases should be short references
    # to the previous result set.
    fresh_query_terms = [
        "student",
        "students",
        "course",
        "courses",
        "subject",
        "subjects",
        "schedule",
        "lecture",
        "lectures",
        "lab",
        "labs",
        "room",
        "rooms",
        "instructor",
        "instructors",
        "طالب",
        "طلاب",
        "طلبة",
        "مادة",
        "مواد",
        "جدول",
        "محاضرات",
        "سكاشن",
    ]
    if text_has_any(lowered, fresh_query_terms):
        return False

    continuation_pattern = (
        r"(?:show\s+more|more|next|next\s+page|nextt|continue|all\s+of\s+them|"
        r"al\s+of\s+them|all\s+of\s+the|al\s+of\s+the|alll|all|"
        r"the\s+rest|and\s+the\s+rest|rest\s+of\s+them|remaining|"
        r"show\s+(?:me\s+)?(?:the\s+)?(?:\d+\s+)?more|(?:\d+\s+)?more|"
        r"show\s+the\s+rest|show\s+all|show\s+al|all\s+results|"
        r"i\s+want\s+all|want\s+all|give\s+me\s+all)"
    )
    return bool(re.fullmatch(continuation_pattern, lowered)) or lowered in {
        "كلهم",
        "الكل",
        "كله",
        "باقيهم",
        "الباقي",
        "والباقي",
        "والبقية",
        "الباقين",
        "كمل",
        "اكمل",
        "المزيد",
    }


def is_analysis_question(text: str) -> bool:
    lowered = normalize_question(text)
    analysis_terms = [
        "why",
        "analyze",
        "analysis",
        "reason",
        "factors",
        "explain",
        "because",
        "cause",
        "impact",
        "influence",
    ]
    return any(term in lowered for term in analysis_terms)


def looks_like_knowledge_question(text: str) -> bool:
    if extract_student_id(text):
        return False

    if looks_like_policy_rag_request(text) or looks_like_educational_rag_request(text):
        return True

    lowered = semantic_normalize(text)
    knowledge_phrases = [
        "who teaches",
        "faculty",
        "professor",
        "department",
        "departments",
        "major",
        "majors",
        "specialization",
        "specializations",
        "track",
        "tracks",
        "data science",
        "software engineering",
        "artificial intelligence",
        "cyber security",
        "computer science",
        "information systems",
        "subject",
        "subjects",
        "course",
        "courses",
        "college",
        "university",
        "campus",
        "admission",
        "fees",
        "fee structure",
        "library",
        "hostel",
        "scholarship",
        "official website",
        "website",
        "policy",
        "rules",
        "credit hours",
        "withdrawal",
        "dean",
        "bylaw",
        "bylaws",
        "translation",
        "translate",
        "اقسام",
        "أقسام",
        "الكلية",
        "عميد",
        "قبول",
        "انذار",
        "غياب",
        "الحضور",
        "الغياب",
        "الساعات المعتمدة",
        "انسحاب",
        "لائحة",
        "موقع الكلية",
        "aksam",
        "aqsam",
        "koleya",
        "kolia",
        "3ameed",
        "sa3at",
    ]
    analytics_phrases = [
        "attendance",
        "exam",
        "score",
        "marks",
        "student id",
        "studentid",
        "school type",
        "distance",
        "sleep",
        "study",
        "motivation",
        "tutoring",
        "internet",
        "resources",
        "family income",
        "parental",
        "peer influence",
        "teacher quality",
    ]
    official_context = any(
        phrase in lowered
        for phrase in ["official", "website", "policy", "rules", "bylaw", "لائحة", "موقع", "قواعد"]
    )
    return any(phrase in lowered for phrase in knowledge_phrases) and (
        official_context or not any(phrase in lowered for phrase in analytics_phrases)
    )


def clean_sql(raw_sql: str) -> str:
    sql = raw_sql.strip()
    sql = re.sub(r"```(?:sql)?", "", sql, flags=re.IGNORECASE).replace("```", "")
    sql = sql.replace("`", "")
    match = re.search(r"\b(WITH|SELECT)\b", sql, flags=re.IGNORECASE)
    if not match:
        return ""
    sql = sql[match.start():].strip()
    sql = re.split(r";\s*", sql, maxsplit=1)[0].strip()
    return sql


def is_read_only_select(sql: str) -> bool:
    without_comments = re.sub(r"--.*?$|/\*.*?\*/", "", sql, flags=re.MULTILINE | re.DOTALL)
    normalized = without_comments.strip()
    if not re.match(r"^(SELECT|WITH)\b", normalized, flags=re.IGNORECASE):
        return False

    forbidden = (
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|MERGE|EXEC|EXECUTE|"
        r"CREATE|GRANT|REVOKE|BACKUP|RESTORE|USE)\b"
    )
    return re.search(forbidden, normalized, flags=re.IGNORECASE) is None


def format_rows(columns: Sequence[str], rows: Sequence[Any], limit: int = 20) -> str:
    lines = []
    for row in rows[:limit]:
        values = list(row)
        parts = [f"{column}: {value}" for column, value in zip(columns, values)]
        lines.append("; ".join(parts))
    return "\n".join(lines)


def student_list_limit(question: str) -> int:
    lowered = normalize_question(question)
    match = re.search(r"\b(?:give|show|list|get|return)\s+(?:me\s+)?(\d{1,3})\s+students?\b", lowered)
    if not match:
        match = re.search(r"\b(\d{1,3})\s+students?\b", lowered)
    if match:
        return min(max(int(match.group(1)), 1), 500)
    if re.search(r"\ball\s+(?:the\s+)?students?\b", lowered) or re.search(r"\bstudents?\b.*\ball\b", lowered):
        return 500
    if re.search(r"\bstudents?\b", lowered) and fci_department_code_from_text(question):
        return 500
    return 20


def student_initial_page_size(question: str) -> int:
    lowered = normalize_question(question)
    if re.search(r"\b(?:give|show|list|get|return)\s+(?:me\s+)?(\d{1,3})\s+students?\b", lowered) or re.search(r"\b(\d{1,3})\s+students?\b", lowered):
        return min(student_list_limit(question), 50)
    return 10


def rows_to_dicts(columns: Sequence[str], rows: Sequence[Any]) -> List[Dict[str, Any]]:
    return [dict(zip(columns, list(row))) for row in rows]


def legacy_student_cache_events(columns: Sequence[str], rows: Sequence[Any], question: str) -> List[Dict[Text, Any]]:
    if "StudentID" not in columns or "FullName" not in columns or len(rows) <= 1:
        return []
    page_size = student_initial_page_size(question)
    return [
        SlotSet("sql_result_cache", rows_to_dicts(columns, rows)),
        SlotSet(
            "sql_result_plan",
            {
                "domain": "student",
                "operation": "list",
                "filters": {},
                "sort": ["full_name"],
                "limit": len(rows),
                "requested_limit": None,
                "page_size": page_size,
                "confidence": 0.7,
            },
        ),
        SlotSet("sql_result_offset", min(page_size, len(rows))),
        SlotSet("sql_result_page_size", page_size),
    ]


def single_student_id_from_rows(columns: Sequence[str], rows: Sequence[Any]) -> Optional[str]:
    student_id_column = "StudentID" if "StudentID" in columns else "student_id" if "student_id" in columns else None
    if not student_id_column:
        return None
    index = list(columns).index(student_id_column)
    values = {str(row[index]) for row in rows if row[index] is not None}
    if len(values) == 1:
        return values.pop()
    return None


def wants_current_student(text: str) -> bool:
    lowered = normalize_question(text)
    if "that student" in lowered or "this student" in lowered:
        return True
    return bool(re.search(r"\b(he|she|his|her|him|them|their)\b", lowered))


def asks_overall_scope(text: str) -> bool:
    lowered = normalize_question(text)
    return any(
        phrase in lowered
        for phrase in [
            "all students",
            "among all",
            "across all",
            "overall",
            "whole database",
            "entire database",
            "everyone",
        ]
    )


def asks_project_purpose(text: str) -> bool:
    lowered = normalize_question(text)
    return any(
        phrase in lowered
        for phrase in [
            "idea behind",
            "purpose",
            "goal",
            "why was",
            "why did you build",
            "why did u build",
            "why make",
            "why create",
            "why was it created",
            "what problem",
            "what's new",
            "what is new",
            "contribution",
        ]
    ) or lowered.strip() in {"why", "why?", "why tho", "why though"}


def is_thanks(text: str) -> bool:
    lowered = semantic_normalize(text).strip(" .?!؟")
    return bool(
        re.search(
            r"\b(thanks|thank you|thank u|thx|merci|appreciate it|appreciate you)\b",
            lowered,
        )
        or any(
            phrase in lowered
            for phrase in {
                "شكرا",
                "جزاكم الله",
                "الله يكرمك",
                "يسلمو",
                "مشكور",
            }
        )
        or lowered in {
            "ty",
            "cheers",
            "شكرا",
            "شكراً",
            "تمام",
            "ممتاز",
            "حلو",
            "مشكور",
            "جزاكم الله",
            "يسلمو",
            "🙏",
            "👍",
        }
    )


def thanks_response(text: str) -> str:
    return THANKS_AR_RESPONSE if contains_arabic(text) else THANKS_EN_RESPONSE


def guard_clean_text(text: str, *, remove_fillers: bool = False) -> str:
    cleaned = semantic_normalize(text)
    cleaned = re.sub(r"[.,?!;:؟،؛]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    if remove_fillers:
        cleaned = re.sub(
            r"\b(?:just|like|actually|basically|so|well|hey|hi)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def is_question_opener(text: str) -> bool:
    cleaned_variants = {
        guard_clean_text(text),
        guard_clean_text(text, remove_fillers=True),
    }
    english_openers = {
        "ok i have a question",
        "i have a question",
        "i have a query",
        "i got a question",
        "got a question",
        "quick question",
        "can i ask",
        "can i ask something",
        "can i ask you something",
        "i want to ask",
        "i want to ask you",
        "i need to ask",
        "i need to ask you something",
        "i have something to ask",
        "may i ask",
        "let me ask",
        "i was wondering",
        "i wanted to ask",
        "before i ask",
        "just a question",
        "just wondering",
        "one question",
        "quick q",
    }
    english_single_word_openers = {
        "question",
        "query",
        "ok question",
        "so question",
        "yeah question",
        "yes question",
    }
    arabic_openers = {
        "عندي سوال",
        "عندي استفسار",
        "ممكن اسال",
        "عايز اسال",
        "عاوز اسال",
        "لو سمحت سوال",
        "فيه سوال",
        "سوال بس",
        "سوال واحد",
        "استفسار",
    }
    normalized_arabic_openers = {guard_clean_text(item) for item in arabic_openers}
    for cleaned in cleaned_variants:
        if not cleaned:
            continue
        if cleaned in english_single_word_openers or cleaned in normalized_arabic_openers:
            return True
        if any(phrase in cleaned for phrase in english_openers):
            return True
        if any(phrase in cleaned for phrase in normalized_arabic_openers):
            return True
    return False


def question_opener_response(text: str) -> str:
    return QUESTION_OPENER_AR_RESPONSE if contains_arabic(text) else QUESTION_OPENER_EN_RESPONSE


CONVERSATION_CONTINUATION_PHRASES = {
    "not bad",
    "sounds good",
    "cool",
    "nice",
    "great",
    "okay",
    "ok",
    "alright",
    "makes sense",
    "understood",
    "got it",
    "that helps",
    "interesting",
    "i see",
    "sure",
    "of course",
    "why not",
    "yeah",
    "yep",
    "nope",
    "no",
    "yes",
    "aha",
    "oh",
    "hmm",
    "wow",
    "really",
    "seriously",
    "tell me more",
    "more details",
    "details",
    "go on",
    "continue",
    "what else",
    "and then",
    "keep going",
    "more",
    "expand on that",
    "elaborate",
    "explain more",
    "can you explain",
    "not really",
    "kind of",
    "sort of",
    "maybe",
    "i guess",
    "possibly",
    "probably",
    "exactly",
    "precisely",
    "true",
    "fair enough",
    "fair point",
    "good point",
    "i agree",
    "i disagree",
    "i think so",
    "i don't think so",
    "i dont think so",
}


CONVERSATION_TOPIC_REPLIES = {
    "study_tips": (
        "Glad that helps. Want me to go deeper on one technique: Anki/spaced repetition, "
        "Pomodoro, active recall, or building a weekly study schedule?"
    ),
    "time_management": (
        "Sure. The next useful step is to turn your week into time blocks: lectures, "
        "assignments, review, and rest. Want a simple weekly template for 15-18 credit hours?"
    ),
    "stress": (
        "I’m with you. Let’s keep it small: sleep, one manageable task, and asking for help early "
        "beat trying to fix everything tonight. Want a quick recovery plan for this week?"
    ),
    "career": (
        "Nice. We can take it further by picking a target role, then mapping the skills, projects, "
        "CV, and LinkedIn profile around it. Want paths for software, data, AI, cyber, or DevOps?"
    ),
    "tools": (
        "Sure. I can break the tools into beginner, intermediate, and portfolio-ready levels. "
        "Which specialisation do you want to focus on: CS, AI, Cyber Security, ISDS, or SE?"
    ),
    "programming": (
        "Good point. The best next move is to build something small with the concept, not just read it. "
        "Want a beginner project idea or a practice roadmap?"
    ),
    "computer_science": (
        "Absolutely. CS is broad, so the useful next step is choosing one lane: algorithms, systems, "
        "databases, networks, AI, security, or web development. Which one should I unpack?"
    ),
    "general_chat": (
        "Sure, I’m with you. Tell me what direction you want to take this: study help, career advice, "
        "programming, stress, or campus services."
    ),
}


def is_conversation_continuation_reply(text: str) -> bool:
    lowered = semantic_normalize(text).strip(" .?!؟")
    return lowered in CONVERSATION_CONTINUATION_PHRASES


def conversation_topic_for_text(text: str, answer: str = "") -> str:
    query = semantic_normalize(text)
    combined = semantic_normalize(f"{text} {answer}")
    if text_has_any(query, ["انصحني", "نصيحة", "نصيحه", "نصحني", "عاوز اذاكر", "عايز اذاكر", "اذاكر ازاي", "ازاي اذاكر", "مش فاهم", "طريقة المذاكرة", "طريقة المذاكره"]):
        return "study_tips"
    if text_has_any(query, ["ازاي انظم", "عاوز انظم", "عايز انظم", "انظم وقتي", "وقتي بيضيع", "مفيش وقت", "معنديش وقت", "معنديس وقت", "ماعنديش وقت", "ما عنديش وقت", "الوقت بيعدي", "تنظيم الوقت"]):
        return "time_management"
    if text_has_any(query, ["تعبت", "زهقت", "مش قادر اكمل", "مبقتش قادر", "محتاج مساعدة", "محتاج مساعده", "مضغوط", "خايف ارسب", "هرسب", "رسبت"]):
        return "stress"
    if text_has_any(query, ["هعمل ايه", "اعمل ايه", "هشتغل ايه", "في شغل ولا لا", "مش عارف اختار"]):
        return "career"
    if text_has_any(query, ["البرمجة صعبة", "البرمجه صعبه", "مش فاهم كود", "ازاي ابدا", "اتعلم ايه", "ابدأ منين", "ابدا منين"]):
        return "programming"
    if text_has_any(query, ["study", "memorize", "active recall", "spaced repetition", "feynman", "flashcard", "anki", "mind map"]):
        return "study_tips"
    if is_tools_topic_query(text) or "essential tools" in combined:
        return "tools"
    if text_has_any(query, ["time management", "manage my time", "weekly plan", "daily schedule", "procrastination", "pomodoro"]):
        return "time_management"
    if text_has_any(combined, ["stress", "stressed", "burnout", "burnt out", "overwhelmed", "anxiety", "i give up", "too hard", "imposter"]):
        return "stress"
    if text_has_any(combined, ["career", "job", "cv", "resume", "linkedin", "freelance", "internship", "salary", "hired"]):
        return "career"
    if text_has_any(combined, ["computer science", "what is cs", "cs explained", "data structures", "algorithms", "operating systems", "databases", "networks"]):
        return "computer_science"
    if text_has_any(combined, ["programming", "coding", "language", "python", "java", "c++", "javascript", "web development", "git", "github"]):
        return "programming"
    if text_has_any(combined, ["study", "active recall", "spaced repetition", "feynman", "flashcard", "anki", "mind map"]):
        return "study_tips"
    return "general_chat"


def continuation_answer_for_topic(topic: str) -> str:
    return CONVERSATION_TOPIC_REPLIES.get(topic or "", CONVERSATION_TOPIC_REPLIES["general_chat"])


INSTRUCTOR_PROFILE_MORE_PHRASES = {
    "yes",
    "yeah",
    "yep",
    "sure",
    "of course",
    "tell me more",
    "more",
    "more details",
    "details",
    "continue",
    "go on",
    "what else",
}


INSTRUCTOR_PROFILE_NO_PHRASES = {"no", "nope", "not really", "i don't think so", "i dont think so"}


def dispatch_instructor_profile_continuation_answer(
    dispatcher: CollectingDispatcher,
    text: str,
    tracker: Optional[Tracker],
) -> Optional[List[Dict[Text, Any]]]:
    if not tracker:
        return None
    if str(tracker.get_slot("last_entity_type") or "").strip() != "instructor_profile":
        return None

    lowered = semantic_normalize(text).strip(" .?!؟")
    if lowered in INSTRUCTOR_PROFILE_NO_PHRASES:
        dispatcher.utter_message(
            text="No problem. Ask me anytime about their courses, schedule, or any FCI policy."
        )
        return [SlotSet("last_query_scope", "chat"), SlotSet("last_conversation_topic", "general_chat")]

    if lowered not in INSTRUCTOR_PROFILE_MORE_PHRASES:
        return None

    instructor_name = str(tracker.get_slot("instructor_name") or tracker.get_slot("last_topic") or "").strip()
    if not instructor_name or "," in instructor_name:
        dispatcher.utter_message(text="Which instructor do you want the course details for?")
        return [SlotSet("last_query_scope", "course_catalog"), SlotSet("last_clarification_topic", "instructor_courses")]

    display_name, instructor_courses = find_catalog_instructor_courses(instructor_name)
    if not instructor_courses:
        dispatcher.utter_message(text=f"I don't have courses listed for {instructor_name} in the current catalog.")
        return [SlotSet("last_query_scope", "course_catalog")]

    header = f"Courses taught by {display_name}:"
    page_size = 20
    events = course_catalog_cache_events(instructor_courses, header, min(page_size, len(instructor_courses)), page_size)
    events.extend(
        [
            SlotSet("instructor_name", display_name),
            SlotSet("last_topic", display_name),
            SlotSet("last_entity_type", "instructor"),
        ]
    )
    dispatcher.utter_message(text=format_instructor_course_brief_matches(header, instructor_courses, max_results=page_size))
    return events


def is_instructor_profile_course_followup(text: str) -> bool:
    lowered = semantic_normalize(text)
    has_instructor_pronoun = bool(
        re.search(r"\b(?:he|she|his|her|him|they|their)\b", lowered)
        or "that instructor" in lowered
        or "this instructor" in lowered
        or "that doctor" in lowered
        or "this doctor" in lowered
    )
    if not has_instructor_pronoun:
        return False
    return text_has_any(
        lowered,
        [
            "course",
            "courses",
            "subject",
            "subjects",
            "teach",
            "teaches",
            "teaching",
            "what does",
            "what do",
            "مقرر",
            "مقررات",
            "مادة",
            "مواد",
            "يدرس",
            "بيدرس",
            "بيشرح",
        ],
    )


def dispatch_instructor_profile_course_followup_answer(
    dispatcher: CollectingDispatcher,
    text: str,
    tracker: Optional[Tracker],
) -> Optional[List[Dict[Text, Any]]]:
    if not tracker:
        return None
    last_entity_type = str(tracker.get_slot("last_entity_type") or "").strip()
    if last_entity_type not in {"instructor_profile", "instructor"}:
        return None
    if not is_instructor_profile_course_followup(text):
        return None

    instructor_name = str(tracker.get_slot("instructor_name") or tracker.get_slot("last_topic") or "").strip()
    if not instructor_name or "," in instructor_name:
        dispatcher.utter_message(text="Which instructor do you mean?")
        return [SlotSet("last_clarification_topic", "instructor_courses"), SlotSet("last_query_scope", "course_catalog")]

    display_name, instructor_courses = find_catalog_instructor_courses(instructor_name)
    if not instructor_courses:
        dispatcher.utter_message(text=f"I don't have courses listed for {instructor_name} in the current catalog.")
        return [SlotSet("last_query_scope", "course_catalog")]

    header = f"Courses taught by {display_name}:"
    page_size = 20
    events = course_catalog_cache_events(instructor_courses, header, min(page_size, len(instructor_courses)), page_size)
    events.extend(
        [
            SlotSet("instructor_name", display_name),
            SlotSet("last_topic", display_name),
            SlotSet("last_entity_type", "instructor"),
        ]
    )
    dispatcher.utter_message(text=format_instructor_course_brief_matches(header, instructor_courses, max_results=page_size))
    return events


def dispatch_conversation_continuation_answer(
    dispatcher: CollectingDispatcher,
    text: str,
    tracker: Optional[Tracker],
) -> Optional[List[Dict[Text, Any]]]:
    if not is_conversation_continuation_reply(text):
        return None
    instructor_profile_events = dispatch_instructor_profile_continuation_answer(dispatcher, text, tracker)
    if instructor_profile_events is not None:
        return instructor_profile_events
    topic = ""
    if tracker:
        topic = str(tracker.get_slot("last_conversation_topic") or "").strip()
        if not topic:
            topic = conversation_topic_for_text(str(tracker.get_slot("last_topic") or ""))
    if not topic:
        topic = "general_chat"
    dispatcher.utter_message(text=continuation_answer_for_topic(topic))
    return [
        SlotSet("last_query_scope", "chat"),
        SlotSet("last_conversation_topic", topic),
    ]


ARABIC_QUESTION_WORDS = {
    "ما",
    "ماذا",
    "من",
    "كيف",
    "متى",
    "اين",
    "أين",
    "هل",
    "ايه",
    "عايز",
    "عاوزه",
    "محتاج",
    "محتاجه",
    "ممكن",
    "عندي",
    "فين",
}

ARABIC_PREPOSITIONS_AND_ARTICLES = {
    "ال",
    "في",
    "من",
    "على",
    "علي",
    "الى",
    "إلى",
    "عن",
    "مع",
    "هل",
    "لو",
    "لما",
}

ARABIC_SUBSTITUTION_PAIRS = [
    ("ص", "س"),
    ("ن", "م"),
    ("ظ", "ض"),
    ("ذ", "د"),
    ("ث", "س"),
    ("ء", "ا"),
    ("إ", "ا"),
    ("أ", "ا"),
    ("ه", "ة"),
    ("ى", "ي"),
    ("و", "ؤ"),
]


def strip_arabic_article(token: str) -> str:
    normalized = semantic_normalize(token)
    return normalized[2:] if normalized.startswith("ال") and len(normalized) > 3 else normalized


def arabic_one_letter_variants(token: str) -> set[str]:
    variants = {semantic_normalize(token), arabic_typo_normalize(token)}
    pair_map: Dict[str, set[str]] = {}
    for left, right in ARABIC_SUBSTITUTION_PAIRS:
        pair_map.setdefault(left, set()).add(right)
        pair_map.setdefault(right, set()).add(left)
    for index, char in enumerate(token):
        for replacement in pair_map.get(char, set()):
            variants.add(token[:index] + replacement + token[index + 1 :])
    return {strip_arabic_article(variant) for variant in variants if variant}


def arabic_known_topic_roots() -> set[str]:
    roots: set[str] = set()

    def add_text(value: str) -> None:
        for token in re.findall(r"[\u0621-\u063a\u0641-\u064a]+", arabic_typo_normalize(value)):
            root = strip_arabic_article(token)
            if len(root) >= 3:
                roots.add(root)

    for term in ARABIC_HARDCODED_ONLY_TERMS:
        add_text(term)
    for term in ARABIC_SPECIFIC_CORRECTIONS.values():
        add_text(term)
    for token in extended_topic_trigger_words():
        if re.search(r"[\u0621-\u063a\u0641-\u064a]", token):
            add_text(token)
    for item in ARABIC_POLICY_ANSWERS:
        for trigger in item.get("triggers", []):
            add_text(str(trigger))
    return roots


def shares_arabic_sequence(left: str, right: str, length: int = 3) -> bool:
    if len(left) < length or len(right) < length:
        return False
    left_sequences = {left[index : index + length] for index in range(len(left) - length + 1)}
    return any(seq in right for seq in left_sequences)


def has_arabic_known_root_proximity(text: str) -> bool:
    roots = arabic_known_topic_roots()
    tokens = re.findall(r"[\u0621-\u063a\u0641-\u064a]+", arabic_typo_normalize(text))
    for token in tokens:
        base_variants = {
            strip_arabic_article(token),
            strip_arabic_article(arabic_typo_normalize(token)),
        }
        all_variants = arabic_one_letter_variants(strip_arabic_article(token))
        for variant in all_variants:
            if len(variant) < 3:
                continue
            for root in roots:
                if variant == root or variant in root or root in variant:
                    return True
                similarity = SequenceMatcher(None, variant, root).ratio()
                if variant in base_variants and shares_arabic_sequence(variant, root) and (
                    similarity >= 0.50 or abs(len(variant) - len(root)) <= 2
                ):
                    return True
                threshold = 0.78 if variant in base_variants else 0.86
                if len(variant) >= 4 and similarity >= threshold:
                    return True
    return False


def has_arabic_question_word(text: str) -> bool:
    tokens = set(re.findall(r"[\u0621-\u063a\u0641-\u064a]+", semantic_normalize(text)))
    normalized_questions = {semantic_normalize(word) for word in ARABIC_QUESTION_WORDS}
    return bool(tokens & normalized_questions)


def has_arabic_preposition_or_article(text: str) -> bool:
    lowered = semantic_normalize(text)
    tokens = set(re.findall(r"[\u0621-\u063a\u0641-\u064a]+", lowered))
    normalized_terms = {semantic_normalize(word) for word in ARABIC_PREPOSITIONS_AND_ARTICLES}
    return bool(tokens & normalized_terms) or any(token.startswith("ال") and len(token) > 3 for token in tokens)


def is_gibberish(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    if is_greeting(stripped) or is_thanks(stripped) or is_bot_identity_question(stripped) or is_fci_identity_query(stripped):
        return False
    compact_alnum = re.sub(r"[^A-Za-z0-9]", "", stripped).upper()
    if compact_alnum in {"FCI", "SAMS", "GPA", "CGPA", "CS", "AI", "CSCS", "ISDS", "SE", "DS", "SQL", "IT"}:
        return False

    if contains_arabic(stripped):
        if extended_topic_answer(stripped) or arabic_policy_direct_answer(stripped):
            return False
        compact_arabic = re.sub(r"[^\u0621-\u063a\u0641-\u064a]", "", stripped)
        if (
            len(compact_arabic) < 12
            and not has_arabic_known_root_proximity(stripped)
            and not has_arabic_question_word(stripped)
            and not has_arabic_preposition_or_article(stripped)
        ):
            return True
        return False

    meaningful = re.findall(r"[A-Za-z0-9\u0621-\u063a\u0641-\u064a]", stripped)
    if len(meaningful) < 2:
        return True
    if re.search(r"[^A-Za-z0-9\u0621-\u063a\u0641-\u064a\s]{3,}", stripped):
        return True

    lowered = semantic_normalize(stripped)
    compact_english = re.sub(r"[^a-z]", "", lowered)
    if len(compact_english) >= 4:
        vowels = sum(1 for char in compact_english if char in "aeiou")
        consonants = sum(1 for char in compact_english if char in "bcdfghjklmnpqrstvwxyz")
        if vowels == 0 and consonants / max(len(compact_english), 1) > 0.6:
            return True
        keyboard_mashes = (
            "asdf",
            "sdfg",
            "dfgh",
            "fghj",
            "ghjk",
            "hjkl",
            "qwer",
            "wert",
            "erty",
            "uiop",
            "zxcv",
            "xcvb",
            "cvbn",
            "hgj",
            "jhg",
            "kjh",
            "lkj",
        )
        if len(compact_english) <= 10 and any(pattern in compact_english for pattern in keyboard_mashes):
            return True
    return False


def gibberish_response(text: str) -> str:
    return "لم أفهم سؤالك جيداً — ممكن تعيد صياغته؟" if contains_arabic(text) else "I didn't quite get that — could you rephrase your question?"


ABUSE_EN_TERMS = {
    "stupid",
    "idiot",
    "dumb",
    "moron",
    "bitch",
    "bastard",
    "ass",
    "asshole",
    "crap",
    "shit",
    "damn",
    "hell",
    "useless",
    "worthless",
    "fuck",
    "loser",
    "trash",
    "garbage",
    "worst",
    "horrible",
    "terrible",
    "suck",
    "sucks",
    "pathetic",
}

ABUSE_AR_TERMS = {
    "غبي",
    "احمق",
    "أحمق",
    "بليد",
    "متخلف",
    "كلب",
    "حمار",
    "زبالة",
    "تافه",
    "اخرس",
    "اخرسى",
    "اغرب",
    "عديم الفايدة",
}


def is_abusive_input(text: str) -> bool:
    lowered = semantic_normalize(text)
    if text_has_any(lowered, ["hate you", "shut up"]):
        return True
    if text_has_any(lowered, ["روح من هنا", "مش محتاجك"]):
        return True
    if re.search(r"\b(" + "|".join(re.escape(term) for term in ABUSE_EN_TERMS) + r")\b", lowered):
        return True
    return any(term in lowered for term in {semantic_normalize(item) for item in ABUSE_AR_TERMS})


def abuse_response(text: str) -> str:
    return ABUSE_AR_RESPONSE if contains_arabic(text) else ABUSE_EN_RESPONSE


def dispatch_abuse_answer(
    dispatcher: CollectingDispatcher,
    text: str,
) -> Optional[List[Dict[Text, Any]]]:
    if not is_abusive_input(text):
        return None
    dispatcher.utter_message(text=abuse_response(text))
    return [SlotSet("last_query_scope", "chat"), SlotSet("last_conversation_topic", "general_chat")]


def dispatch_question_opener_answer(
    dispatcher: CollectingDispatcher,
    text: str,
) -> Optional[List[Dict[Text, Any]]]:
    if not is_question_opener(text):
        return None
    dispatcher.utter_message(text=question_opener_response(text))
    return [
        SlotSet("last_query_scope", "chat"),
        SlotSet("last_conversation_topic", "general_chat"),
        SlotSet("last_conversation_state", "waiting_for_question"),
    ]


def dispatch_status_answer(
    dispatcher: CollectingDispatcher,
    text: str,
) -> Optional[List[Dict[Text, Any]]]:
    if not is_status_check(text):
        return None
    dispatcher.utter_message(text=status_response(text))
    return [SlotSet("last_query_scope", "chat"), SlotSet("last_conversation_topic", "general_chat")]


def emotional_support_answer(text: str) -> Optional[str]:
    lowered = semantic_normalize(text).strip(" .?!؟")
    is_arabic = contains_arabic(text)

    time_terms = [
        "wasting time",
        "wasting my time",
        "time is wasted",
        "manage my time",
        "organize my time",
        "organise my time",
        "time management",
        "بضيع وقت",
        "بضيع وقتي",
        "وقتي بيضيع",
        "وقتي بيضيع مني",
        "ازاي انظم وقتي",
        "ازاي انظم",
        "انظم وقتي",
        "مش قادر انظم",
        "مفيش وقت",
        "معنديش وقت",
        "معنديس وقت",
    ]
    if text_has_any(lowered, time_terms):
        return WASTING_TIME_AR_RESPONSE if is_arabic else WASTING_TIME_EN_RESPONSE

    help_exact = {
        "help me",
        "i need help",
        "need help",
        "i need some help",
        "can you help me",
        "ساعدني",
        "محتاج مساعدة",
        "محتاج مساعده",
        "عايز مساعدة",
        "عايز مساعده",
        "عاوز مساعدة",
        "عاوز مساعده",
    }
    if lowered in help_exact:
        return HELP_AR_RESPONSE if is_arabic else HELP_EN_RESPONSE

    support_terms = [
        "i'm tired",
        "im tired",
        "i am tired",
        "i'm exhausted",
        "im exhausted",
        "i'm lost",
        "i feel lost",
        "i'm struggling",
        "im struggling",
        "i don't know what to do",
        "i dont know what to do",
        "i'm stressed",
        "im stressed",
        "i'm overwhelmed",
        "im overwhelmed",
        "i give up",
        "i feel like giving up",
        "i'm failing",
        "im failing",
        "i feel like a failure",
        "i'm scared",
        "im scared",
        "i'm anxious",
        "im anxious",
        "i'm worried",
        "im worried",
        "i can't do this",
        "i cant do this",
        "i'm burning out",
        "im burning out",
        "i'm burnt out",
        "im burnt out",
        "everything is going wrong",
        "i feel stuck",
        "i'm not okay",
        "im not okay",
        "this is too much",
        "i can't handle this",
        "i cant handle this",
        "i feel alone",
        "تعبت",
        "انا تعبت",
        "انا تعبان",
        "زهقت",
        "انا زهقت",
        "مش عارف اعمل ايه",
        "خايف",
        "انا خايف",
        "خايف من المستقبل",
        "مش لاقي نفسي",
        "حاسس اني بتضيع",
        "مش قادر اكمل",
        "مبقتش قادر",
        "مضغوط",
        "انا مضغوط",
        "في ضغط كبير",
        "الدراسة صعبة",
        "الدراسه صعبه",
        "مش قادر اذاكر",
        "مش ماشي معايا حاجة",
        "كل حاجة غلط",
        "حاسس اني فاشل",
    ]
    if text_has_any(lowered, support_terms):
        return EMOTIONAL_SUPPORT_AR_RESPONSE if is_arabic else EMOTIONAL_SUPPORT_EN_RESPONSE

    return None


def dispatch_emotional_support_answer(
    dispatcher: CollectingDispatcher,
    text: str,
) -> Optional[List[Dict[Text, Any]]]:
    answer = emotional_support_answer(text)
    if not answer:
        return None
    dispatcher.utter_message(text=answer)
    return [
        SlotSet("last_query_scope", "chat"),
        SlotSet("last_conversation_topic", "stress" if answer in {EMOTIONAL_SUPPORT_EN_RESPONSE, EMOTIONAL_SUPPORT_AR_RESPONSE} else "time_management"),
    ]


def dispatch_gibberish_answer(
    dispatcher: CollectingDispatcher,
    text: str,
) -> Optional[List[Dict[Text, Any]]]:
    if not is_gibberish(text):
        return None
    dispatcher.utter_message(text=gibberish_response(text))
    return [SlotSet("last_query_scope", "chat")]


def is_closing(text: str) -> bool:
    lowered = normalize_question(text).strip(" .?!")
    return bool(
        re.search(
            r"\b(that's all|thats all|that is all|no more|nothing else|done|"
            r"finish|finished|bye|goodbye|see you|stop|exit|end chat)\b",
            lowered,
        )
    )


def is_short_why(text: str) -> bool:
    return normalize_question(text).strip(" .?!") in {"why", "why tho", "why though"}


def looks_like_general_conversation_request(text: str) -> bool:
    lowered = normalize_question(text).strip()

    chat_phrases = [
        "let's chat",
        "lets chat",
        "talk to me",
        "can we talk",
        "normal conversation",
        "conversation with me",
        "be my friend",
        "study buddy",
    ]
    study_advice_phrases = [
        "study tip",
        "study plan",
        "study schedule",
        "study advice",
        "study help",
        "study routine",
        "revision plan",
        "plan my study",
        "plan my day",
        "organize my day",
        "help me study",
        "how should i study",
        "study tips",
        "exam tips",
        "pomodoro",
        "flashcard",
        "note taking",
        "mind map",
        "learning technique",
    ]
    advice_phrases = [
        "advise me",
        "advice",
        "give me advice",
        "give me tips",
        "help me",
        "i need help",
        "i'm lost",
        "im lost",
        "not sure what",
        "what should i do",
        "what do you think",
        "recommend",
        "suggestion",
        "tell me something useful",
        "improve myself",
        "motivate me",
        "i need motivation",
        "motivation",
    ]
    wellbeing_phrases = [
        "don't feel good",
        "dont feel good",
        "do not feel good",
        "not feeling good",
        "i feel bad",
        "i feel lost",
        "stressed",
        "stress",
        "anxious",
        "overwhelmed",
        "burnout",
        "burnt out",
        "tired",
        "can't focus",
        "cant focus",
        "procrastinating",
        "lazy",
        "struggling with",
        "i give up",
        "too hard",
        "this is hard",
    ]
    programming_phrases = [
        "programming help",
        "coding help",
        "cs advice",
        "which language",
        "what language",
        "where to start",
    ]

    return any(
        phrase in lowered
        for phrase in chat_phrases + study_advice_phrases + advice_phrases + wellbeing_phrases + programming_phrases
    )


def creator_response_from_text(text: str) -> Optional[str]:
    lowered = normalize_question(text)
    if re.search(r"\b(?:student|profile|record|show|find|get|search)\b", lowered):
        return None
    if text_has_any(
        semantic_normalize(text),
        ["teach", "teaches", "teaching", "courses", "course", "subjects", "instructor", "faculty", "بيشرح", "بيدرس", "مواد"],
    ):
        return None
    if asks_project_purpose(lowered):
        return PROJECT_WHY_RESPONSE if "why" in lowered else PROJECT_PURPOSE_RESPONSE

    creator_words = [
        "creator",
        "created",
        "made",
        "built",
        "developed",
        "team",
        "supervised",
        "behind",
    ]
    if any(word in lowered for word in creator_words):
        return CREATOR_TEAM_RESPONSE
    return None


def looks_like_fci_database_request(text: str) -> bool:
    lowered = semantic_normalize(text)
    if looks_like_policy_rag_request(text) or looks_like_educational_rag_request(text):
        return False
    if looks_like_official_knowledge_request(text):
        return False
    if looks_like_structured_sql_request(text):
        return True
    if fci_extract_course_code(text):
        return True
    fci_terms = [
        "gpa",
        "cgpa",
        "cumulative",
        "semester",
        "credit",
        "credits",
        "course",
        "courses",
        "subject",
        "subjects",
        "schedule",
        "timetable",
        "class",
        "classes",
        "lecture",
        "lectures",
        "lab",
        "labs",
        "room",
        "instructor",
        "teacher",
        "teaches",
        "taught",
        "professor",
        "faculty",
        "department",
        "departments",
        "major",
        "group",
        "email",
        "code",
        "id",
    ]
    if any(term in lowered for term in fci_terms):
        return True
    return "student" in lowered and any(
        word in lowered
        for word in ["name", "profile", "status", "year", "semester", "group", "email"]
    )


def looks_like_database_request(text: str) -> bool:
    lowered = semantic_normalize(text)
    route_name = hybrid_route(text).get("route")
    if route_name in {"policy_rag", "educational_rag"}:
        return False
    if route_name == "structured_sql":
        return True
    if looks_like_official_knowledge_request(text) and not looks_like_result_continuation(text):
        return False
    if is_closing(lowered) or is_thanks(lowered) or asks_project_purpose(lowered):
        return False
    if looks_like_general_conversation_request(lowered):
        return False
    if looks_like_fci_database_request(lowered):
        return True
    if extract_student_id(lowered):
        return True
    if metric_column_from_question(lowered) or group_expression_from_question(lowered):
        return True
    if "student" in lowered and any(
        word in lowered
        for word in ["show", "list", "tell", "about", "details", "data", "records", "all"]
    ):
        return True
    return bool(
        any(word in lowered for word in ["average", "percent", "percentage", "ratio", "count", "calculate", "calc"])
        and any(
            word in lowered
            for word in [
                "attendance",
                "score",
                "study",
                "sleep",
                "gender",
                "male",
                "female",
                "school",
                "motivation",
                "resource",
                "internet",
            ]
        )
    )


def mentions_student_attribute(text: str) -> bool:
    lowered = normalize_question(text)
    detail_terms = [
        "everything",
        "details",
        "profile",
        "record",
        "data",
        "attendance",
        "exam",
        "score",
        "marks",
        "previous",
        "study",
        "sleep",
        "motivation",
        "tutoring",
        "physical",
        "activity",
        "extracurricular",
        "family",
        "parent",
        "income",
        "education",
        "involvement",
        "internet",
        "resource",
        "teacher",
        "peer",
        "gender",
        "school",
        "distance",
        "disabil",
        "gpa",
        "cgpa",
        "cumulative",
        "department",
        "course",
        "subject",
        "schedule",
        "timetable",
        "group",
        "email",
        "status",
        "semester",
        "year",
        "credit",
        "major",
    ]
    return any(term in lowered for term in detail_terms)


def should_use_context_student(text: str) -> bool:
    lowered = normalize_question(text)
    if extract_student_id(lowered):
        return False
    if re.search(r"\bstudents\b", lowered):
        return False
    if fci_department_code_from_text(lowered) and text_has_any(
        lowered, ["student", "students", "show", "list", "find", "give"]
    ):
        return False
    if asks_overall_scope(lowered) and not wants_current_student(lowered):
        return False
    if wants_current_student(lowered):
        return True
    if any(
        term in lowered
        for term in ["percent", "percentage", "ratio", "average", "how many", "count", "number of", "breakdown"]
    ):
        return False
    if not mentions_student_attribute(lowered):
        return False
    return bool(
        re.search(
            r"^\s*(and\s+)?(what about|how about|what is|what's|tell me|show me|give me|does|did|is)\b",
            lowered,
        )
    )


def looks_like_metric_followup(text: str) -> bool:
    lowered = normalize_question(text)
    if extract_student_id(lowered) or wants_current_student(lowered):
        return False
    if not metric_column_from_question(lowered):
        return False
    return bool(
        re.search(
            r"^\s*(and\s+)?(what about|how about|what's|what is|and the|the)?\s*(the\s+)?"
            r"(attendance|exam|score|marks|study|sleep|tutoring|physical|previous)",
            lowered,
        )
    )


def expand_followup_question(text: str, last_query_scope: Optional[str]) -> str:
    lowered = normalize_question(text)
    if last_query_scope == "aggregate" and looks_like_metric_followup(lowered):
        column = metric_column_from_question(lowered)
        if column == "Attendance":
            return "average attendance"
        if column == "Exam_Score":
            return "average exam score"
        if column == "Hours_Studied":
            return "average study hours"
        if column == "Sleep_Hours":
            return "average sleep hours"
        if column == "Tutoring_Sessions":
            return "average tutoring sessions"
        if column == "Physical_Activity":
            return "average physical activity"
        if column == "Previous_Scores":
            return "average previous score"
    return text


def sql_string(value: Any) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def fci_where(conditions: Sequence[str]) -> str:
    filtered = [condition for condition in conditions if condition]
    return "\nWHERE " + "\n  AND ".join(filtered) if filtered else ""


def fci_student_id_condition(column_ref: str, student_id: str) -> str:
    if len(student_id) >= 7:
        return f"{column_ref} = {sql_string(student_id)}"
    return f"({column_ref} = {sql_string(student_id)} OR {column_ref} LIKE {sql_string('%' + student_id)})"


def resolve_student_id_suffix(text: str) -> Optional[Dict[str, Any]]:
    """Resolve short student IDs before SQL generation to avoid giant substring lists."""

    candidate = extract_student_id(text)
    if not candidate or len(candidate) >= 7:
        return None
    lowered = semantic_normalize(text)
    if not (re.fullmatch(r"\d{2,6}", (text or "").strip()) or text_has_any(lowered, ["student", "id", "code", "طالب", "كود"])):
        return None
    if len(candidate) < 3:
        return {
            "answer": "Please type at least 3 ID digits, or the full student ID, so I can match the right student.",
        }

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if postgres_mode():
            cursor.execute(
                """
                SELECT
                    s.student_id AS StudentID,
                    s.full_name AS FullName,
                    s.group_code AS GroupCode,
                    s.dept_name AS DepartmentName
                FROM v_rasa_students s
                WHERE s.student_id = %s OR s.student_id LIKE %s
                ORDER BY
                    CASE WHEN s.student_id = %s THEN 0 ELSE 1 END,
                    LENGTH(s.student_id),
                    s.student_id
                LIMIT 6
                """,
                (candidate, "%" + candidate, candidate),
            )
        else:
            cursor.execute(
                """
                SELECT TOP 6
                    s.student_id AS StudentID,
                    s.full_name AS FullName,
                    s.group_code AS GroupCode,
                    s.dept_name AS DepartmentName
                FROM v_rasa_students s
                WHERE s.student_id = ? OR s.student_id LIKE ?
                ORDER BY
                    CASE WHEN s.student_id = ? THEN 0 ELSE 1 END,
                    LEN(s.student_id),
                    s.student_id
                """,
                candidate,
                "%" + candidate,
                candidate,
            )
        rows = cursor.fetchall()
    except Exception:
        return None
    finally:
        if conn:
            conn.close()

    if not rows:
        return {"answer": student_not_found_fallback(candidate, text)}
    if len(rows) == 1:
        return {"student_id": str(rows[0][0])}
    if len(rows) <= 5:
        lines = [f"I found more than one student ID ending in {candidate}. Type the full ID to choose:"]
        for row in rows:
            lines.append(f"- {row[0]}: {row[1]} ({row[2]}, {row[3]})")
        return {"answer": "\n".join(lines)}
    return {
        "answer": (
            f"I found several student IDs ending in {candidate}. "
            "Please type more digits or the full student ID."
        )
    }


def rewrite_student_id_suffix(text: str, resolved_student_id: str) -> str:
    candidate = extract_student_id(text)
    if not candidate or candidate == resolved_student_id:
        return text
    return re.sub(rf"\b{re.escape(candidate)}\b", resolved_student_id, text, count=1)


def fci_extract_student_name_words(text: str) -> List[str]:
    original = re.sub(r"\s+", " ", text.strip())
    lowered = normalize_question(original)
    if extract_student_id(original):
        return []
    if re.search(r"\bstudents\b", lowered) and (fci_department_code_from_text(lowered) or re.search(r"\bin\b", lowered)):
        return []

    phrase: Optional[str] = None
    patterns = [
        r"\b(?:name of|named|called)\s+(.+)$",
        r"\bdepartment\s+(?:is\s+)?(.+?)\s+(?:is\s+)?(?:in|at|with)\b",
        r"\bwhat\s+department\s+(.+?)\s+(?:is\s+)?(?:in|at|with)\b",
        r"\b(?:student|profile|record|data)\s+(?:for|of|about)?\s*([a-z][a-z\s.'-]{2,})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if match:
            phrase = match.group(1)
            break

    if (
        not phrase
        and re.search(r"\b(?:gpa|cgpa|cumulative)\b", lowered)
        and not fci_department_code_from_text(lowered)
        and not re.search(r"\b(average|avg|highest|lowest|top|best|min|max|department|group|all|students)\b", lowered)
    ):
        phrase = re.sub(
            r"\b(?:gpa|cgpa|cumulative|show|tell|give|get|check|me|for|of|about|student|profile|record|data|please|pls)\b",
            " ",
            lowered,
        )

    if not phrase:
        return []

    phrase = re.sub(r"\b(?:please|pls|do|u|you|have|a|an|the|student|with|name|of|is|in|at|department|dept|code|id|number)\b", " ", phrase)
    words = [
        word
        for word in re.findall(r"[a-z]+", phrase.lower())
        if len(word) > 1
        and word
        not in {
            "what",
            "which",
            "show",
            "tell",
            "me",
            "about",
            "for",
            "his",
            "her",
            "him",
            "he",
            "she",
            "their",
            "them",
        }
    ]
    return words[:5]


def fci_student_name_conditions(words: Sequence[str], alias: str = "s") -> List[str]:
    return [f"LOWER({alias}.full_name) LIKE {sql_string('%' + word.lower() + '%')}" for word in words]


STUDENT_NAME_STOP_WORDS = {
    "show",
    "me",
    "find",
    "get",
    "check",
    "search",
    "tell",
    "about",
    "student",
    "profile",
    "record",
    "data",
    "named",
    "called",
    "name",
    "of",
    "who",
    "is",
    "whos",
    "please",
    "pls",
}

CREATOR_STUDENT_IDS_BY_NAME = {
    "mazen mohamed": "2122209",
    "mazen mohamed abdelmageed": "2122209",
    "sama waleed": "2122188",
    "sama waleed hussein": "2122188",
    "jonier hany": "2122163",
    "jonier hany fokeeh": "2122163",
    "aliaa amr": "2122240",
    "aliaa amr hamed": "2122240",
    "abdullah mohamed": "2122224",
    "abdullah mohamed abdelhamed": "2122224",
}


def normalize_person_name_tokens(value: str) -> List[str]:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = semantic_normalize(normalized)
    normalized = re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", normalized)
    return [
        token
        for token in normalized.split()
        if len(token) > 1 and token not in STUDENT_NAME_STOP_WORDS
    ]


def extract_student_name_lookup_phrase(text: str) -> Optional[str]:
    if extract_student_id(text):
        return None
    lowered = semantic_normalize(text).strip(" ?.!/")
    if contains_arabic(text):
        return None
    if not lowered or re.search(r"\bstudents\b", lowered):
        return None
    if wants_current_student(lowered):
        return None
    if fci_department_code_from_text(text) or text_has_any(
        lowered,
        [
            "course",
            "courses",
            "subject",
            "subjects",
            "schedule",
            "timetable",
            "gpa",
            "cgpa",
            "department",
            "major",
            "teacher",
            "teaches",
            "instructor",
            "policy",
            "fees",
            "attendance",
            "warning",
            "email",
            "mail",
            "group",
            "year",
            "semester",
            "status",
        ],
    ):
        return None

    trigger_patterns = [
        r"\b(?:show|find|get|check|search)\s+(?:me\s+)?(?:student|profile|record)\s+(.+)$",
        r"\btell\s+me\s+about\s+(?:student\s+)?(.+)$",
        r"\bstudent\s+(.+)$",
        r"\b(?:who(?:'s|\s+is)|who is)\s+(.+)$",
        r"\b(?:named|called|name of)\s+(.+)$",
    ]
    for pattern in trigger_patterns:
        match = re.search(pattern, lowered, flags=re.I)
        if match:
            phrase = match.group(1).strip(" ?.!/")
            tokens = normalize_person_name_tokens(phrase)
            return " ".join(tokens) if len(tokens) >= 2 else None

    tokens = normalize_person_name_tokens(lowered)
    if 2 <= len(tokens) <= 5 and not re.search(r"\b(what|why|how|when|where|which|can|do|does)\b", lowered):
        return " ".join(tokens)
    return None


def find_student_rows_by_name_tokens(tokens: Sequence[str]) -> List[Dict[str, Any]]:
    if len(tokens) < 2:
        return []
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                s.student_id AS StudentID,
                s.full_name AS FullName,
                s.email AS Email,
                s.current_year AS CurrentYear,
                s.current_semester AS CurrentSemester,
                s.group_code AS GroupCode,
                s.dept_code AS DepartmentCode,
                s.dept_name AS DepartmentName,
                st.status AS Status,
                g.third_year_cumulative_gpa AS ThirdYearCumulativeGPA,
                g.cumulative_gpa AS CumulativeGPA
            FROM v_rasa_students s
            JOIN Students st ON st.student_id = s.student_id
            LEFT JOIN v_rasa_student_gpa g ON g.student_id = s.student_id
            ORDER BY s.full_name
            """
        )
        columns = cursor_column_names(cursor)
        rows = [dict(zip(columns, list(row))) for row in cursor.fetchall()]
    except Exception:
        return []
    finally:
        if conn:
            conn.close()

    query_tokens = [token.lower() for token in tokens if token]
    matches: List[Dict[str, Any]] = []
    for row in rows:
        name_tokens = set(normalize_person_name_tokens(str(row.get("FullName") or "")))
        if all(token in name_tokens for token in query_tokens):
            matches.append(row)
    return matches


def student_name_lookup_result(text: str) -> Optional[Dict[str, Any]]:
    phrase = extract_student_name_lookup_phrase(text)
    if not phrase:
        return None
    tokens = normalize_person_name_tokens(phrase)
    rows = find_student_rows_by_name_tokens(tokens)
    display_name = " ".join(token.capitalize() for token in tokens)

    if not rows:
        return {
            "handled": True,
            "answer": student_not_found_fallback(display_name, text),
            "events": [SlotSet("last_query_scope", "student")],
        }
    phrase_key = " ".join(tokens)
    preferred_student_id = CREATOR_STUDENT_IDS_BY_NAME.get(phrase_key)
    if preferred_student_id:
        preferred_rows = [row for row in rows if str(row.get("StudentID") or "") == preferred_student_id]
        if preferred_rows:
            rows = preferred_rows
    if len(rows) == 1:
        row = rows[0]
        columns = list(row.keys())
        values = [tuple(row[column] for column in columns)]
        student_id = str(row.get("StudentID") or "")
        return {
            "handled": True,
            "answer": answer_from_rows(columns, values, text, row_limit=1),
            "events": [
                SlotSet("student_id", student_id),
                SlotSet("student_name", str(row.get("FullName") or "")),
                SlotSet("group_code", str(row.get("GroupCode") or "")),
                SlotSet("department_code", str(row.get("DepartmentCode") or "")),
                SlotSet("last_query_scope", "student"),
                SlotSet("last_topic", student_id),
                SlotSet("last_entity_type", "student"),
            ],
        }

    lines = [f"I found multiple students named like {display_name}:"]
    for row in rows[:5]:
        lines.append(
            f"- {row.get('FullName')} (StudentID {row.get('StudentID')}), "
            f"group {row.get('GroupCode')}, {row.get('DepartmentName')}"
        )
    lines.append("Type the full name or student ID to choose the right one.")
    return {
        "handled": True,
        "answer": "\n".join(lines),
        "events": [SlotSet("last_query_scope", "student")],
    }


def dispatch_student_name_lookup_answer(
    dispatcher: CollectingDispatcher,
    text: str,
) -> Optional[List[Dict[Text, Any]]]:
    result = student_name_lookup_result(text)
    if not result:
        return None
    dispatcher.utter_message(text=str(result.get("answer") or ""))
    return result.get("events") or [SlotSet("last_query_scope", "student")]


def fci_extract_academic_year(text: str) -> Optional[int]:
    match = re.search(r"\b(20\d{2})\b", text)
    return int(match.group(1)) if match else None


def fci_extract_semester(text: str) -> Optional[int]:
    lowered = normalize_question(text)
    if re.search(r"\b(first|1st)\s+(semester|term)\b", lowered):
        return 1
    if re.search(r"\b(second|2nd)\s+(semester|term)\b", lowered):
        return 2
    match = re.search(r"\b(?:semester|term|sem)\s*(?:number|no\.?)?\s*([12])\b", lowered)
    if match:
        return int(match.group(1))
    return None


def fci_extract_year_level(text: str) -> Optional[int]:
    lowered = normalize_question(text)
    word_years = {
        "first": 1,
        "1st": 1,
        "second": 2,
        "2nd": 2,
        "third": 3,
        "3rd": 3,
        "fourth": 4,
        "4th": 4,
    }
    for word, value in word_years.items():
        if re.search(rf"\b{word}\s+(?:year|level)\b", lowered):
            return value
    match = re.search(r"\b(?:year|level)\s*([1-4])\b", lowered)
    return int(match.group(1)) if match else None


def fci_extract_day(text: str) -> Optional[str]:
    days = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    lowered = normalize_question(text)
    for day in days:
        if re.search(rf"\b{day.lower()}\b", lowered):
            return day
    return None


def fci_extract_course_code(text: str) -> Optional[str]:
    match = re.search(r"\b[A-Z]{2,5}\d{3}\b", text.upper())
    return match.group(0) if match else None


def fci_department_code_from_text(text: str) -> Optional[str]:
    lowered = semantic_normalize(text)
    if "cyber" in lowered:
        return "CSCS"
    if "data science" in lowered or "داتا ساينس" in lowered or "علم البيانات" in lowered or "علوم البيانات" in lowered:
        return "ISDS"
    if "software" in lowered or "هندسة البرمجيات" in lowered or "سوفتوير" in lowered:
        return "SE"
    if "artificial intelligence" in lowered or "الذكاء الاصطناعي" in lowered or "ذكاء اصطناعي" in lowered:
        return "AI"
    if "علوم الحاسب" in lowered or "علوم الكمبيوتر" in lowered:
        return "CS"
    if "الامن السيبراني" in lowered or "امن سيبراني" in lowered:
        return "CSCS"
    upper = text.upper()
    for code in ["CSCS", "ISDS", "AI", "SE", "CS", "DS"]:
        if re.search(rf"\b{code}\b", upper):
            return "ISDS" if code == "DS" else code
    return None


def fci_group_values_from_text(text: str) -> List[str]:
    upper = text.upper()
    values: List[str] = []

    for match in re.finditer(r"\b([123]A)\b", upper):
        values.append(match.group(1))

    for match in re.finditer(r"\bAI\s*([12])\b", upper):
        values.append(f"AI {match.group(1)}")

    for match in re.finditer(r"\b(CSCS|ISDS|SE|CS|DS)\s*([123])\b", upper):
        values.append(match.group(1) + match.group(2))

    for match in re.finditer(r"\b(AI|CSCS|ISDS|SE|CS|DS)\b", upper):
        value = match.group(1)
        values.append("ISDS" if value == "DS" else value)

    unique_values = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return unique_values


def fci_extract_group_code(text: str) -> Optional[str]:
    values = fci_group_values_from_text(text)
    return values[0] if values else None


def fci_student_conditions(text: str, alias: str = "s", include_student_id: bool = True) -> List[str]:
    lowered = normalize_question(text)
    conditions: List[str] = []

    if include_student_id:
        student_id = extract_student_id(text)
        if student_id:
            conditions.append(fci_student_id_condition(f"{alias}.student_id", student_id))

    year_level = fci_extract_year_level(text)
    if year_level:
        conditions.append(f"{alias}.current_year = {year_level}")

    semester = fci_extract_semester(text)
    if semester:
        conditions.append(f"{alias}.current_semester = {semester}")

    group_values = fci_group_values_from_text(text)
    group_conditions = []
    for group_value in group_values:
        if group_value == "AI":
            group_conditions.append(f"{alias}.group_code LIKE 'AI%'")
        elif group_value == "ISDS":
            group_conditions.append(f"{alias}.group_code IN ('DS', 'ISDS', 'ISDS1', 'ISDS2')")
        elif group_value == "CS":
            group_conditions.append(f"{alias}.group_code = 'CS'")
        else:
            group_conditions.append(f"{alias}.group_code = {sql_string(group_value)}")
    if group_conditions:
        conditions.append("(" + " OR ".join(group_conditions) + ")")

    department_code = fci_department_code_from_text(text)
    if department_code and not group_conditions:
        conditions.append(f"{alias}.dept_code = {sql_string(department_code)}")

    return conditions


def fci_schedule_group_conditions(text: str, alias: str = "sch") -> List[str]:
    conditions = []
    for group_value in fci_group_values_from_text(text):
        candidates = [group_value]
        if group_value.startswith("AI"):
            candidates.append("AI")
        if group_value.startswith("ISDS") or group_value == "DS":
            candidates.extend(["ISDS", "DS"])
        if group_value.startswith("CSCS"):
            candidates.extend(["CSCS", group_value])
        if group_value.startswith("SE"):
            candidates.extend(["SE", group_value])
        if group_value.startswith("CS") and not group_value.startswith("CSCS"):
            candidates.extend(["CS", group_value])

        escaped = [sql_string(candidate) for candidate in sorted(set(candidates))]
        conditions.append(f"{alias}.target_group IN ({', '.join(escaped)})")

    if conditions:
        return ["(" + " OR ".join(conditions) + ")"]
    return []


def fci_course_phrase_from_question(text: str) -> Optional[str]:
    lowered = normalize_question(text)
    patterns = [
        r"\b(?:who teaches|which instructor teaches|which faculty teaches|teacher for|instructor for)\s+(.+)$",
        r"\b(?:what\s+is|what's|whats)\s+(?:the\s+)?time\s+(?:of|for)\s+(.+?)(?:\s+(?:lecture|class|lab))?\??$",
        r"\b(?:when\s+is|when's|when\s+are)\s+(.+?)(?:\s+(?:lecture|class|lab))?\??$",
        r"\b(?:time|timing)\s+(?:of|for)\s+(.+?)(?:\s+(?:lecture|class|lab))?\??$",
        r"\b(?:schedule|timetable|classes|lectures|labs|room|when|where)\s+(?:for|of|is|are)?\s*(.+)$",
        r"\b(?:course|subject)\s+(?:called|named|about|for)?\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        phrase = match.group(1).strip(" ?.!")
        phrase = re.sub(r"\b(on|in|for|during)\s+(saturday|sunday|monday|tuesday|wednesday|thursday|friday)\b", "", phrase)
        phrase = re.sub(r"\b(first|second|1st|2nd)\s+(semester|term)\b", "", phrase)
        phrase = re.sub(r"\b(year|level)\s+[1-4]\b", "", phrase)
        phrase = re.sub(r"\b(group|department|major)\b", "", phrase).strip()
        phrase = re.sub(r"\b(lecture|class|lab|time|timing)\b", "", phrase).strip()
        if not phrase or phrase in {"all", "available", "the", "me"}:
            continue
        if phrase.upper() in set(fci_group_values_from_text(phrase)):
            continue
        return phrase
    return None


def fci_catalog_helpers_available() -> bool:
    return bool(
        find_courses_by_keyword
        and find_courses_by_instructor
        and format_course_answer
        and get_department
        and get_courses_by_dept
    )


def clean_fci_catalog_phrase(phrase: str) -> str:
    cleaned = semantic_normalize(phrase or "").strip(" ?.!؟:")
    cleaned = re.sub(r"\b(the|a|an|course|subject|class|lecture|lab|details?|info|information)\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned in {"it", "me", "him", "her", "them", "us", "that", "this", "there"}:
        return ""
    aliases = {
        "ai": "artificial intelligence",
        "a i": "artificial intelligence",
        "ds": "data science",
        "isds": "data science",
        "se": "software engineering",
        "cscs": "cyber security",
    }
    cleaned = aliases.get(cleaned, cleaned)
    if len(cleaned) < 3:
        return ""
    return cleaned


def extract_course_info_phrase(text: str) -> Optional[str]:
    lowered = normalize_question(text)
    patterns = [
        r"\b(?:what\s+is|what's|whats|tell\s+me\s+about|explain|describe)\s+(?:the\s+)?(.+?)(?:\s+course)?\??$",
        r"\b(?:course|subject|class)\s+(?:called|named|about|for)?\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered, flags=re.I)
        if match:
            phrase = clean_fci_catalog_phrase(match.group(1))
            if phrase:
                return phrase
    return None


def extract_teacher_subject_phrase(text: str) -> Optional[str]:
    lowered = normalize_question(text)
    patterns = [
        r"\b(?:who\s+teaches|who\s+is\s+teaching|who's\s+teaching|which\s+instructor\s+teaches|teacher\s+for|instructor\s+for|دكتور\s+مادة|مين\s+بيدرس)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered, flags=re.I)
        if match:
            phrase = clean_fci_catalog_phrase(match.group(1))
            if phrase:
                return phrase
    return None


def is_course_catalog_intent(text: str) -> bool:
    lowered = semantic_normalize(text)
    if fci_extract_course_code(text):
        return True
    if extract_teacher_subject_phrase(text):
        return True
    if extract_fci_instructor_name(text):
        return True
    if fci_department_code_from_text(text) and text_has_any(
        lowered,
        ["courses", "course list", "subjects", "curriculum", "study plan", "مواد", "مقررات", "كورسات"],
    ):
        return True
    if extract_course_info_phrase(text) and (
        text_has_any(lowered, ["course", "subject", "class", "مادة", "مقرر", "كورس"])
        or bool(fci_extract_course_code(text))
    ):
        return True
    return False


def format_department_catalog_answer(dept_code: str) -> Optional[str]:
    if not get_department:
        return None
    department = get_department(dept_code)
    if not department:
        return None
    courses = get_courses_by_dept(dept_code) if get_courses_by_dept else []
    lines = [
        f"{department.get('name', dept_code)} ({dept_code})",
        str(department.get("description") or "").strip(),
    ]
    if courses:
        lines.append(f"The catalog currently has {len(courses)} major courses for this department.")
    return "\n".join(line for line in lines if line)


def format_fci_catalog_course_matches(
    header: str,
    courses: Sequence[Dict[str, Any]],
    max_results: int = 5,
    offset: int = 0,
) -> str:
    if not format_course_answer:
        return ""
    total = len(courses)
    start_index = max(offset, 0)
    end_index = min(start_index + max_results, total)
    shown = courses[start_index:end_index]
    parts = [header]
    if total:
        parts.append(f"Showing courses {start_index + 1}-{end_index} of {total}.")
    for course in shown:
        code = str(course.get("code") or "").upper()
        if code:
            parts.append(format_course_answer(code))
    if end_index < total:
        parts.append('Say "next" or "show more" to continue.')
    return "\n\n".join(part for part in parts if part)


def format_instructor_course_brief_matches(
    header: str,
    courses: Sequence[Dict[str, Any]],
    max_results: int = 20,
    offset: int = 0,
) -> str:
    total = len(courses)
    start_index = max(offset, 0)
    end_index = min(start_index + max_results, total)
    shown = courses[start_index:end_index]
    parts = [header]
    if total:
        parts.append(f"Showing courses {start_index + 1}-{end_index} of {total}.")
    for course in shown:
        code = str(course.get("code") or "").upper()
        name = str(course.get("name") or code).strip()
        dept = str(course.get("dept") or "").upper()
        year = str(course.get("year") or "?")
        semester = str(course.get("semester") or "?")
        parts.append(f"- {name} ({code}) — Year {year}, Semester {semester}, {dept}")
    if end_index < total:
        parts.append('Say "next" or "show more" to continue.')
    return "\n".join(part for part in parts if part)


def rank_fci_catalog_courses(query: str, courses: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    q = clean_fci_catalog_phrase(query)
    ranked = []
    for course in courses:
        code = str(course.get("code") or "").lower()
        name = semantic_normalize(str(course.get("name") or ""))
        keywords = [semantic_normalize(str(keyword)) for keyword in course.get("keywords", [])]
        description = semantic_normalize(str(course.get("description") or ""))
        score = 0
        if q == code:
            score = 120
        elif q == name:
            score = 110
        elif q and q in name:
            score = 100
        elif q and any(q == keyword for keyword in keywords):
            score = 90
        elif q and any(q in keyword for keyword in keywords):
            score = 75
        elif len(q) >= 6 and q in description:
            score = 55
        ranked.append((score, course))
    ranked.sort(
        key=lambda item: (
            -item[0],
            int(item[1].get("year") or 0),
            int(item[1].get("semester") or 0),
            str(item[1].get("code") or ""),
        )
    )
    if ranked and ranked[0][0] >= 100:
        cutoff = ranked[0][0] - 20
        ranked = [item for item in ranked if item[0] >= cutoff]
    return [course for _, course in ranked]


INSTRUCTOR_TITLE_RE = re.compile(
    r"\b(?:dr|doctor|prof|professor|assistant\s+prof|assistant|assist|mr|ms|mrs|miss|eng|engineer|د|د\.|دكتور|استاذ|أستاذ)\.?\s+",
    flags=re.I,
)


def normalize_instructor_lookup_name(name: str) -> str:
    cleaned = semantic_normalize(name or "")
    cleaned = INSTRUCTOR_TITLE_RE.sub(" ", cleaned)
    cleaned = re.sub(r"[^a-z0-9\u0600-\u06ff\s]", " ", cleaned)
    replacements = {
        "yacoub": "yakoub",
        "mohy": "mohey",
        "mohy": "mohey",
        "bahi": "bahai",
        "bahy": "bahai",
        "zayn": "zain",
        "essmat": "esmat",
        "sabri": "sabry",
    }
    for wrong, right in replacements.items():
        cleaned = re.sub(rf"\b{wrong}\b", right, cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def known_catalog_instructor_names() -> List[str]:
    names: List[str] = []
    for course in (COURSES or {}).values():
        for instructor in course.get("instructors", []) or []:
            if instructor and instructor not in names:
                names.append(str(instructor))
    return names


def find_catalog_instructor_courses(name: str) -> tuple[str, List[Dict[str, Any]]]:
    if not find_courses_by_instructor:
        return name, []
    display_name = re.sub(r"\s+", " ", INSTRUCTOR_TITLE_RE.sub(" ", name or "")).strip()
    courses = find_courses_by_instructor(display_name)
    if courses:
        query_norm = normalize_instructor_lookup_name(display_name)
        for course in courses:
            for instructor in course.get("instructors", []) or []:
                instructor_norm = normalize_instructor_lookup_name(str(instructor))
                if query_norm and (query_norm in instructor_norm or instructor_norm in query_norm):
                    return str(instructor), courses
        return display_name, courses

    query_norm = normalize_instructor_lookup_name(display_name)
    if not query_norm:
        return display_name, []

    best_name = ""
    best_score = 0.0
    query_tokens = set(query_norm.split())
    for instructor in known_catalog_instructor_names():
        instructor_norm = normalize_instructor_lookup_name(instructor)
        if not instructor_norm:
            continue
        score = SequenceMatcher(None, query_norm, instructor_norm).ratio()
        instructor_tokens = set(instructor_norm.split())
        if query_tokens and query_tokens.issubset(instructor_tokens):
            score = max(score, 0.96)
        if instructor_norm in query_norm or query_norm in instructor_norm:
            score = max(score, 0.92)
        if score > best_score:
            best_name = instructor
            best_score = score

    if best_name and best_score >= 0.80:
        return best_name, find_courses_by_instructor(best_name)
    return display_name, []


INSTRUCTOR_PROFILE_DATA: Dict[str, Dict[str, Any]] = {
    "antony_noshy": {
        "display": "Dr. Antony Noshy",
        "catalog_name": "Antony Noshy",
        "aliases": ["antony", "antony noshy", "انطوني", "انطوني نصحي", "أنطوني", "أنطوني نصحي"],
        "en": (
            "Dr. Antony Noshy\n"
            "Faculty Member — Faculty of Computers and Information, Sadat Academy for Management Sciences.\n\n"
            "Dr. Antony Noshy contributes to teaching, research, and academic development at SAMS. "
            "Through his work in higher education, he supports the preparation of future computing "
            "and information-systems professionals."
        ),
        "ar": (
            "د. أنطوني نصحي\n"
            "عضو هيئة تدريس — كلية الحاسبات والمعلومات، أكاديمية السادات للعلوم الإدارية.\n\n"
            "د. أنطوني نصحي يساهم في التدريس والبحث العلمي والتطوير الأكاديمي، ويدعم إعداد "
            "كوادر مهنية مستقبلية في مجالات الحاسبات ونظم المعلومات."
        ),
    },
    "wael_karam": {
        "display": "Dr. Wael Karam Hanna",
        "catalog_name": "Wael Karam",
        "aliases": ["wael", "wael karam", "wael karam hanna", "dr wael", "وائل", "وائل كرم", "وائل كرم حنا", "د وائل", "دكتور وائل"],
        "en": (
            "Dr. Wael Karam Hanna\n"
            "Assistant Professor — Faculty of Computers and Information, Sadat Academy for Management Sciences.\n\n"
            "Specialisation: Data Science, Artificial Intelligence, Machine Learning, and Data Mining. "
            "His interests include predictive analytics, intelligent decision-support systems, "
            "educational analytics, and healthcare informatics. He also supervised the BuddyBot "
            "graduation project."
        ),
        "ar": (
            "د. وائل كرم حنا\n"
            "أستاذ مساعد — كلية الحاسبات والمعلومات، أكاديمية السادات للعلوم الإدارية.\n\n"
            "تخصصه يشمل علوم البيانات والذكاء الاصطناعي والتعلم الآلي وتنقيب البيانات، ومن اهتماماته "
            "التحليلات التنبؤية ونظم دعم القرار الذكية والتحليلات التعليمية والمعلوماتية الصحية. "
            "كما أشرف على مشروع التخرج BuddyBot."
        ),
    },
    "badria_nabil": {
        "display": "Dr. Badria Nabil",
        "catalog_name": "Badria Nabil",
        "aliases": ["badria", "badria nabil", "vice dean", "وكيل الكلية", "نائب العميد", "بدرية", "بدرية نبيل"],
        "en": (
            "Dr. Badria Nabil\n"
            "Vice Dean — Faculty of Computers and Information, Sadat Academy for Management Sciences.\n\n"
            "Dr. Badria Nabil plays a senior academic leadership role in FCI, supporting academic "
            "administration, student affairs, and the development of the faculty's educational mission."
        ),
        "ar": (
            "د. بدرية نبيل\n"
            "وكيل كلية الحاسبات والمعلومات — أكاديمية السادات للعلوم الإدارية.\n\n"
            "تقوم د. بدرية نبيل بدور قيادي أكاديمي داخل الكلية، وتدعم الإدارة الأكاديمية وشؤون الطلاب "
            "وتطوير رسالة الكلية التعليمية."
        ),
    },
    "mostafa_yakoub": {
        "display": "Dr. Mostafa Yacoub",
        "catalog_name": "Mostafa Yakoub",
        "aliases": ["mostafa", "mostafa yacoub", "mostafa yakoub", "mustafa yacoub", "مصطفى يعقوب", "مصطفي يعقوب"],
        "en": (
            "Dr. Mostafa Yacoub\n"
            "Faculty Member — Faculty of Computers and Information, Sadat Academy for Management Sciences.\n\n"
            "Research focus: Data Mining, Machine Learning, Information Systems, and Intelligent "
            "Data Analytics. He contributes to teaching and applied research in data-driven systems."
        ),
        "ar": (
            "د. مصطفى يعقوب\n"
            "عضو هيئة تدريس — كلية الحاسبات والمعلومات، أكاديمية السادات للعلوم الإدارية.\n\n"
            "يركز بحثياً على تنقيب البيانات والتعلم الآلي ونظم المعلومات والتحليلات الذكية، ويساهم "
            "في التدريس والبحث التطبيقي في الأنظمة المعتمدة على البيانات."
        ),
    },
    "maha_talaat": {
        "display": "Prof. Maha Talaat",
        "catalog_name": "Maha Talaat",
        "aliases": ["maha", "maha talaat", "prof maha", "مها طلعت", "أستاذة مها", "د مها"],
        "en": (
            "Prof. Maha Talaat\n"
            "Professor of Information Systems and Computer Science — Sadat Academy for Management Sciences.\n\n"
            "Her work spans information systems, digital transformation, e-learning, e-banking, "
            "and sustainable development, with a focus on applying technology to institutional and "
            "business challenges."
        ),
        "ar": (
            "أ.د. مها طلعت\n"
            "أستاذ نظم المعلومات وعلوم الحاسب — أكاديمية السادات للعلوم الإدارية.\n\n"
            "تشمل اهتماماتها نظم المعلومات والتحول الرقمي والتعليم الإلكتروني والخدمات المصرفية "
            "الإلكترونية والتنمية المستدامة، مع التركيز على توظيف التكنولوجيا في حل تحديات المؤسسات."
        ),
    },
    "christina_albert": {
        "display": "Prof. Christina Albert",
        "catalog_name": "Christina Albert",
        "aliases": ["christina", "christina albert", "dean", "dean of fci", "عميد", "عميدة", "كريستينا", "كريستينا ألبرت", "كريستينا البرت"],
        "en": (
            "Prof. Christina Albert\n"
            "Dean — Faculty of Computers and Information, Sadat Academy for Management Sciences.\n\n"
            "Prof. Christina Albert leads FCI academically and administratively, supporting the "
            "faculty's programmes, research direction, and student-focused educational mission."
        ),
        "ar": (
            "أ.د. كريستينا ألبرت\n"
            "عميدة كلية الحاسبات والمعلومات — أكاديمية السادات للعلوم الإدارية.\n\n"
            "تقود أ.د. كريستينا ألبرت الكلية أكاديمياً وإدارياً، وتدعم برامجها واتجاهها البحثي "
            "ورسالتها التعليمية الموجهة للطلاب."
        ),
    },
    "ahmed_esmat": {
        "display": "Dr. Ahmed Esmat",
        "catalog_name": "Ahmed Esmat",
        "aliases": ["ahmed esmat", "esmat", "essmat", "د احمد عصمت", "أحمد عصمت", "احمد عصمت"],
        "en": (
            "Dr. Ahmed Esmat\n"
            "Faculty Member — Faculty of Computers and Information, Sadat Academy for Management Sciences.\n\n"
            "Dr. Ahmed Esmat contributes to FCI teaching across computing, information systems, "
            "data science, and related applied technology areas."
        ),
        "ar": (
            "د. أحمد عصمت\n"
            "عضو هيئة تدريس — كلية الحاسبات والمعلومات، أكاديمية السادات للعلوم الإدارية.\n\n"
            "يساهم د. أحمد عصمت في التدريس داخل الكلية في مجالات الحوسبة ونظم المعلومات وعلوم "
            "البيانات والتكنولوجيا التطبيقية."
        ),
    },
    "dalia_magdy": {
        "display": "Prof. Dalia Magdy",
        "catalog_name": "Dalia Magdy",
        "aliases": ["dalia", "dalia magdy", "most experienced", "29 years", "داليا مجدي", "داليا", "خبرة 29"],
        "en": (
            "Prof. Dalia Magdy\n"
            "Professor of Information Systems — Sadat Academy for Management Sciences.\n\n"
            "Prof. Dalia Magdy has 29+ years of academic experience, with interests in artificial "
            "intelligence, data science, digital business, and information systems. She has also "
            "held senior academic leadership responsibilities."
        ),
        "ar": (
            "أ.د. داليا مجدي\n"
            "أستاذ نظم المعلومات — أكاديمية السادات للعلوم الإدارية.\n\n"
            "تمتلك أ.د. داليا مجدي خبرة أكاديمية تزيد عن 29 عاماً، وتشمل اهتماماتها الذكاء "
            "الاصطناعي وعلوم البيانات والأعمال الرقمية ونظم المعلومات، كما تولت مسؤوليات قيادية أكاديمية."
        ),
    },
    "ahmed_eldeqen": {
        "display": "Prof. Ahmed ElSayed ElDeqen",
        "catalog_name": "Ahmed ElDeqen",
        "aliases": ["ahmed eldeqen", "ahmed elsayed eldeqen", "prof eldeqen", "eldeqen", "الدقن", "أحمد الدقن", "أحمد السيد الدقن"],
        "en": (
            "Prof. Ahmed ElSayed ElDeqen\n"
            "Professor of Management Information Systems — Sadat Academy for Management Sciences.\n\n"
            "Research focus: Artificial Intelligence, Machine Learning, Cloud Computing, Blockchain, "
            "Internet of Things, and Knowledge Discovery. He is an experienced academic leader, "
            "researcher, and educator in intelligent systems and emerging technologies."
        ),
        "ar": (
            "أ.د. أحمد السيد الدقن\n"
            "أستاذ نظم المعلومات الإدارية — أكاديمية السادات للعلوم الإدارية.\n\n"
            "تركز اهتماماته البحثية على الذكاء الاصطناعي والتعلم الآلي والحوسبة السحابية والبلوك "
            "تشين وإنترنت الأشياء واستخراج المعرفة، وله خبرة أكاديمية وبحثية في الأنظمة الذكية "
            "والتقنيات الناشئة."
        ),
    },
    "kholoud_farag": {
        "display": "Dr. Kholoud Farag",
        "catalog_name": "Kholoud Farag",
        "aliases": ["kholoud", "kholoud farag", "خلود", "خلود فرج", "د خلود"],
        "en": (
            "Dr. Kholoud Farag\n"
            "Faculty Member and Researcher — Faculty of Computers and Information, Sadat Academy for Management Sciences.\n\n"
            "Dr. Kholoud Farag contributes to teaching and academic research at FCI, supporting "
            "students through applied computing and information-systems education."
        ),
        "ar": (
            "د. خلود فرج\n"
            "عضو هيئة تدريس وباحثة — كلية الحاسبات والمعلومات، أكاديمية السادات للعلوم الإدارية.\n\n"
            "تساهم د. خلود فرج في التدريس والبحث الأكاديمي داخل الكلية، وتدعم الطلاب من خلال "
            "التعليم التطبيقي في مجالات الحوسبة ونظم المعلومات."
        ),
    },
}


INSTRUCTOR_PROFILE_ROLE_MAP: Sequence[tuple[Sequence[str], Sequence[str]]] = [
    (["who is the dean", "dean of fci", "who runs fci", "who is in charge", "عميد", "عميدة"], ["christina_albert"]),
    (["who is the vice dean", "vice dean", "وكيل الكلية", "نائب العميد"], ["badria_nabil"]),
    (["project supervisor", "who supervises buddybot", "who supervised buddybot", "من أشرف على المشروع", "مشرف المشروع"], ["wael_karam"]),
    (["head of data science", "head of isds", "رئيس قسم علوم البيانات", "رئيس قسم نظم المعلومات"], ["wael_karam"]),
    (["who teaches big data", "big data instructor", "دكتور big data", "مين بيدرس big data"], ["wael_karam"]),
    (["who has 29 years", "29 years experience", "most experienced", "خبرة 29"], ["dalia_magdy"]),
    (
        ["who teaches digital marketing", "digital marketing instructor", "دكتور digital marketing", "مين بيدرس digital marketing"],
        ["mostafa_yakoub", "antony_noshy", "kholoud_farag"],
    ),
]


PROFILE_INTENT_TERMS = [
    "who is",
    "who's",
    "tell me about",
    "profile",
    "background",
    "research",
    "specialisation",
    "specialization",
    "known for",
    "experience",
    "من هو",
    "مين",
    "عن",
    "نبذة",
    "سيرة",
    "تخصص",
    "بحث",
]


def profile_alias_norm(value: str) -> str:
    return normalize_instructor_lookup_name(value)


def instructor_profile_keys_for_text(text: str) -> List[str]:
    lowered = semantic_normalize(text)
    stripped = lowered.strip(" .?!؟")
    for phrases, keys in INSTRUCTOR_PROFILE_ROLE_MAP:
        if any(semantic_normalize(phrase) in lowered for phrase in phrases):
            return list(keys)

    course_teaching_query = bool(extract_instructor_course_query_name(text)) and not text_has_any(lowered, PROFILE_INTENT_TERMS)
    if course_teaching_query:
        return []

    has_profile_intent = text_has_any(lowered, PROFILE_INTENT_TERMS)
    best_key = ""
    best_score = 0.0
    query_norm = profile_alias_norm(text)
    query_tokens = set(query_norm.split())

    for key, profile in INSTRUCTOR_PROFILE_DATA.items():
        aliases = [str(profile.get("display") or ""), str(profile.get("catalog_name") or "")]
        aliases.extend(str(alias) for alias in profile.get("aliases", []) or [])
        for alias in aliases:
            alias_norm = profile_alias_norm(alias)
            if not alias_norm:
                continue
            alias_tokens = set(alias_norm.split())
            score = SequenceMatcher(None, query_norm, alias_norm).ratio()
            if query_norm == alias_norm or stripped == alias_norm:
                score = max(score, 1.0)
            if len(alias_norm) >= 4 and re.search(rf"\b{re.escape(alias_norm)}\b", query_norm):
                score = max(score, 0.98)
            if alias_tokens and alias_tokens.issubset(query_tokens):
                score = max(score, 0.94)
            # Avoid treating ambiguous first names like "Ahmed" as a full profile request.
            if len(alias_tokens) == 1 and alias_norm in {"ahmed", "prof", "dr", "doctor", "د", "دكتور"}:
                score = min(score, 0.2)
            if score > best_score:
                best_key = key
                best_score = score

    if best_key and (best_score >= 0.88 or (has_profile_intent and best_score >= 0.72)):
        return [best_key]
    return []


def instructor_profile_course_lines(catalog_name: str, arabic: bool = False) -> str:
    display_name, courses = find_catalog_instructor_courses(catalog_name)
    if not courses:
        return (
            "Courses in the current catalog: not listed."
            if not arabic
            else "المقررات في الكتالوج الحالي: غير مدرجة."
        )

    label_term = "الفصل الدراسي" if arabic else "Term"
    lines: List[str] = []
    for semester in [1, 2]:
        term_courses = [course for course in courses if int(course.get("semester") or 0) == semester]
        if not term_courses:
            continue
        lines.append(f"{label_term} {semester}:")
        for course in sorted(term_courses, key=lambda c: (int(c.get("year") or 0), str(c.get("code") or ""))):
            code = str(course.get("code") or "").upper()
            name = str(course.get("name") or code).strip()
            dept = str(course.get("dept") or "").upper()
            year = str(course.get("year") or "?")
            lines.append(f"- {name} ({code}) — Year {year}, {dept}")

    if not lines:
        return f"Courses taught by {display_name}: {len(courses)} course(s) in the current catalog."
    return "\n".join(lines)


def instructor_profile_should_include_courses(text: str) -> bool:
    lowered = semantic_normalize(text)
    return text_has_any(
        lowered,
        [
            "teach",
            "teaches",
            "teaching",
            "courses",
            "subjects",
            "who teaches",
            "instructor for",
            "teacher for",
            "بيشرح",
            "بيدرس",
            "يدرس",
            "مين بيدرس",
            "مقررات",
            "مواد",
        ],
    )


def instructor_profile_answer(text: str) -> Optional[str]:
    keys = instructor_profile_keys_for_text(text)
    if not keys:
        return None
    arabic = contains_arabic(text)
    include_courses = instructor_profile_should_include_courses(text)
    answers: List[str] = []
    for key in keys:
        profile = INSTRUCTOR_PROFILE_DATA.get(key)
        if not profile:
            continue
        bio = str(profile.get("ar" if arabic else "en") or profile.get("en") or "").strip()
        if include_courses:
            courses_header = "المقررات المطابقة في الكتالوج الحالي:" if arabic else "Courses matched from the current catalog:"
            courses = instructor_profile_course_lines(str(profile.get("catalog_name") or profile.get("display") or ""), arabic)
            answers.append(f"{bio}\n\n{courses_header}\n{courses}".strip())
        else:
            answers.append(bio)
    return "\n\n".join(answers) if answers else None


def dispatch_instructor_profile_answer(
    dispatcher: CollectingDispatcher,
    text: str,
    tracker: Optional[Tracker] = None,
) -> Optional[List[Dict[Text, Any]]]:
    answer = instructor_profile_answer(text)
    if not answer:
        return None
    keys = instructor_profile_keys_for_text(text)
    display_name = ", ".join(str(INSTRUCTOR_PROFILE_DATA[key].get("display") or key) for key in keys if key in INSTRUCTOR_PROFILE_DATA)
    dispatcher.utter_message(text=with_duplicate_prompt(answer, text, tracker))
    return [
        SlotSet("last_query_scope", "knowledge"),
        SlotSet("last_entity_type", "instructor_profile"),
        SlotSet("last_topic", display_name or "instructor_profile"),
        SlotSet("instructor_name", display_name or None),
    ]


def extract_instructor_course_query_name(text: str) -> Optional[str]:
    lowered = normalize_question(text)
    patterns = [
        r"\bwhat\s+courses?\s+(?:does\s+)?(?:(?:dr|prof|professor|doctor)\.?\s+)?(.+?)\s+(?:teach|teaches|teaching)\??$",
        r"\bwhat\s+(?:does|do)\s+(?:(?:dr|prof|professor|doctor)\.?\s+)?(.+?)\s+(?:teach|teaches)\??$",
        r"\bwhat\s+(?:(?:dr|prof|professor|doctor)\.?\s+)(.+?)\s+(?:teach|teaches)\??$",
        r"\b(?:courses?|subjects?)\s+(?:by|for|of)\s+(?:(?:dr|prof|professor|doctor)\.?\s+)?(.+?)\??$",
        r"(?:بيشرح|بيدرس|يدرس)\s+(?:د|د\.|دكتور|استاذ|أستاذ)?\s*([\u0600-\u06ff\s]{2,})\??$",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered, flags=re.I)
        if match:
            candidate = re.sub(r"[?.!]+$", "", match.group(1)).strip()
            return candidate or None
    return None


def extract_bare_instructor_candidate(text: str) -> Optional[str]:
    stripped = re.sub(r"\s+", " ", (text or "").strip(" ?.!/")).strip()
    lowered = semantic_normalize(stripped)
    if not stripped or contains_arabic(stripped) or fci_department_code_from_text(stripped):
        return None
    if lowered in {"sadat academy", "buddybot"} or lowered.startswith(("what ", "who ", "show ", "list ", "tell ", "give ")):
        return None
    if text_has_any(lowered, ["course", "courses", "student", "students", "schedule", "gpa", "room", "department", "major"]):
        return None
    words = re.findall(r"[a-z][a-z.'-]*", lowered)
    if 1 <= len(words) <= 4 and sum(len(word) > 1 for word in words) == len(words):
        return stripped
    return None


def department_comparison_result(text: str) -> Optional[Dict[str, Any]]:
    lowered = semantic_normalize(text)
    patterns = [
        r"\b(?:what(?:'s| is)?\s+)?(?:the\s+)?difference\s+between\s+(.+?)\s+(?:and|vs\.?)\s+(.+?)\??$",
        r"\bcompare\s+(.+?)\s+(?:and|with|vs\.?)\s+(.+?)\??$",
        r"\b(.+?)\s+vs\.?\s+(.+?)\??$",
    ]
    left_code = right_code = None
    for pattern in patterns:
        match = re.search(pattern, lowered, flags=re.I)
        if not match:
            continue
        left_code = fci_department_code_from_text(match.group(1))
        right_code = fci_department_code_from_text(match.group(2))
        if left_code and right_code and left_code != right_code:
            break
    if not left_code or not right_code or left_code == right_code:
        return None

    left = get_department(left_code) if get_department else None
    right = get_department(right_code) if get_department else None
    if not left or not right:
        return None

    def compact_list(value: Any) -> str:
        if isinstance(value, list):
            return "; ".join(str(item) for item in value[:4] if item)
        return str(value or "").strip()

    def first_sentence(value: str) -> str:
        sentence = re.split(r"(?<=[.!?])\s+", value.strip(), maxsplit=1)[0]
        return sentence or value.strip()

    rows = [
        (
            "Overview",
            first_sentence(str(left.get("description") or "")),
            first_sentence(str(right.get("description") or "")),
        ),
        (
            "Objectives",
            compact_list(left.get("objectives")) or "Focuses on the department's core computing outcomes.",
            compact_list(right.get("objectives")) or "Focuses on the department's core computing outcomes.",
        ),
        (
            "Careers",
            compact_list(left.get("careers")) or "Roles aligned with this specialization.",
            compact_list(right.get("careers")) or "Roles aligned with this specialization.",
        ),
        (
            "Tools",
            compact_list(left.get("tools")) or "Tools vary by course.",
            compact_list(right.get("tools")) or "Tools vary by course.",
        ),
    ]
    lines = [
        f"Difference between {left.get('name', left_code)} ({left_code}) and {right.get('name', right_code)} ({right_code}):"
    ]
    for label, left_value, right_value in rows:
        lines.append(f"{label}:")
        lines.append(f"- {left_code}: {left_value}")
        lines.append(f"- {right_code}: {right_value}")
    return {
        "answer": "\n".join(lines),
        "events": [
            SlotSet("last_query_scope", "course_catalog"),
            SlotSet("department_code", left_code),
            SlotSet("last_topic", f"{left_code}_vs_{right_code}"),
            SlotSet("last_entity_type", "department_comparison"),
        ],
    }


def catalog_context_events(entity_type: str, topic: str, extra: Optional[List[Dict[Text, Any]]] = None) -> List[Dict[Text, Any]]:
    events = list(extra or [])
    events.extend(
        [
            SlotSet("last_query_scope", "course_catalog"),
            SlotSet("last_entity_type", entity_type),
            SlotSet("last_topic", topic),
        ]
    )
    return events


def fci_catalog_result(text: str, tracker: Optional[Tracker] = None) -> Optional[Dict[str, Any]]:
    if not fci_catalog_helpers_available():
        return None

    if is_fci_identity_query(text):
        return {
            "answer": FCI_IDENTITY_RESPONSE,
            "events": [
                SlotSet("last_query_scope", "knowledge"),
                SlotSet("last_topic", "fci"),
                SlotSet("last_entity_type", "faculty"),
            ],
        }

    department_code = fci_department_code_from_text(text)
    lowered = semantic_normalize(text)
    comparison = department_comparison_result(text)
    if comparison:
        return comparison

    if department_code and looks_like_bare_fci_department_query(text):
        answer = format_department_catalog_answer(department_code)
        if answer:
            return {
                "answer": answer,
                "events": [
                    SlotSet("last_query_scope", "course_catalog"),
                    SlotSet("department_code", department_code),
                    SlotSet("last_topic", department_code),
                    SlotSet("last_entity_type", "department"),
                ],
            }

    context_department_code = str(tracker.get_slot("department_code") or "") if tracker else ""
    context_instructor_name = str(tracker.get_slot("instructor_name") or "") if tracker else ""
    context_entity_type = str(tracker.get_slot("last_entity_type") or "") if tracker else ""
    context_topic = str(tracker.get_slot("last_topic") or "") if tracker else ""

    instructor_query_name = extract_instructor_course_query_name(text)
    if instructor_query_name:
        display_name, instructor_courses = find_catalog_instructor_courses(instructor_query_name)
        if instructor_courses:
            header = f"Courses taught by {display_name}:"
            page_size = 20
            events = course_catalog_cache_events(instructor_courses, header, min(page_size, len(instructor_courses)), page_size)
            events.extend(
                [
                    SlotSet("instructor_name", display_name),
                    SlotSet("last_topic", display_name),
                    SlotSet("last_entity_type", "instructor"),
                ]
            )
            return {
                "answer": format_instructor_course_brief_matches(header, instructor_courses, max_results=page_size),
                "events": events,
            }

    generic_course_followup = bool(
        re.search(r"\b(?:what|which|show|list|give|display)\b.*\b(?:courses|subjects)\b", lowered)
        or re.search(r"\b\d{1,3}\s+(?:courses|subjects)\b", lowered)
        or lowered.strip(" ?.!") in {
            "courses",
            "course list",
            "the courses",
            "show me the courses",
            "show courses",
            "show me courses",
            "what courses",
            "what are the courses",
            "what are the 24 courses",
            "list them",
        }
    )
    if not department_code and generic_course_followup and context_department_code and context_entity_type in {"department", "department_comparison", ""}:
        courses = get_courses_by_dept(context_department_code)
        if courses:
            header = f"Courses for {context_department_code}:"
            page_size = 5
            events = course_catalog_cache_events(courses, header, min(page_size, len(courses)), page_size)
            events.extend(
                [
                    SlotSet("department_code", context_department_code),
                    SlotSet("last_topic", context_department_code),
                    SlotSet("last_entity_type", "department"),
                ]
            )
            return {
                "answer": format_fci_catalog_course_matches(header, courses, max_results=page_size),
                "events": events,
            }

    instructor_followup = bool(
        re.search(r"\bwhat\s+(?:does|do)\s+(?:he|she|they|that\s+instructor)\s+teach", lowered)
        or re.search(r"\b(?:his|her|their)\s+(?:courses|subjects)\b", lowered)
    )
    if instructor_followup and context_instructor_name:
        display_name, instructor_courses = find_catalog_instructor_courses(context_instructor_name)
        if instructor_courses:
            header = f"Courses taught by {display_name}:"
            page_size = 20
            events = course_catalog_cache_events(instructor_courses, header, min(page_size, len(instructor_courses)), page_size)
            events.extend(
                [
                    SlotSet("instructor_name", display_name),
                    SlotSet("last_topic", display_name),
                    SlotSet("last_entity_type", "instructor"),
                ]
            )
            return {
                "answer": format_instructor_course_brief_matches(header, instructor_courses, max_results=page_size),
                "events": events,
            }

    if lowered.strip(" ?.!") in {"tell me about it", "about it", "what about it", "explain it", "more about it"}:
        if context_topic == "sadat_academy":
            return {
                "answer": sadat_academy_answer("sadat academy"),
                "events": [
                    SlotSet("last_query_scope", "knowledge"),
                    SlotSet("last_topic", "sadat_academy"),
                    SlotSet("last_entity_type", "institution"),
                ],
            }
        if context_department_code:
            answer = format_department_catalog_answer(context_department_code)
            if answer:
                return {
                    "answer": answer,
                    "events": [
                        SlotSet("last_query_scope", "course_catalog"),
                        SlotSet("department_code", context_department_code),
                        SlotSet("last_topic", context_department_code),
                        SlotSet("last_entity_type", "department"),
                    ],
                }

    schedule_terms = [
        "schedule",
        "timetable",
        "time",
        "timing",
        "lecture",
        "lectures",
        "class",
        "classes",
        "lab",
        "labs",
        "جدول",
        "محاضرة",
        "سكشن",
    ]
    course_list_terms = ["courses", "course list", "subjects", "curriculum", "study plan", "مواد", "مقررات", "كورسات"]
    if text_has_any(lowered, schedule_terms) and not text_has_any(lowered, course_list_terms):
        return None

    course_code = fci_extract_course_code(text)
    if course_code:
        return {
            "answer": format_course_answer(course_code),
            "events": catalog_context_events(
                "course",
                course_code,
                [SlotSet("course_code", course_code)],
            ),
        }

    phrase = extract_course_info_phrase(text)
    if department_code and phrase and fci_department_code_from_text(phrase) and not text_has_any(
        lowered,
        ["course", "courses", "subject", "subjects", "class", "lecture", "مادة", "مواد", "مقرر", "مقررات", "كورس", "كورسات"],
    ):
        return {
            "answer": format_department_catalog_answer(department_code),
            "events": [
                SlotSet("last_query_scope", "course_catalog"),
                SlotSet("department_code", department_code),
                SlotSet("last_topic", department_code),
                SlotSet("last_entity_type", "department"),
            ],
        }

    if department_code and text_has_any(
        lowered,
        ["courses", "course list", "subjects", "curriculum", "study plan", "مواد", "مقررات", "كورسات"],
    ):
        courses = get_courses_by_dept(department_code)
        if courses:
            header = f"Courses for {department_code}:"
            page_size = 5
            events = course_catalog_cache_events(courses, header, min(page_size, len(courses)), page_size)
            events.extend(
                [
                    SlotSet("department_code", department_code),
                    SlotSet("last_topic", department_code),
                    SlotSet("last_entity_type", "department"),
                ]
            )
            return {
                "answer": format_fci_catalog_course_matches(header, courses, max_results=page_size),
                "events": events,
            }

    teacher_subject = extract_teacher_subject_phrase(text)
    if teacher_subject:
        courses = rank_fci_catalog_courses(teacher_subject, find_courses_by_keyword(teacher_subject))
        if courses:
            header = f"I found these matching courses for '{teacher_subject}':"
            page_size = 5
            events = course_catalog_cache_events(courses, header, min(page_size, len(courses)), page_size)
            events.extend(
                [
                    SlotSet("last_topic", teacher_subject),
                    SlotSet("last_entity_type", "course"),
                ]
            )
            if len(courses) == 1 and courses[0].get("code"):
                events.append(SlotSet("course_code", str(courses[0].get("code"))))
            return {
                "answer": format_fci_catalog_course_matches(header, courses, max_results=page_size),
                "events": events,
            }
        display_name, instructor_courses = find_catalog_instructor_courses(teacher_subject)
        if instructor_courses:
            header = f"Courses taught by {display_name}:"
            page_size = 20
            events = course_catalog_cache_events(
                instructor_courses,
                header,
                min(page_size, len(instructor_courses)),
                page_size,
            )
            events.extend(
                [
                    SlotSet("instructor_name", display_name),
                    SlotSet("last_topic", display_name),
                    SlotSet("last_entity_type", "instructor"),
                ]
            )
            return {
                "answer": format_instructor_course_brief_matches(header, instructor_courses, max_results=page_size),
                "events": events,
            }

    instructor_name = extract_fci_instructor_name(text)
    if instructor_name:
        display_name, instructor_courses = find_catalog_instructor_courses(instructor_name)
        if instructor_courses:
            header = f"Courses taught by {display_name}:"
            page_size = 20
            events = course_catalog_cache_events(
                instructor_courses,
                header,
                min(page_size, len(instructor_courses)),
                page_size,
            )
            events.extend(
                [
                    SlotSet("instructor_name", display_name),
                    SlotSet("last_topic", display_name),
                    SlotSet("last_entity_type", "instructor"),
                ]
            )
            return {
                "answer": format_instructor_course_brief_matches(header, instructor_courses, max_results=page_size),
                "events": events,
            }

    bare_instructor = extract_bare_instructor_candidate(text)
    if bare_instructor:
        display_name, instructor_courses = find_catalog_instructor_courses(bare_instructor)
        if instructor_courses:
            header = f"Courses taught by {display_name}:"
            page_size = 20
            events = course_catalog_cache_events(instructor_courses, header, min(page_size, len(instructor_courses)), page_size)
            events.extend(
                [
                    SlotSet("instructor_name", display_name),
                    SlotSet("last_topic", display_name),
                    SlotSet("last_entity_type", "instructor"),
                ]
            )
            return {
                "answer": format_instructor_course_brief_matches(header, instructor_courses, max_results=page_size),
                "events": events,
            }

    if phrase:
        courses = rank_fci_catalog_courses(phrase, find_courses_by_keyword(phrase))
        if courses:
            header = f"I found these course matches for '{phrase}':"
            page_size = 5
            events = course_catalog_cache_events(courses, header, min(page_size, len(courses)), page_size)
            events.extend(
                [
                    SlotSet("last_topic", phrase),
                    SlotSet("last_entity_type", "course"),
                ]
            )
            if len(courses) == 1 and courses[0].get("code"):
                events.append(SlotSet("course_code", str(courses[0].get("code"))))
            return {
                "answer": format_fci_catalog_course_matches(header, courses, max_results=page_size),
                "events": events,
            }

    return None


def fci_catalog_answer(text: str) -> Optional[str]:
    result = fci_catalog_result(text)
    return str(result.get("answer")) if result else None


def dispatch_fci_catalog_answer(
    dispatcher: CollectingDispatcher,
    text: str,
    tracker: Optional[Tracker] = None,
) -> Optional[List[Dict[Text, Any]]]:
    result = fci_catalog_result(text, tracker)
    if not result:
        return None
    dispatcher.utter_message(text=with_duplicate_prompt(str(result.get("answer") or ""), text, tracker))
    return result.get("events") or [SlotSet("last_query_scope", "course_catalog")]


def pending_clarification_topic(tracker: Optional[Tracker]) -> str:
    if not tracker:
        return ""
    return str(tracker.get_slot("last_clarification_topic") or "").strip()


def dispatch_pending_clarification_answer(
    dispatcher: CollectingDispatcher,
    text: str,
    tracker: Optional[Tracker],
    domain: Optional[Dict[Text, Any]] = None,
) -> Optional[List[Dict[Text, Any]]]:
    topic = pending_clarification_topic(tracker)
    if not topic:
        return None

    clear_events = [SlotSet("last_clarification_topic", None)]

    if topic == "tools_by_dept":
        answer = tools_answer_for_department_text(text)
        if answer:
            dispatcher.utter_message(text=with_duplicate_prompt(answer, text, tracker))
            return clear_events + [
                SlotSet("last_query_scope", "knowledge"),
                SlotSet("last_topic", semantic_normalize(text)[:80]),
                SlotSet("last_entity_type", "tools"),
                SlotSet("last_conversation_topic", "tools"),
            ]
        dispatcher.utter_message(text=TOOLS_CLARIFICATION_RESPONSE)
        return [SlotSet("last_clarification_topic", "tools_by_dept"), SlotSet("last_query_scope", "knowledge")]

    if topic == "course_listing":
        department_code = fci_department_code_from_text(text)
        if department_code:
            result = fci_catalog_result(f"{department_code} courses", tracker)
            if result:
                dispatcher.utter_message(text=with_duplicate_prompt(str(result.get("answer") or ""), text, tracker))
                return clear_events + (result.get("events") or [SlotSet("last_query_scope", "course_catalog")])
        dispatcher.utter_message(text="Which department do you want courses for: CS, AI, Cyber Security, ISDS/Data Science, or SE?")
        return [SlotSet("last_clarification_topic", "course_listing"), SlotSet("last_query_scope", "course_catalog")]

    if topic == "schedule_filter":
        followup_question = f"schedule for {text}"
        result = query_sql_engine_service(followup_question, tracker)
        if result and (result.get("handled") or result.get("needs_clarification")):
            utter_sql_engine_result(dispatcher, result, followup_question, tracker)
            return clear_events + sql_engine_events(result)
        dispatcher.utter_message(text=SCHEDULE_CLARIFICATION_RESPONSE)
        return [SlotSet("last_clarification_topic", "schedule_filter"), SlotSet("last_query_scope", "schedule")]

    if topic == "instructor_courses":
        display_name, instructor_courses = find_catalog_instructor_courses(text)
        if instructor_courses:
            header = f"Courses taught by {display_name}:"
            page_size = 20
            events = course_catalog_cache_events(
                instructor_courses,
                header,
                min(page_size, len(instructor_courses)),
                page_size,
            )
            events.extend(
                [
                    SlotSet("instructor_name", display_name),
                    SlotSet("last_topic", display_name),
                    SlotSet("last_entity_type", "instructor"),
                ]
            )
            dispatcher.utter_message(text=format_instructor_course_brief_matches(header, instructor_courses, max_results=page_size))
            return clear_events + events
        dispatcher.utter_message(text="Which instructor do you want the course details for?")
        return [SlotSet("last_clarification_topic", "instructor_courses"), SlotSet("last_query_scope", "course_catalog")]

    return None


def fci_words_like_condition(alias: str, column: str, phrase: str) -> Optional[str]:
    words = [
        word
        for word in re.findall(r"[a-z0-9]+", phrase.lower())
        if word not in {"the", "a", "an", "course", "subject", "class", "lecture", "lab"}
    ]
    if not words:
        return None
    return " AND ".join(
        f"LOWER({alias}.{column}) LIKE {sql_string('%' + word + '%')}" for word in words
    )


def fci_course_conditions(text: str, alias: str = "c") -> List[str]:
    conditions: List[str] = []
    course_code = fci_extract_course_code(text)
    if course_code:
        conditions.append(f"{alias}.course_code = {sql_string(course_code)}")

    phrase = fci_course_phrase_from_question(text)
    if phrase and not course_code:
        condition = fci_words_like_condition(alias, "course_name", phrase)
        if condition:
            conditions.append("(" + condition + ")")

    year_level = fci_extract_year_level(text)
    if year_level:
        conditions.append(f"{alias}.course_year = {year_level}")

    semester = fci_extract_semester(text)
    if semester:
        if alias == "sch":
            conditions.append(f"{alias}.semester = {semester}")
        else:
            conditions.append(f"{alias}.course_semester = {semester}")

    lowered = normalize_question(text)
    if "general" in lowered:
        conditions.append(f"{alias}.category = 'general'")
    if "major" in lowered:
        conditions.append(f"{alias}.category = 'major'")

    return conditions


def fci_schedule_conditions(text: str, alias: str = "sch") -> List[str]:
    conditions = fci_course_conditions(text, alias)
    academic_year = fci_extract_academic_year(text)
    if academic_year:
        conditions.append(f"{alias}.academic_year = {academic_year}")

    day = fci_extract_day(text)
    if day:
        conditions.append(f"{alias}.day_of_week = {sql_string(day)}")

    conditions.extend(fci_schedule_group_conditions(text, alias))

    room_name = extract_room_name(text)
    if room_name:
        conditions.append(f"LOWER({alias}.room_name) LIKE {sql_string('%' + room_name.lower() + '%')}")

    department_code = fci_department_code_from_text(text)
    if department_code:
        conditions.append(
            f"({alias}.target_group = {sql_string(department_code)} "
            f"OR {alias}.course_code LIKE {sql_string(department_code + '%')})"
        )

    return conditions


def fci_list_students_sql(question: str) -> str:
    conditions = fci_student_conditions(question, "s", include_student_id=False)
    top_n = student_list_limit(question)
    return f"""
SELECT TOP {top_n}
    s.student_id AS StudentID,
    s.full_name AS FullName,
    s.email AS Email,
    s.current_year AS CurrentYear,
    s.current_semester AS CurrentSemester,
    s.group_code AS GroupCode,
    s.dept_code AS DepartmentCode,
    s.dept_name AS DepartmentName,
    st.status AS Status
FROM v_rasa_students s
JOIN Students st ON st.student_id = s.student_id
{fci_where(conditions)}
ORDER BY s.group_code, s.full_name
"""


def fci_students_by_name_sql(words: Sequence[str]) -> str:
    conditions = fci_student_name_conditions(words, "s")
    return f"""
SELECT TOP 20
    s.student_id AS StudentID,
    s.full_name AS FullName,
    s.email AS Email,
    s.current_year AS CurrentYear,
    s.current_semester AS CurrentSemester,
    s.group_code AS GroupCode,
    s.dept_code AS DepartmentCode,
    s.dept_name AS DepartmentName,
    st.status AS Status
FROM v_rasa_students s
JOIN Students st ON st.student_id = s.student_id
{fci_where(conditions)}
ORDER BY s.full_name
"""


def fci_student_gpa_by_name_sql(words: Sequence[str]) -> str:
    conditions = fci_student_name_conditions(words, "s")
    return f"""
SELECT TOP 20
    s.student_id AS StudentID,
    s.full_name AS FullName,
    s.group_code AS GroupCode,
    s.dept_code AS DepartmentCode,
    g.academic_year AS AcademicYear,
    g.semester AS Semester,
    g.semester_gpa AS SemesterGPA,
    cg.third_year_cumulative_gpa AS ThirdYearCumulativeGPA,
    cg.cumulative_gpa AS CumulativeGPA
FROM v_rasa_students s
LEFT JOIN GPA_Records g ON g.student_id = s.student_id
LEFT JOIN v_cumulative_gpa cg ON cg.student_id = s.student_id
{fci_where(conditions)}
ORDER BY s.full_name, g.academic_year, g.semester
"""


def fci_student_profile_sql(student_id: str) -> str:
    return f"""
SELECT TOP 20
    s.student_id AS StudentID,
    s.full_name AS FullName,
    s.email AS Email,
    s.current_year AS CurrentYear,
    s.current_semester AS CurrentSemester,
    s.group_code AS GroupCode,
    s.dept_code AS DepartmentCode,
    s.dept_name AS DepartmentName,
    st.status AS Status,
    g.third_year_cumulative_gpa AS ThirdYearCumulativeGPA,
    g.cumulative_gpa AS CumulativeGPA
FROM v_rasa_students s
JOIN Students st ON st.student_id = s.student_id
LEFT JOIN v_rasa_student_gpa g ON g.student_id = s.student_id
WHERE {fci_student_id_condition("s.student_id", student_id)}
"""


def fci_student_gpa_sql(student_id: str) -> str:
    return f"""
SELECT
    s.student_id AS StudentID,
    s.full_name AS FullName,
    g.academic_year AS AcademicYear,
    g.semester AS Semester,
    g.semester_gpa AS SemesterGPA,
    cg.third_year_cumulative_gpa AS ThirdYearCumulativeGPA,
    cg.cumulative_gpa AS CumulativeGPA
FROM Students s
LEFT JOIN GPA_Records g ON g.student_id = s.student_id
LEFT JOIN v_cumulative_gpa cg ON cg.student_id = s.student_id
WHERE {fci_student_id_condition("s.student_id", student_id)}
ORDER BY g.academic_year, g.semester
"""


def fci_student_schedule_sql(student_id: str, question: str) -> str:
    conditions = [
        fci_student_id_condition("s.student_id", student_id),
        "(sch.target_group = s.schedule_group OR sch.target_group = s.group_code)",
    ]
    conditions.extend(fci_schedule_conditions(question, "sch"))
    return f"""
SELECT TOP 60
    s.student_id AS StudentID,
    s.full_name AS FullName,
    sch.day_of_week AS DayOfWeek,
    CONVERT(VARCHAR(5), sch.start_time, 108) AS StartTime,
    CONVERT(VARCHAR(5), sch.end_time, 108) AS EndTime,
    sch.course_code AS CourseCode,
    sch.course_name AS CourseName,
    sch.instructor_name AS InstructorName,
    sch.room_name AS RoomName,
    sch.section_type AS SectionType,
    sch.target_group AS TargetGroup
FROM v_rasa_students s
JOIN v_rasa_schedule sch ON 1 = 1
{fci_where(conditions)}
ORDER BY sch.day_order, sch.start_time, sch.course_code
"""


def fci_schedule_sql(question: str) -> str:
    conditions = fci_schedule_conditions(question, "sch")
    return f"""
SELECT TOP 60
    sch.day_of_week AS DayOfWeek,
    CONVERT(VARCHAR(5), sch.start_time, 108) AS StartTime,
    CONVERT(VARCHAR(5), sch.end_time, 108) AS EndTime,
    sch.course_code AS CourseCode,
    sch.course_name AS CourseName,
    sch.instructor_name AS InstructorName,
    sch.room_name AS RoomName,
    sch.section_type AS SectionType,
    sch.target_group AS TargetGroup
FROM v_rasa_schedule sch
{fci_where(conditions)}
ORDER BY sch.day_order, sch.start_time, sch.target_group, sch.course_code
"""


def fci_course_list_sql(question: str) -> str:
    conditions = fci_course_conditions(question, "c")
    department_code = fci_department_code_from_text(question)
    if department_code:
        conditions.append(f"d.dept_code = {sql_string(department_code)}")
    return f"""
SELECT TOP 50
    c.course_code AS CourseCode,
    c.course_name AS CourseName,
    c.credit_hours AS CreditHours,
    c.total_marks AS TotalMarks,
    c.course_year AS CourseYear,
    c.course_semester AS CourseSemester,
    c.category AS Category,
    d.dept_code AS DepartmentCode,
    d.dept_name AS DepartmentName
FROM Courses c
LEFT JOIN Departments d ON d.dept_id = c.dept_id
{fci_where(conditions)}
ORDER BY c.course_year, c.course_semester, c.course_code
"""


def fci_instructor_by_name_sql(name: str) -> str:
    terms = [term.lower() for term in re.findall(r"[A-Za-z\u0600-\u06ff]+", name or "") if len(term) > 1]
    conditions = [
        f"LOWER(COALESCE(i.full_name, sch.instructor_name)) LIKE {sql_string('%' + term + '%')}"
        for term in terms
    ]
    return f"""
SELECT DISTINCT TOP 30
    i.instructor_id AS InstructorID,
    COALESCE(i.title, sch.instructor_title) AS InstructorTitle,
    COALESCE(i.full_name, sch.instructor_name) AS InstructorName,
    i.email AS Email,
    sch.course_code AS CourseCode,
    sch.course_name AS CourseName,
    sch.target_group AS TargetGroup,
    sch.section_type AS SectionType
FROM Instructors i
LEFT JOIN v_rasa_schedule sch ON LOWER(sch.instructor_name) = LOWER(i.full_name)
{fci_where(conditions)}
ORDER BY InstructorName, CourseCode, TargetGroup
"""


def fci_teacher_sql(question: str) -> str:
    conditions = fci_schedule_conditions(question, "sch")
    if conditions:
        return f"""
SELECT DISTINCT TOP 30
    sch.course_code AS CourseCode,
    sch.course_name AS CourseName,
    sch.instructor_title AS InstructorTitle,
    sch.instructor_name AS InstructorName,
    sch.target_group AS TargetGroup,
    sch.section_type AS SectionType
FROM v_rasa_schedule sch
{fci_where(conditions)}
ORDER BY sch.course_code, sch.instructor_name
"""
    return """
SELECT TOP 50
    instructor_id AS InstructorID,
    title AS InstructorTitle,
    full_name AS InstructorName,
    email AS Email
FROM Instructors
ORDER BY full_name
"""


def fci_departments_sql() -> str:
    return """
SELECT
    d.dept_code AS DepartmentCode,
    d.dept_name AS DepartmentName,
    COUNT(s.student_id) AS StudentCount
FROM Departments d
LEFT JOIN Students s ON s.dept_id = d.dept_id
GROUP BY d.dept_code, d.dept_name
ORDER BY d.dept_code
"""


def fci_rooms_sql(question: str) -> str:
    lowered = normalize_question(question)
    conditions = []
    if "lab" in lowered:
        conditions.append("room_type = 'lab'")
    elif "hall" in lowered:
        conditions.append("room_type = 'hall'")
    elif "classroom" in lowered or "class room" in lowered:
        conditions.append("room_type = 'classroom'")
    return f"""
SELECT TOP 50
    room_name AS RoomName,
    room_type AS RoomType,
    capacity AS Capacity,
    building AS Building
FROM Rooms
{fci_where(conditions)}
ORDER BY room_type, room_name
"""


def fci_gpa_aggregate_sql(question: str) -> str:
    lowered = normalize_question(question)
    conditions = ["g.semester_gpa IS NOT NULL"]
    conditions.extend(fci_student_conditions(question, "s", include_student_id=False))

    if any(word in lowered for word in ["highest", "top", "best", "maximum", "max"]):
        return f"""
SELECT TOP 10
    s.student_id AS StudentID,
    s.full_name AS FullName,
    s.group_code AS GroupCode,
    s.dept_code AS DepartmentCode,
    g.academic_year AS AcademicYear,
    g.semester AS Semester,
    g.semester_gpa AS SemesterGPA
FROM GPA_Records g
JOIN v_rasa_students s ON s.student_id = g.student_id
{fci_where(conditions)}
ORDER BY g.semester_gpa DESC
"""

    if any(word in lowered for word in ["lowest", "least", "minimum", "min"]):
        return f"""
SELECT TOP 10
    s.student_id AS StudentID,
    s.full_name AS FullName,
    s.group_code AS GroupCode,
    s.dept_code AS DepartmentCode,
    g.academic_year AS AcademicYear,
    g.semester AS Semester,
    g.semester_gpa AS SemesterGPA
FROM GPA_Records g
JOIN v_rasa_students s ON s.student_id = g.student_id
{fci_where(conditions)}
ORDER BY g.semester_gpa ASC
"""

    if "by department" in lowered or "per department" in lowered or "department" in lowered:
        return f"""
SELECT
    s.dept_code AS GroupName,
    AVG(CAST(g.semester_gpa AS FLOAT)) AS AverageSemesterGPA,
    COUNT(DISTINCT s.student_id) AS StudentCount
FROM GPA_Records g
JOIN v_rasa_students s ON s.student_id = g.student_id
{fci_where(conditions)}
GROUP BY s.dept_code
ORDER BY AverageSemesterGPA DESC
"""

    if "by group" in lowered or "per group" in lowered or "group" in lowered:
        return f"""
SELECT
    s.group_code AS GroupName,
    AVG(CAST(g.semester_gpa AS FLOAT)) AS AverageSemesterGPA,
    COUNT(DISTINCT s.student_id) AS StudentCount
FROM GPA_Records g
JOIN v_rasa_students s ON s.student_id = g.student_id
{fci_where(conditions)}
GROUP BY s.group_code
ORDER BY AverageSemesterGPA DESC
"""

    return f"""
SELECT
    AVG(CAST(g.semester_gpa AS FLOAT)) AS AverageSemesterGPA
FROM GPA_Records g
JOIN v_rasa_students s ON s.student_id = g.student_id
{fci_where(conditions)}
"""


def fci_student_count_sql(question: str) -> str:
    lowered = normalize_question(question)
    conditions = fci_student_conditions(question, "s", include_student_id=False)
    if "by department" in lowered or "per department" in lowered or "department" in lowered:
        return f"""
SELECT
    s.dept_code AS GroupName,
    COUNT(*) AS StudentCount,
    COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0) AS StudentPercent
FROM v_rasa_students s
{fci_where(conditions)}
GROUP BY s.dept_code
ORDER BY StudentCount DESC
"""
    if "by group" in lowered or "per group" in lowered or "group" in lowered:
        return f"""
SELECT
    s.group_code AS GroupName,
    COUNT(*) AS StudentCount,
    COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0) AS StudentPercent
FROM v_rasa_students s
{fci_where(conditions)}
GROUP BY s.group_code
ORDER BY StudentCount DESC
"""
    return f"""
SELECT COUNT(*) AS StudentCount
FROM v_rasa_students s
{fci_where(conditions)}
"""


def fci_stats_scope_label(text: str) -> str:
    department_code = fci_department_code_from_text(text)
    if department_code:
        department = get_department(department_code) if get_department else None
        return str((department or {}).get("name") or department_code)
    group_code = fci_extract_group_code(text)
    if group_code:
        return f"group {group_code}"
    year_level = fci_extract_year_level(text)
    if year_level:
        return f"year {year_level}"
    return "FCI"


def looks_like_instructor_count_or_list(text: str) -> bool:
    lowered = semantic_normalize(text)
    instructor_terms = [
        "doctor",
        "doctors",
        "dr",
        "instructor",
        "instructors",
        "teacher",
        "teachers",
        "professor",
        "professors",
        "teaching staff",
        "faculty staff",
        "اعضاء هيئة التدريس",
        "هيئة التدريس",
        "دكاترة",
        "دكتور",
        "مدرسين",
        "محاضرين",
        "اساتذة",
        "أساتذة",
    ]
    if not text_has_any(lowered, instructor_terms):
        return False
    has_standalone_arabic_all = bool(re.search(r"(?<![\u0600-\u06ff])كل(?![\u0600-\u06ff])", lowered))
    return has_standalone_arabic_all or text_has_any(
        lowered,
        [
            "how many",
            "count",
            "number of",
            "total",
            "list",
            "names",
            "show",
            "give me",
            "all",
            "كام",
            "كم",
            "عدد",
            "قائمة",
            "اسماء",
            "أسماء",
            "اعرض",
            "هات",
        ],
    )


def looks_like_student_count_question(text: str) -> bool:
    lowered = semantic_normalize(text)
    if not text_has_any(lowered, ["student", "students", "طلاب", "طالب", "طلبة"]):
        return False
    return text_has_any(
        lowered,
        ["how many", "count", "number of", "total", "breakdown", "كام", "كم", "عدد", "احصاء", "إحصاء"],
    )


def looks_like_gpa_average_question(text: str) -> bool:
    lowered = semantic_normalize(text)
    has_gpa = text_has_any(lowered, ["gpa", "cgpa", "معدل", "المعدل", "جي بي اي"])
    has_average = text_has_any(lowered, ["average", "avg", "mean", "متوسط", "المتوسط"])
    return has_gpa and has_average


def run_fci_stats_sql(sql: str) -> tuple[List[str], List[Any]]:
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(adapt_sql_for_configured_database(sql))
        rows = cursor.fetchall()
        columns = cursor_column_names(cursor)
        return columns, rows
    finally:
        if conn:
            conn.close()


def format_instructor_list_answer(columns: Sequence[str], rows: Sequence[Any], text: str) -> str:
    arabic = contains_arabic(text)
    if not rows:
        return student_affairs_fallback(text)
    lines = [
        "قائمة أعضاء هيئة التدريس المسجلين في قاعدة بيانات FCI:"
        if arabic
        else "Here are the instructors/teaching staff listed in the FCI database:"
    ]
    for row in rows[:80]:
        data = dict(zip(columns, list(row)))
        title = format_value(data.get("InstructorTitle"))
        name = format_value(data.get("InstructorName"))
        email = format_value(data.get("Email"))
        display = f"{title} {name}".replace("not recorded", "").replace("  ", " ").strip()
        if email != "not recorded":
            lines.append(f"- {display} — {email}")
        else:
            lines.append(f"- {display}")
    if len(rows) > 80:
        lines.append(
            f"ويظهر هنا أول 80 اسمًا من إجمالي {len(rows)}."
            if arabic
            else f"Showing the first 80 names out of {len(rows)}."
        )
    return "\n".join(lines)


def row_value_case_insensitive(data: Dict[str, Any], *names: str) -> Any:
    lowered = {str(key).lower(): value for key, value in data.items()}
    for name in names:
        key = str(name).lower()
        if key in lowered:
            return lowered[key]
    return None


def dispatch_fci_stats_answer(
    dispatcher: CollectingDispatcher,
    text: str,
    tracker: Optional[Tracker] = None,
) -> Optional[List[Dict[Text, Any]]]:
    lowered = semantic_normalize(text)
    arabic = contains_arabic(text)

    try:
        if looks_like_instructor_count_or_list(text):
            list_query = bool(re.search(r"(?<![\u0600-\u06ff])كل(?![\u0600-\u06ff])", lowered)) or text_has_any(
                lowered,
                ["list", "names", "show", "give me", "all", "قائمة", "اسماء", "أسماء", "اعرض", "هات"],
            )
            if list_query:
                sql = """
SELECT DISTINCT TOP 100
    title AS InstructorTitle,
    full_name AS InstructorName,
    email AS Email
FROM Instructors
WHERE full_name IS NOT NULL AND full_name <> ''
ORDER BY full_name
"""
                columns, rows = run_fci_stats_sql(sql)
                dispatcher.utter_message(text=with_duplicate_prompt(format_instructor_list_answer(columns, rows, text), text, tracker))
                return [SlotSet("last_query_scope", "database"), SlotSet("last_entity_type", "instructor_list")]

            sql = """
SELECT COUNT(DISTINCT full_name) AS InstructorCount
FROM Instructors
WHERE full_name IS NOT NULL AND full_name <> ''
"""
            columns, rows = run_fci_stats_sql(sql)
            count = format_value(rows[0][0]) if rows else "0"
            answer = (
                f"يوجد {count} عضو هيئة تدريس/مدرس مسجل في قاعدة بيانات FCI."
                if arabic
                else f"There are {count} instructors/teaching staff members listed in the FCI database."
            )
            dispatcher.utter_message(text=with_duplicate_prompt(answer, text, tracker))
            return [SlotSet("last_query_scope", "database"), SlotSet("last_entity_type", "instructor_count")]

        if looks_like_student_count_question(text):
            scope = fci_stats_scope_label(text)
            conditions = fci_student_conditions(text, "s", include_student_id=False)
            sql = f"""
SELECT COUNT(*) AS StudentCount
FROM v_rasa_students s
{fci_where(conditions)}
"""
            columns, rows = run_fci_stats_sql(sql)
            count = format_value(rows[0][0]) if rows else "0"
            answer = (
                f"عدد الطلاب في {scope}: {count}."
                if arabic
                else f"{scope} has {count} student records in the FCI database."
            )
            dispatcher.utter_message(text=with_duplicate_prompt(answer, text, tracker))
            return [SlotSet("last_query_scope", "database"), SlotSet("last_entity_type", "student_count")]

        if looks_like_gpa_average_question(text):
            scope = fci_stats_scope_label(text)
            conditions = fci_student_conditions(text, "s", include_student_id=False)
            conditions.append("g.semester_gpa IS NOT NULL")
            sql = f"""
SELECT
    AVG(CAST(g.semester_gpa AS FLOAT)) AS AverageGPA,
    COUNT(DISTINCT s.student_id) AS StudentCount
FROM GPA_Records g
JOIN v_rasa_students s ON s.student_id = g.student_id
{fci_where(conditions)}
"""
            columns, rows = run_fci_stats_sql(sql)
            if not rows or rows[0][0] is None:
                dispatcher.utter_message(text=student_affairs_fallback(text))
                return [SlotSet("last_query_scope", "database")]
            data = dict(zip(columns, list(rows[0])))
            average = format_value(row_value_case_insensitive(data, "AverageGPA", "averagegpa"))
            count = format_value(row_value_case_insensitive(data, "StudentCount", "studentcount"))
            answer = (
                f"متوسط المعدل في {scope} هو {average} محسوبًا على {count} طالب."
                if arabic
                else f"The average GPA in {scope} is {average}, based on {count} student records."
            )
            dispatcher.utter_message(text=with_duplicate_prompt(answer, text, tracker))
            return [SlotSet("last_query_scope", "database"), SlotSet("last_entity_type", "gpa_average")]

    except Exception as exc:
        print(f"FCI stats answer failed: {exc}", file=sys.stderr)
        dispatcher.utter_message(text=student_affairs_fallback(text))
        return [SlotSet("last_query_scope", "database")]

    return None


def fci_grades_sql(question: str, student_id: Optional[str]) -> str:
    conditions = []
    if student_id:
        conditions.append(fci_student_id_condition("g.student_id", student_id))
    conditions.extend(fci_course_conditions(question, "g"))
    return f"""
SELECT TOP 30
    g.student_id AS StudentID,
    g.student_name AS FullName,
    g.course_code AS CourseCode,
    g.course_name AS CourseName,
    g.raw_score AS RawScore,
    g.enrollment_total_marks AS TotalMarks,
    g.percentage AS Percentage,
    g.grade_letter AS GradeLetter,
    g.pass_status AS PassStatus
FROM v_grades g
{fci_where(conditions)}
ORDER BY g.academic_year, g.semester, g.course_code
"""


def build_fci_known_sql(question: str, context_student_id: Optional[str]) -> Optional[str]:
    lowered = normalize_question(question)
    message_student_id = extract_student_id(question)
    student_id = message_student_id or (context_student_id if should_use_context_student(question) else None)
    instructor_name = extract_fci_instructor_name(question)
    name_words = fci_extract_student_name_words(question)
    if student_id and wants_current_student(question):
        name_words = []

    asks_schedule = any(word in lowered for word in ["schedule", "timetable", "class", "classes", "lecture", "lectures", "lab", "labs", "when", "where"])
    asks_gpa = any(word in lowered for word in ["gpa", "cgpa", "cumulative"])
    asks_average_gpa = asks_gpa and re.search(r"\b(?:average|avg|mean)\b", lowered)
    asks_student_count = (
        bool(re.search(r"\b(?:how many|count|number of|percentage|percent|breakdown|total)\b", lowered))
        and "student" in lowered
    )
    asks_grade = any(word in lowered for word in ["grade", "grades", "mark", "marks", "score", "scores", "result"]) or (
        bool(fci_extract_course_code(question))
        and bool(student_id)
        and any(word in lowered for word in ["get", "got", "receive", "received"])
    )

    if asks_student_count:
        return fci_student_count_sql(question)

    if asks_average_gpa:
        return fci_gpa_aggregate_sql(question)

    if instructor_name:
        return fci_instructor_by_name_sql(instructor_name)

    if student_id and asks_schedule:
        return fci_student_schedule_sql(student_id, question)

    if asks_schedule:
        return fci_schedule_sql(question)

    if name_words and asks_gpa:
        resolved_creator_id = CREATOR_STUDENT_IDS_BY_NAME.get(" ".join(name_words).lower())
        if resolved_creator_id:
            return fci_student_gpa_sql(resolved_creator_id)
        return fci_student_gpa_by_name_sql(name_words)

    if name_words:
        return fci_students_by_name_sql(name_words)

    if student_id and asks_gpa:
        return fci_student_gpa_sql(student_id)

    if asks_grade:
        return fci_grades_sql(question, student_id)

    if student_id:
        return fci_student_profile_sql(student_id)

    if any(word in lowered for word in ["teacher", "teaches", "instructor", "professor"]) or ("faculty" in lowered and "student" not in lowered):
        return fci_teacher_sql(question)

    if "department" in lowered or "departments" in lowered or "major" in lowered:
        return fci_departments_sql()

    if "room" in lowered or "rooms" in lowered or "classroom" in lowered or "hall" in lowered:
        return fci_rooms_sql(question)

    if "course" in lowered or "courses" in lowered or "subject" in lowered or "subjects" in lowered or "credit" in lowered:
        if re.search(r"\b(how many|count|number of)\b", lowered):
            conditions = fci_course_conditions(question, "c")
            department_code = fci_department_code_from_text(question)
            if department_code:
                conditions.append(f"d.dept_code = {sql_string(department_code)}")
            return f"""
SELECT COUNT(*) AS CourseCount
FROM Courses c
LEFT JOIN Departments d ON d.dept_id = c.dept_id
{fci_where(conditions)}
"""
        return fci_course_list_sql(question)

    if asks_gpa:
        return fci_gpa_aggregate_sql(question)

    if "student" in lowered and any(word in lowered for word in ["show", "list", "all", "records", "profiles", "profile", "data"]):
        return fci_list_students_sql(question)

    return None


def missing_schema_question(text: str) -> bool:
    lowered = normalize_question(text)
    missing_terms = [
        "gpa",
        "cgpa",
        "credit",
        "credits",
        "credit hours",
        "roll number",
        "roll no",
        "name",
        "department",
        "department id",
        "faculty",
        "subject",
        "class",
        "course",
    ]
    return any(term in lowered for term in missing_terms)


def extract_numeric_comparison(text: str) -> Optional[tuple]:
    lowered = normalize_question(text)
    patterns = [
        (r"\b(?:more than|greater than|higher than|above|over)\s*(\d+(?:\.\d+)?)\b", ">"),
        (r"\b(?:at least|minimum of|not less than)\s*(\d+(?:\.\d+)?)\b", ">="),
        (r"\b(?:less than|lower than|below|under)\s*(\d+(?:\.\d+)?)\b", "<"),
        (r"\b(?:at most|maximum of|not more than|up to)\s*(\d+(?:\.\d+)?)\b", "<="),
        (r"\b(?:equal to|equals|exactly)\s*(\d+(?:\.\d+)?)\b", "="),
    ]
    for pattern, operator in patterns:
        match = re.search(pattern, lowered)
        if match:
            return operator, match.group(1)
    return None


def metric_column_from_question(text: str) -> Optional[str]:
    lowered = normalize_question(text)
    if looks_like_general_conversation_request(lowered):
        return None
    if "attendance" in lowered:
        return "Attendance"
    if "previous" in lowered and ("score" in lowered or "marks" in lowered):
        return "Previous_Scores"
    if "study" in lowered or "hours studied" in lowered:
        return "Hours_Studied"
    if "sleep" in lowered:
        return "Sleep_Hours"
    if "tutoring" in lowered:
        return "Tutoring_Sessions"
    if "physical" in lowered:
        return "Physical_Activity"
    if "exam" in lowered or "score" in lowered or "marks" in lowered or "grade" in lowered:
        return "Exam_Score"
    return None


def metric_table_for_column(column: str) -> str:
    if column in {"Hours_Studied", "Sleep_Hours", "Tutoring_Sessions", "Physical_Activity"}:
        return "Academic_Behavior"
    return "Academic_Performance"


def metric_alias_for_column(column: str) -> str:
    aliases = {
        "Exam_Score": "AverageExamScore",
        "Attendance": "AverageAttendance",
        "Previous_Scores": "AveragePreviousScore",
        "Hours_Studied": "AverageStudyHours",
        "Sleep_Hours": "AverageSleepHours",
        "Tutoring_Sessions": "AverageTutoringSessions",
        "Physical_Activity": "AveragePhysicalActivity",
    }
    return aliases.get(column, f"Average{column.replace('_', '')}")


def metric_percent_alias_for_column(column: str) -> str:
    aliases = {
        "Exam_Score": "PercentOfAverageExamScore",
        "Attendance": "PercentOfAverageAttendance",
        "Previous_Scores": "PercentOfAveragePreviousScore",
        "Hours_Studied": "PercentOfAverageStudyHours",
        "Sleep_Hours": "PercentOfAverageSleepHours",
        "Tutoring_Sessions": "PercentOfAverageTutoringSessions",
        "Physical_Activity": "PercentOfAveragePhysicalActivity",
    }
    return aliases.get(column, f"PercentOfAverage{column.replace('_', '')}")


def aggregate_alias(prefix: str, column: str) -> str:
    stems = {
        "Exam_Score": "ExamScore",
        "Attendance": "Attendance",
        "Previous_Scores": "PreviousScore",
        "Hours_Studied": "StudyHours",
        "Sleep_Hours": "SleepHours",
        "Tutoring_Sessions": "TutoringSessions",
        "Physical_Activity": "PhysicalActivity",
    }
    return f"{prefix}{stems.get(column, column.replace('_', ''))}"


def metric_threshold_sql(question: str) -> Optional[str]:
    column = metric_column_from_question(question)
    comparison = extract_numeric_comparison(question)
    if not column or not comparison:
        return None

    operator, threshold = comparison
    lowered = normalize_question(question)
    table = metric_table_for_column(column)
    if re.search(r"\b(how many|count|number of)\b", lowered):
        return f"""
SELECT COUNT(*) AS StudentCount
FROM {table}
WHERE {column} {operator} {threshold}
"""

    order = "ASC" if operator in {"<", "<="} else "DESC"
    return f"""
SELECT TOP 20 StudentID, {column}
FROM {table}
WHERE {column} {operator} {threshold}
ORDER BY {column} {order}
"""


def student_metric_percent_sql(question: str, student_id: Optional[str]) -> Optional[str]:
    if not student_id:
        return None

    lowered = normalize_question(question)
    compares_to_average = ("compare" in lowered or "compared" in lowered) and (
        "average" in lowered or asks_overall_scope(lowered)
    )
    if not any(word in lowered for word in ["percent", "percentage", "ratio"]) and not compares_to_average:
        return None

    column = metric_column_from_question(lowered)
    if not column:
        return None

    expression = metric_expression(column)
    table = metric_table_for_column(column)
    average_alias = metric_alias_for_column(column)
    percent_alias = metric_percent_alias_for_column(column)
    if not expression:
        return None

    return f"""
SELECT
    s.StudentID,
    {expression} AS {column},
    overall.{average_alias},
    CAST({expression} AS FLOAT) * 100.0 / NULLIF(overall.{average_alias}, 0) AS {percent_alias}
{join_all_tables_sql()}
CROSS JOIN (
    SELECT AVG(CAST({column} AS FLOAT)) AS {average_alias}
    FROM {table}
    WHERE {column} IS NOT NULL
) overall
WHERE s.StudentID = {student_id} AND {expression} IS NOT NULL
"""


def join_all_tables_sql() -> str:
    return """
FROM Students s
LEFT JOIN Academic_Performance ap ON s.StudentID = ap.StudentID
LEFT JOIN Academic_Behavior ab ON s.StudentID = ab.StudentID
LEFT JOIN Family_Background fb ON s.StudentID = fb.StudentID
LEFT JOIN School_Environment se ON s.StudentID = se.StudentID
"""


def metric_expression(column: str) -> Optional[str]:
    aliases = {
        "Exam_Score": "ap.Exam_Score",
        "Attendance": "ap.Attendance",
        "Previous_Scores": "ap.Previous_Scores",
        "Hours_Studied": "ab.Hours_Studied",
        "Sleep_Hours": "ab.Sleep_Hours",
        "Tutoring_Sessions": "ab.Tutoring_Sessions",
        "Physical_Activity": "ab.Physical_Activity",
    }
    return aliases.get(column)


def gender_from_question(text: str) -> Optional[str]:
    lowered = normalize_question(text)
    if re.search(r"\b(female|females|girl|girls|women)\b", lowered):
        return "Female"
    if re.search(r"\b(male|males|boy|boys|men)\b", lowered):
        return "Male"
    return None


def mentions_both_genders(text: str) -> bool:
    lowered = normalize_question(text)
    has_male = bool(re.search(r"\b(male|males|boy|boys|men)\b", lowered))
    has_female = bool(re.search(r"\b(female|females|girl|girls|women)\b", lowered))
    return has_male and has_female


def group_expression_from_question(question: str) -> Optional[tuple]:
    lowered = normalize_question(question)
    if "motivation" in lowered:
        return "ab.Motivation_Level", "motivation"
    if "school type" in lowered or "public" in lowered or "private" in lowered:
        return "s.School_Type", "school type"
    if "gender" in lowered or gender_from_question(lowered):
        return "s.Gender", "gender"
    if "resource" in lowered or "resources" in lowered:
        return "se.Access_to_Resources", "resource access"
    if "family income" in lowered or "income" in lowered:
        return "fb.Family_Income", "family income"
    if "parental involvement" in lowered or ("parent" in lowered and "involvement" in lowered):
        return "fb.Parental_Involvement", "parental involvement"
    if "parental education" in lowered or ("parent" in lowered and "education" in lowered):
        return "fb.Parental_Education_Level", "parental education"
    if "teacher quality" in lowered:
        return "se.Teacher_Quality", "teacher quality"
    if "peer influence" in lowered:
        return "se.Peer_Influence", "peer influence"
    if "distance" in lowered or "home" in lowered:
        return "s.Distance_from_Home", "distance from home"
    return None


def analytics_calculation_sql(question: str) -> Optional[str]:
    lowered = normalize_question(question)
    column = metric_column_from_question(question)
    group = group_expression_from_question(question)

    if "correlation" in lowered or (
        ("relationship" in lowered or "relation" in lowered or "connected" in lowered)
        and "study" in lowered
        and ("exam" in lowered or "score" in lowered)
    ):
        return """
SELECT
    (
        COUNT(*) * SUM(CAST(ab.Hours_Studied AS FLOAT) * CAST(ap.Exam_Score AS FLOAT))
        - SUM(CAST(ab.Hours_Studied AS FLOAT)) * SUM(CAST(ap.Exam_Score AS FLOAT))
    ) /
    NULLIF(
        SQRT(
            (COUNT(*) * SUM(CAST(ab.Hours_Studied AS FLOAT) * CAST(ab.Hours_Studied AS FLOAT))
             - SUM(CAST(ab.Hours_Studied AS FLOAT)) * SUM(CAST(ab.Hours_Studied AS FLOAT)))
            *
            (COUNT(*) * SUM(CAST(ap.Exam_Score AS FLOAT) * CAST(ap.Exam_Score AS FLOAT))
             - SUM(CAST(ap.Exam_Score AS FLOAT)) * SUM(CAST(ap.Exam_Score AS FLOAT)))
        ),
        0
    ) AS CorrelationStudyHoursExamScore
FROM Academic_Behavior ab
JOIN Academic_Performance ap ON ap.StudentID = ab.StudentID
WHERE ab.Hours_Studied IS NOT NULL AND ap.Exam_Score IS NOT NULL
"""

    if group and (
        (
            re.search(r"\b(how many|count|number of)\b", lowered)
            and (
                re.search(r"\b(by|each|per)\b", lowered)
                or "breakdown" in lowered
                or "break down" in lowered
                or (group[1] == "gender" and mentions_both_genders(lowered))
            )
        )
        or (
            any(word in lowered for word in ["percent", "percentage", "ratio", "share", "breakdown", "break down"])
            and (
                re.search(r"\b(by|each|per)\b", lowered)
                or "breakdown" in lowered
                or "break down" in lowered
                or group[1] == "gender"
            )
        )
    ):
        group_expression, _ = group
        return f"""
SELECT
    {group_expression} AS GroupName,
    COUNT(*) AS StudentCount,
    COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0) AS StudentPercent
{join_all_tables_sql()}
WHERE {group_expression} IS NOT NULL
GROUP BY {group_expression}
ORDER BY StudentCount DESC
"""

    if column and ("average" in lowered or "avg" in lowered or "mean" in lowered):
        expression = metric_expression(column)
        alias = metric_alias_for_column(column)
        if not expression:
            return None
        if group and ("by" in lowered or "compare" in lowered or "comparison" in lowered):
            group_expression, _ = group
            return f"""
SELECT
    {group_expression} AS GroupName,
    AVG(CAST({expression} AS FLOAT)) AS {alias},
    COUNT(*) AS StudentCount
{join_all_tables_sql()}
WHERE {expression} IS NOT NULL AND {group_expression} IS NOT NULL
GROUP BY {group_expression}
ORDER BY {alias} DESC
"""
        return f"SELECT AVG(CAST({expression} AS FLOAT)) AS {alias} {join_all_tables_sql()} WHERE {expression} IS NOT NULL"

    if column and ("compare" in lowered or "comparison" in lowered):
        group = group_expression_from_question(question)
        expression = metric_expression(column)
        alias = metric_alias_for_column(column)
        if group and expression:
            group_expression, _ = group
            return f"""
SELECT
    {group_expression} AS GroupName,
    AVG(CAST({expression} AS FLOAT)) AS {alias},
    COUNT(*) AS StudentCount
{join_all_tables_sql()}
WHERE {expression} IS NOT NULL AND {group_expression} IS NOT NULL
GROUP BY {group_expression}
ORDER BY {alias} DESC
"""

    if column:
        expression = metric_expression(column)
        if not expression:
            return None
        has_numeric_filter = extract_numeric_comparison(question) is not None
        wants_listing = bool(re.search(r"\b(who|which|show|list|top)\b", lowered))
        aggregate: Optional[tuple] = None
        if any(phrase in lowered for phrase in ["standard deviation", "std dev", "stdev"]):
            aggregate = ("STDEV", "StandardDeviation")
        elif "variance" in lowered:
            aggregate = ("VAR", "Variance")
        elif any(word in lowered for word in ["total", "sum"]):
            aggregate = ("SUM", "Total")
        elif not has_numeric_filter and not wants_listing and any(word in lowered for word in ["maximum", "max", "highest", "best"]):
            aggregate = ("MAX", "Highest")
        elif not has_numeric_filter and not wants_listing and any(word in lowered for word in ["minimum", "min", "lowest", "least"]):
            aggregate = ("MIN", "Lowest")
        if aggregate:
            function_name, prefix = aggregate
            alias = aggregate_alias(prefix, column)
            return f"SELECT {function_name}(CAST({expression} AS FLOAT)) AS {alias} {join_all_tables_sql()} WHERE {expression} IS NOT NULL"

    return None


def categorical_filter_sql(question: str) -> Optional[str]:
    lowered = normalize_question(question)
    wants_count = bool(re.search(r"\b(how many|count|number of)\b", lowered))
    wants_list = any(word in lowered for word in ["show", "list", "which", "who"])
    wants_percent = any(word in lowered for word in ["percent", "percentage", "ratio"])

    def build(table: str, column: str, value: Any, order_column: str = "StudentID") -> str:
        if isinstance(value, str):
            condition = f"{column} = '{value}'"
        else:
            condition = f"{column} = {value}"
        if wants_percent:
            return f"""
SELECT
    SUM(CASE WHEN {condition} THEN 1 ELSE 0 END) AS MatchingStudents,
    COUNT(*) AS TotalStudents,
    SUM(CASE WHEN {condition} THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0) AS StudentPercent
FROM {table}
"""
        if wants_count:
            return f"SELECT COUNT(*) AS StudentCount FROM {table} WHERE {condition}"
        if wants_list:
            return f"SELECT TOP 20 StudentID, {column} FROM {table} WHERE {condition} ORDER BY {order_column}"
        return ""

    if "motivation" in lowered:
        for level in ["low", "medium", "high"]:
            if level in lowered:
                return build("Academic_Behavior", "Motivation_Level", level.capitalize())

    gender = gender_from_question(lowered)
    if gender:
        return build("Students", "Gender", gender)

    if "school" in lowered:
        for school_type in ["private", "public"]:
            if school_type in lowered:
                return build("Students", "School_Type", school_type.capitalize())

    if "internet" in lowered:
        if any(phrase in lowered for phrase in ["no internet", "without internet", "do not have internet"]):
            return build("School_Environment", "Internet_Access", 0)
        if "internet access" in lowered or "have internet" in lowered:
            return build("School_Environment", "Internet_Access", 1)

    if "learning disabil" in lowered:
        if any(phrase in lowered for phrase in ["no learning", "without learning", "do not have"]):
            return build("Students", "Learning_Disabilities", 0)
        return build("Students", "Learning_Disabilities", 1)

    if "resource" in lowered or "resources" in lowered:
        if "limited" in lowered:
            return build("School_Environment", "Access_to_Resources", "Low")
        for level in ["low", "medium", "high"]:
            if level in lowered:
                return build("School_Environment", "Access_to_Resources", level.capitalize())

    if "family income" in lowered or "income" in lowered:
        for level in ["low", "medium", "high"]:
            if level in lowered:
                return build("Family_Background", "Family_Income", level.capitalize())

    return None


def student_profile_sql(student_id: str) -> str:
    return f"""
SELECT
    s.StudentID,
    s.Gender,
    s.Learning_Disabilities,
    s.Distance_from_Home,
    s.School_Type,
    ap.Attendance,
    ap.Previous_Scores,
    ap.Exam_Score,
    ab.Hours_Studied,
    ab.Sleep_Hours,
    ab.Physical_Activity,
    ab.Motivation_Level,
    ab.Tutoring_Sessions,
    ab.Extracurricular_Activities,
    fb.Family_Income,
    fb.Parental_Education_Level,
    fb.Parental_Involvement,
    se.Teacher_Quality,
    se.Peer_Influence,
    se.Internet_Access,
    se.Access_to_Resources
FROM Students s
LEFT JOIN Academic_Performance ap ON s.StudentID = ap.StudentID
LEFT JOIN Academic_Behavior ab ON s.StudentID = ab.StudentID
LEFT JOIN Family_Background fb ON s.StudentID = fb.StudentID
LEFT JOIN School_Environment se ON s.StudentID = se.StudentID
WHERE s.StudentID = {student_id}
"""


def build_known_sql(question: str, context_student_id: Optional[str]) -> Optional[str]:
    lowered = normalize_question(question)
    message_student_id = extract_student_id(question)
    student_id = message_student_id or (context_student_id if should_use_context_student(question) else None)

    if missing_schema_question(question):
        return "SELECT 'DATA_NOT_AVAILABLE' AS result"

    if not student_id and looks_like_metric_followup(question):
        column = metric_column_from_question(question)
        expression = metric_expression(column) if column else None
        if expression:
            alias = metric_alias_for_column(column)
            return f"SELECT AVG(CAST({expression} AS FLOAT)) AS {alias} {join_all_tables_sql()} WHERE {expression} IS NOT NULL"

    student_percent_sql = student_metric_percent_sql(question, student_id)
    if student_percent_sql:
        return student_percent_sql

    analytics_sql = analytics_calculation_sql(question)
    if analytics_sql:
        return analytics_sql

    threshold_sql = metric_threshold_sql(question)
    if threshold_sql:
        return threshold_sql

    categorical_sql = categorical_filter_sql(question)
    if categorical_sql:
        return categorical_sql

    if not student_id and ("parental involvement" in lowered or ("parent" in lowered and "involvement" in lowered)):
        return f"""
SELECT
    fb.Parental_Involvement AS GroupName,
    COUNT(*) AS StudentCount,
    COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0) AS StudentPercent
{join_all_tables_sql()}
WHERE fb.Parental_Involvement IS NOT NULL
GROUP BY fb.Parental_Involvement
ORDER BY StudentCount DESC
"""

    if not student_id and ("parental education" in lowered or ("parent" in lowered and "education" in lowered)):
        return f"""
SELECT
    fb.Parental_Education_Level AS GroupName,
    COUNT(*) AS StudentCount,
    COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0) AS StudentPercent
{join_all_tables_sql()}
WHERE fb.Parental_Education_Level IS NOT NULL
GROUP BY fb.Parental_Education_Level
ORDER BY StudentCount DESC
"""

    if "highest" in lowered and "who" in lowered:
        return """
SELECT TOP 1
    s.StudentID,
    s.Gender,
    s.Learning_Disabilities,
    s.Distance_from_Home,
    s.School_Type,
    ap.Attendance,
    ap.Previous_Scores,
    ap.Exam_Score,
    ab.Hours_Studied,
    ab.Sleep_Hours,
    ab.Motivation_Level,
    fb.Family_Income,
    se.Internet_Access,
    se.Access_to_Resources
FROM Students s
LEFT JOIN Academic_Performance ap ON s.StudentID = ap.StudentID
LEFT JOIN Academic_Behavior ab ON s.StudentID = ab.StudentID
LEFT JOIN Family_Background fb ON s.StudentID = fb.StudentID
LEFT JOIN School_Environment se ON s.StudentID = se.StudentID
ORDER BY ap.Exam_Score DESC
"""

    if "school type" in lowered or "school types" in lowered:
        if student_id:
            return f"""
SELECT StudentID, School_Type
FROM Students
WHERE StudentID = {student_id}
"""
        return """
SELECT School_Type, COUNT(*) AS StudentCount
FROM Students
GROUP BY School_Type
ORDER BY StudentCount DESC
"""

    if "average" in lowered and ("exam" in lowered or "score" in lowered or "marks" in lowered):
        return "SELECT AVG(CAST(Exam_Score AS FLOAT)) AS AverageExamScore FROM Academic_Performance"

    if "average" in lowered and "attendance" in lowered:
        return "SELECT AVG(CAST(Attendance AS FLOAT)) AS AverageAttendance FROM Academic_Performance"

    if "average" in lowered and ("study" in lowered or "hours studied" in lowered):
        return "SELECT AVG(CAST(Hours_Studied AS FLOAT)) AS AverageStudyHours FROM Academic_Behavior"

    if "average" in lowered and "sleep" in lowered:
        return "SELECT AVG(CAST(Sleep_Hours AS FLOAT)) AS AverageSleepHours FROM Academic_Behavior"

    if re.search(r"\b(how many|count)\b", lowered) and "student" in lowered:
        return "SELECT COUNT(*) AS StudentCount FROM Students"

    if "highest" in lowered and ("exam" in lowered or "score" in lowered or "marks" in lowered):
        return """
SELECT TOP 5 StudentID, Exam_Score
FROM Academic_Performance
ORDER BY Exam_Score DESC
"""

    if "lowest" in lowered and ("exam" in lowered or "score" in lowered or "marks" in lowered):
        return """
SELECT TOP 5 StudentID, Exam_Score
FROM Academic_Performance
ORDER BY Exam_Score ASC
"""

    if "high attendance" in lowered:
        return """
SELECT TOP 20 StudentID, Attendance
FROM Academic_Performance
WHERE Attendance >= 85
ORDER BY Attendance DESC
"""

    if "low attendance" in lowered:
        return """
SELECT TOP 20 StudentID, Attendance
FROM Academic_Performance
WHERE Attendance < 75
ORDER BY Attendance ASC
"""

    if "good marks" in lowered or "good score" in lowered:
        return """
SELECT TOP 20 StudentID, Exam_Score
FROM Academic_Performance
WHERE Exam_Score >= 80
ORDER BY Exam_Score DESC
"""

    if "poor marks" in lowered or "low marks" in lowered or "poor score" in lowered:
        return """
SELECT TOP 20 StudentID, Exam_Score
FROM Academic_Performance
WHERE Exam_Score < 50
ORDER BY Exam_Score ASC
"""

    if student_id:
        if is_analysis_question(question) and (
            "exam" in lowered or "score" in lowered or "marks" in lowered
        ):
            return f"""
SELECT
    s.StudentID,
    s.Gender,
    ap.Exam_Score,
    ap.Attendance,
    ap.Previous_Scores,
    ab.Hours_Studied,
    ab.Sleep_Hours,
    ab.Physical_Activity,
    ab.Motivation_Level,
    ab.Tutoring_Sessions,
    fb.Family_Income,
    fb.Parental_Education_Level,
    fb.Parental_Involvement,
    se.Teacher_Quality,
    se.Peer_Influence,
    se.Internet_Access,
    se.Access_to_Resources
FROM Students s
LEFT JOIN Academic_Performance ap ON s.StudentID = ap.StudentID
LEFT JOIN Academic_Behavior ab ON s.StudentID = ab.StudentID
LEFT JOIN Family_Background fb ON s.StudentID = fb.StudentID
LEFT JOIN School_Environment se ON s.StudentID = se.StudentID
WHERE s.StudentID = {student_id}
"""
        if "attendance" in lowered:
            return f"SELECT StudentID, Attendance FROM Academic_Performance WHERE StudentID = {student_id}"
        if "previous" in lowered:
            return f"SELECT StudentID, Previous_Scores FROM Academic_Performance WHERE StudentID = {student_id}"
        if "exam" in lowered or "score" in lowered or "marks" in lowered or "perform" in lowered:
            return f"SELECT StudentID, Exam_Score, Attendance FROM Academic_Performance WHERE StudentID = {student_id}"
        if "study" in lowered or "hours" in lowered or "sleep" in lowered or "motivation" in lowered or "tutoring" in lowered:
            return f"""
SELECT s.StudentID, s.Gender, ab.Hours_Studied, ab.Sleep_Hours, ab.Motivation_Level, ab.Tutoring_Sessions
FROM Academic_Behavior ab
JOIN Students s ON s.StudentID = ab.StudentID
WHERE s.StudentID = {student_id}
"""
        if "parental involvement" in lowered or ("parent" in lowered and "involvement" in lowered):
            return f"""
SELECT StudentID, Parental_Involvement
FROM Family_Background
WHERE StudentID = {student_id}
"""
        if "parental education" in lowered or ("parent" in lowered and "education" in lowered):
            return f"""
SELECT StudentID, Parental_Education_Level
FROM Family_Background
WHERE StudentID = {student_id}
"""
        if "family" in lowered or "parent" in lowered or "income" in lowered:
            return f"""
SELECT StudentID, Family_Income, Parental_Education_Level, Parental_Involvement
FROM Family_Background
WHERE StudentID = {student_id}
"""
        if "internet" in lowered or "resource" in lowered or "teacher" in lowered or "peer" in lowered:
            return f"""
SELECT StudentID, Internet_Access, Access_to_Resources, Teacher_Quality, Peer_Influence
FROM School_Environment
WHERE StudentID = {student_id}
"""
        if "gender" in lowered or "school" in lowered or "distance" in lowered or "disabil" in lowered:
            return f"""
SELECT StudentID, Gender, Learning_Disabilities, Distance_from_Home, School_Type
FROM Students
WHERE StudentID = {student_id}
"""
        return student_profile_sql(student_id)

    if "student" in lowered and any(word in lowered for word in ["show", "list", "all", "students", "records"]):
        return """
SELECT TOP 20
    s.StudentID,
    s.Gender,
    s.School_Type,
    s.Distance_from_Home,
    ap.Exam_Score,
    ap.Attendance
FROM Students s
LEFT JOIN Academic_Performance ap ON s.StudentID = ap.StudentID
ORDER BY s.StudentID
"""

    return None


def humanize_label(column: str) -> str:
    labels = {
        "StudentID": "StudentID",
        "StudentCount": "students",
        "CourseCount": "courses",
        "FullName": "full name",
        "Email": "email",
        "CurrentYear": "current year",
        "CurrentSemester": "current semester",
        "GroupCode": "group",
        "DepartmentCode": "department code",
        "DepartmentName": "department",
        "Status": "status",
        "AcademicYear": "academic year",
        "Semester": "semester",
        "SemesterGPA": "semester GPA",
        "AverageSemesterGPA": "average semester GPA",
        "ThirdYearCumulativeGPA": "third-year cumulative GPA",
        "CumulativeGPA": "cumulative GPA",
        "CourseCode": "course code",
        "CourseName": "course",
        "CreditHours": "credit hours",
        "TotalMarks": "total marks",
        "CourseYear": "course year",
        "CourseSemester": "course semester",
        "Category": "category",
        "InstructorID": "instructor ID",
        "InstructorTitle": "title",
        "InstructorName": "instructor",
        "RoomName": "room",
        "RoomType": "room type",
        "Capacity": "capacity",
        "Building": "building",
        "DayOfWeek": "day",
        "StartTime": "start time",
        "EndTime": "end time",
        "SectionType": "section type",
        "TargetGroup": "target group",
        "RawScore": "raw score",
        "Percentage": "percentage",
        "GradeLetter": "grade",
        "PassStatus": "pass status",
        "MaleStudents": "male students",
        "FemaleStudents": "female students",
        "School_Type": "school type",
        "AverageExamScore": "average exam score",
        "AverageAttendance": "average attendance",
        "AveragePreviousScore": "average previous score",
        "AverageStudyHours": "average study hours",
        "AverageSleepHours": "average sleep hours",
        "AverageTutoringSessions": "average tutoring sessions",
        "AveragePhysicalActivity": "average physical activity",
        "HighestExamScore": "highest exam score",
        "HighestAttendance": "highest attendance",
        "HighestPreviousScore": "highest previous score",
        "HighestStudyHours": "highest study hours",
        "HighestSleepHours": "highest sleep hours",
        "HighestTutoringSessions": "highest tutoring sessions",
        "LowestExamScore": "lowest exam score",
        "LowestAttendance": "lowest attendance",
        "LowestPreviousScore": "lowest previous score",
        "LowestStudyHours": "lowest study hours",
        "LowestSleepHours": "lowest sleep hours",
        "LowestTutoringSessions": "lowest tutoring sessions",
        "TotalExamScore": "total exam score",
        "TotalAttendance": "total attendance",
        "TotalPreviousScore": "total previous score",
        "TotalStudyHours": "total study hours",
        "TotalSleepHours": "total sleep hours",
        "TotalTutoringSessions": "total tutoring sessions",
        "StandardDeviationExamScore": "standard deviation of exam score",
        "StandardDeviationAttendance": "standard deviation of attendance",
        "StandardDeviationStudyHours": "standard deviation of study hours",
        "StandardDeviationSleepHours": "standard deviation of sleep hours",
        "VarianceExamScore": "variance of exam score",
        "VarianceAttendance": "variance of attendance",
        "VarianceStudyHours": "variance of study hours",
        "VarianceSleepHours": "variance of sleep hours",
        "CorrelationStudyHoursExamScore": "study-hours/exam-score relationship",
        "MatchingStudents": "matching students",
        "TotalStudents": "total students",
        "StudentPercent": "student percentage",
        "PercentOfAverageExamScore": "percentage of average exam score",
        "PercentOfAverageAttendance": "percentage of average attendance",
        "PercentOfAveragePreviousScore": "percentage of average previous score",
        "PercentOfAverageStudyHours": "percentage of average study hours",
        "PercentOfAverageSleepHours": "percentage of average sleep hours",
        "PercentOfAverageTutoringSessions": "percentage of average tutoring sessions",
        "PercentOfAveragePhysicalActivity": "percentage of average physical activity",
        "GroupName": "group",
        "Exam_Score": "exam score",
        "Previous_Scores": "previous score",
        "Hours_Studied": "study hours",
        "Sleep_Hours": "sleep hours",
        "Learning_Disabilities": "learning disabilities",
        "Distance_from_Home": "distance from home",
        "Internet_Access": "internet access",
        "Access_to_Resources": "resource access",
        "Motivation_Level": "motivation",
        "Family_Income": "family income",
        "Teacher_Quality": "teacher quality",
        "Peer_Influence": "peer influence",
        "Parental_Education_Level": "parental education",
        "Parental_Involvement": "parental involvement",
        "Tutoring_Sessions": "tutoring sessions",
        "Physical_Activity": "physical activity",
    }
    return labels.get(column, column.replace("_", " ").lower())


def format_value(value: Any) -> str:
    if value is None:
        return "not recorded"
    if isinstance(value, (float, Decimal)):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def average_semester_gpa_from_rows(data_rows: Sequence[Dict[str, Any]]) -> str:
    values = [
        as_float(row.get("SemesterGPA"))
        for row in data_rows
        if row.get("SemesterGPA") is not None
    ]
    values = [value for value in values if value is not None]
    if not values:
        return "not recorded"
    return format_value(sum(values) / len(values))


def computed_cumulative_gpa_for_student(student_id: str) -> str:
    if not student_id or student_id == "not recorded":
        return "not recorded"
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql_query = f"""
SELECT AVG(CAST(semester_gpa AS FLOAT)) AS ComputedCumulativeGPA
FROM GPA_Records
WHERE {fci_student_id_condition("student_id", student_id)}
  AND semester_gpa IS NOT NULL
"""
        cursor.execute(adapt_sql_for_configured_database(sql_query))
        row = cursor.fetchone()
        if row and row[0] is not None:
            return format_value(row[0])
    except Exception:
        return "not recorded"
    finally:
        if conn:
            conn.close()
    return "not recorded"


def format_column_value(column: str, value: Any) -> str:
    if column in {"Internet_Access", "Learning_Disabilities", "Extracurricular_Activities"}:
        if str(value) == "1":
            return "yes"
        if str(value) == "0":
            return "no"
    return format_value(value)


def as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def student_pronouns(gender: Any) -> tuple:
    gender_text = str(gender).strip().lower()
    if gender_text == "male":
        return "he", "his"
    if gender_text == "female":
        return "she", "her"
    return "this student", "this student's"


def join_natural(items: Sequence[str]) -> str:
    items = [item for item in items if item]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def score_change_phrase(exam_score: Any, previous_score: Any, possessive: str) -> str:
    exam = as_float(exam_score)
    previous = as_float(previous_score)
    if exam is None or previous is None:
        return ""

    change = exam - previous
    if abs(change) < 0.5:
        return f"about the same as {possessive} previous score"

    points = f"{abs(change):.1f}".rstrip("0").rstrip(".")
    point_word = "point" if points == "1" else "points"
    if change < 0:
        tone = "tiny " if abs(change) <= 1.5 else ""
        return f"a {tone}drop of {points} {point_word} from {possessive} previous score"
    tone = "small " if change <= 1.5 else ""
    return f"a {tone}rise of {points} {point_word} from {possessive} previous score"


def conversational_student_profile(data: Dict[str, Any]) -> str:
    student_id = data.get("StudentID", "this student")
    subject, possessive = student_pronouns(data.get("Gender"))
    gender = str(data.get("Gender", "")).strip().lower()
    school_type = format_column_value("School_Type", data.get("School_Type"))
    distance = format_column_value("Distance_from_Home", data.get("Distance_from_Home"))
    exam = format_column_value("Exam_Score", data.get("Exam_Score"))
    previous = format_column_value("Previous_Scores", data.get("Previous_Scores"))
    attendance = format_column_value("Attendance", data.get("Attendance"))
    hours = format_column_value("Hours_Studied", data.get("Hours_Studied"))
    sleep = format_column_value("Sleep_Hours", data.get("Sleep_Hours"))
    physical = format_column_value("Physical_Activity", data.get("Physical_Activity"))
    motivation = format_column_value("Motivation_Level", data.get("Motivation_Level"))
    tutoring = format_column_value("Tutoring_Sessions", data.get("Tutoring_Sessions"))
    extracurricular = format_column_value("Extracurricular_Activities", data.get("Extracurricular_Activities"))
    family_income = format_column_value("Family_Income", data.get("Family_Income"))
    parental_education = format_column_value("Parental_Education_Level", data.get("Parental_Education_Level"))
    parental_involvement = format_column_value("Parental_Involvement", data.get("Parental_Involvement"))
    resources = format_column_value("Access_to_Resources", data.get("Access_to_Resources"))
    internet = format_column_value("Internet_Access", data.get("Internet_Access"))
    teacher_quality = format_column_value("Teacher_Quality", data.get("Teacher_Quality"))
    peer_influence = format_column_value("Peer_Influence", data.get("Peer_Influence"))

    intro_bits = []
    if gender:
        intro_bits.append(f"a {gender} student")
    if school_type != "not recorded":
        intro_bits.append(f"from a {school_type.lower()} school")

    if intro_bits:
        intro = f"StudentID {student_id} is " + " ".join(intro_bits) + "."
    else:
        intro = f"StudentID {student_id} is in the database."

    location = ""
    if distance != "not recorded":
        location = f" Distance from home is listed as {distance.lower()}."

    academic_parts = []
    if exam != "not recorded":
        score_part = f"{subject.capitalize()} scored {exam} in the exam"
        change = score_change_phrase(data.get("Exam_Score"), data.get("Previous_Scores"), possessive)
        if change:
            score_part += f", {change}"
        elif previous != "not recorded":
            score_part += f", with a previous score of {previous}"
        academic_parts.append(score_part)
    elif previous != "not recorded":
        academic_parts.append(f"{subject.capitalize()} has a previous score of {previous}")

    if attendance != "not recorded":
        academic_parts.append(f"{possessive.capitalize()} attendance is {attendance}%")

    academic_sentence = ""
    if academic_parts:
        academic_sentence = " " + ". ".join(academic_parts) + "."

    habits = []
    if hours != "not recorded":
        habits.append(f"{hours} study hours")
    if sleep != "not recorded":
        habits.append(f"{sleep} hours of sleep")
    if motivation != "not recorded":
        habits.append(f"{motivation.lower()} motivation")
    if tutoring != "not recorded":
        habits.append(f"{tutoring} tutoring sessions")
    if physical != "not recorded":
        habits.append(f"{physical} physical activity")
    if extracurricular != "not recorded":
        habits.append(f"extracurricular activities: {extracurricular}")

    habit_sentence = ""
    if habits:
        habit_sentence = f" Study-wise, {subject} has {join_natural(habits)}."

    family = []
    if family_income != "not recorded":
        family.append(f"family income is {family_income.lower()}")
    if parental_education != "not recorded":
        family.append(f"parental education is {parental_education.lower()}")
    if parental_involvement != "not recorded":
        family.append(f"parental involvement is {parental_involvement.lower()}")

    family_sentence = ""
    if family:
        family_sentence = " Family-wise, " + join_natural(family) + "."

    support = []
    if internet != "not recorded":
        if internet == "yes":
            support.append("internet access is available")
        elif internet == "no":
            support.append("internet access is not available")
        else:
            support.append(f"internet access is {internet}")
    if resources != "not recorded":
        support.append(f"resource access is {resources.lower()}")
    if teacher_quality != "not recorded":
        support.append(f"teacher quality is {teacher_quality.lower()}")
    if peer_influence != "not recorded":
        support.append(f"peer influence is {peer_influence.lower()}")

    support_sentence = ""
    if support:
        support_sentence = " For support, " + join_natural(support) + "."

    return intro + location + academic_sentence + habit_sentence + family_sentence + support_sentence


def comparison_words(operator: str) -> str:
    return {
        ">": "more than",
        ">=": "at least",
        "<": "less than",
        "<=": "at most",
        "=": "exactly",
    }.get(operator, operator)


def categorical_count_phrase(question: str) -> Optional[str]:
    lowered = normalize_question(question)
    gender = gender_from_question(lowered)
    if gender:
        return gender.lower()
    if "school" in lowered:
        if "private" in lowered:
            return "private school students"
        if "public" in lowered:
            return "public school students"
    for level in ["low", "medium", "high"]:
        if "motivation" in lowered and level in lowered:
            return f"{level} motivation"
        if ("resource" in lowered or "resources" in lowered) and (level in lowered or (level == "low" and "limited" in lowered)):
            return f"{level} resource access"
        if ("family income" in lowered or "income" in lowered) and level in lowered:
            return f"{level} family income"
    if "internet" in lowered:
        if any(phrase in lowered for phrase in ["no internet", "without internet", "do not have internet"]):
            return "no internet access"
        return "internet access"
    if "learning disabil" in lowered:
        return "learning disabilities"
    return None


def average_answer(label: str, value: Any) -> str:
    number = format_value(value)
    if label == "average study hours":
        return f"Students study about {number} hours on average."
    if label == "average sleep hours":
        return f"Students sleep about {number} hours on average."
    if label == "average attendance":
        return f"Average attendance is about {number}%."
    if label == "average exam score":
        return f"The average exam score is about {number}."
    return f"The {label} is about {number}."


def aggregate_answer(label: str, value: Any) -> str:
    number = format_value(value)
    if label.startswith("total "):
        return f"The {label} adds up to {number}."
    if label.startswith("standard deviation") or label.startswith("variance"):
        return f"The {label} is about {number}."
    return f"The {label} is {number}."


def correlation_answer(value: Any) -> str:
    number = as_float(value)
    if number is None:
        return "I couldn't calculate the relationship from the available data."
    strength = "very weak"
    abs_value = abs(number)
    if abs_value >= 0.7:
        strength = "strong"
    elif abs_value >= 0.4:
        strength = "moderate"
    elif abs_value >= 0.2:
        strength = "weak"
    direction = "positive" if number > 0 else "negative"
    return (
        f"The study-hours to exam-score relationship is {direction} but {strength} "
        f"(correlation {format_value(number)})."
    )


def percent_answer(columns: Sequence[str], row: Any, question: str) -> str:
    data = dict(zip(columns, list(row)))
    matching = format_value(data.get("MatchingStudents"))
    total = format_value(data.get("TotalStudents"))
    percent = format_value(data.get("StudentPercent"))
    phrase = categorical_count_phrase(question) or "that condition"
    if phrase in {"male", "female"}:
        return f"{matching} out of {total} students are {phrase}, which is about {percent}%."
    if phrase == "private school students":
        return f"{matching} out of {total} students are from private schools, which is about {percent}%."
    if phrase == "public school students":
        return f"{matching} out of {total} students are from public schools, which is about {percent}%."
    verb = "match" if phrase == "that condition" else "have"
    return f"{matching} out of {total} students {verb} {phrase}, which is about {percent}%."


def metric_unit(column: str) -> str:
    if column in {"Attendance", "PercentOfAverageAttendance"}:
        return "%"
    if column in {"Hours_Studied", "Sleep_Hours", "AverageStudyHours", "AverageSleepHours"}:
        return " hours"
    return ""


def student_percent_of_average_answer(columns: Sequence[str], row: Any) -> Optional[str]:
    if "StudentID" not in columns:
        return None

    data = dict(zip(columns, list(row)))
    for metric_column in [
        "Exam_Score",
        "Attendance",
        "Previous_Scores",
        "Hours_Studied",
        "Sleep_Hours",
        "Tutoring_Sessions",
        "Physical_Activity",
    ]:
        percent_column = metric_percent_alias_for_column(metric_column)
        average_column = metric_alias_for_column(metric_column)
        if percent_column not in columns or average_column not in columns or metric_column not in columns:
            continue

        student_id = data.get("StudentID")
        value = format_value(data.get(metric_column))
        average = format_value(data.get(average_column))
        percent = format_value(data.get(percent_column))
        label = humanize_label(metric_column)
        unit = metric_unit(metric_column)
        average_unit = metric_unit(average_column)

        if metric_column == "Hours_Studied":
            return (
                f"StudentID {student_id} studied {value}{unit}. That's about {percent}% "
                f"of the overall average study hours ({average}{average_unit})."
            )
        if metric_column == "Sleep_Hours":
            return (
                f"StudentID {student_id} sleeps {value}{unit}. That's about {percent}% "
                f"of the overall average sleep hours ({average}{average_unit})."
            )
        return (
            f"StudentID {student_id}'s {label} is {value}{unit}. That's about {percent}% "
            f"of the overall {humanize_label(average_column)} ({average}{average_unit})."
        )

    return None


def single_student_fact_answer(columns: Sequence[str], row: Any) -> Optional[str]:
    if "StudentID" not in columns:
        return None

    data = dict(zip(columns, list(row)))
    fact_columns = [
        column
        for column in columns
        if column != "StudentID" and data.get(column) is not None
    ]
    if not fact_columns or len(fact_columns) > 4:
        return None

    student_id = data.get("StudentID")
    parts = []
    for column in fact_columns:
        rendered = format_column_value(column, data.get(column))
        suffix = "%" if column == "Attendance" and rendered != "not recorded" else ""
        parts.append(f"{humanize_label(column)} is {rendered}{suffix}")

    if len(parts) == 1:
        return f"StudentID {student_id}'s {parts[0]}."
    return f"For StudentID {student_id}: " + "; ".join(parts) + "."


def group_average_answer(columns: Sequence[str], rows: Sequence[Any]) -> Optional[str]:
    if "GroupName" not in columns or "StudentCount" not in columns:
        return None
    average_columns = [column for column in columns if column.startswith("Average")]
    if not average_columns:
        return None

    average_column = average_columns[0]
    label = humanize_label(average_column)
    group_index = list(columns).index("GroupName")
    average_index = list(columns).index(average_column)
    count_index = list(columns).index("StudentCount")
    parts = []
    for row in rows:
        group = format_value(row[group_index])
        average = format_value(row[average_index])
        count = format_value(row[count_index])
        parts.append(f"{group}: {average} across {count} students")
    return f"Here is the {label} comparison: " + "; ".join(parts) + "."


def group_count_answer(columns: Sequence[str], rows: Sequence[Any]) -> Optional[str]:
    if "GroupName" not in columns or "StudentCount" not in columns:
        return None

    group_index = list(columns).index("GroupName")
    count_index = list(columns).index("StudentCount")
    percent_index = list(columns).index("StudentPercent") if "StudentPercent" in columns else None
    parts = []
    for row in rows:
        group = format_value(row[group_index])
        count = format_value(row[count_index])
        if percent_index is not None:
            percent = format_value(row[percent_index])
            parts.append(f"{group}: {count} students ({percent}%)")
        else:
            parts.append(f"{group}: {count} students")
    return "Here's the breakdown: " + "; ".join(parts) + "."


def fci_student_profile_answer(columns: Sequence[str], row: Any) -> Optional[str]:
    if "StudentID" not in columns or "FullName" not in columns:
        return None

    data = dict(zip(columns, list(row)))
    student_id = format_value(data.get("StudentID"))
    full_name = format_value(data.get("FullName"))
    group_code = format_value(data.get("GroupCode"))
    department = format_value(data.get("DepartmentName"))
    year = format_value(data.get("CurrentYear"))
    semester = format_value(data.get("CurrentSemester"))
    status = format_value(data.get("Status"))
    email = format_value(data.get("Email"))
    cumulative = format_value(data.get("CumulativeGPA"))
    third_year = format_value(data.get("ThirdYearCumulativeGPA"))
    if cumulative == "not recorded" and third_year == "not recorded":
        cumulative = computed_cumulative_gpa_for_student(student_id)

    sentence = f"{full_name} (StudentID {student_id})"
    details = []
    if status != "not recorded":
        details.append(status)
    if year != "not recorded":
        details.append(f"year {year}")
    if semester != "not recorded":
        details.append(f"semester {semester}")
    if group_code != "not recorded":
        details.append(f"group {group_code}")
    if department != "not recorded":
        details.append(department)

    if details:
        sentence += " is " + ", ".join(details) + "."
    else:
        sentence += " is in the FCI database."

    gpa_value = cumulative if cumulative != "not recorded" else third_year
    sentence += f" Email: {email}; cumulative GPA: {gpa_value}."
    return sentence


def fci_gpa_records_answer(columns: Sequence[str], rows: Sequence[Any], question: str = "") -> Optional[str]:
    column_set = set(columns)
    if not {"StudentID", "FullName"}.issubset(column_set):
        return None
    gpa_columns = {
        "AcademicYear",
        "Semester",
        "SemesterGPA",
        "SemesterCumulativeGPA",
        "ThirdYearCumulativeGPA",
        "CumulativeGPA",
    }
    if not column_set.intersection(gpa_columns):
        return None
    if not text_has_any(semantic_normalize(question), ["gpa", "cgpa", "معدل", "المعدل"]) and not {
        "SemesterGPA",
        "AcademicYear",
        "Semester",
    }.intersection(column_set):
        return None
    data_rows = [dict(zip(columns, list(row))) for row in rows]
    student_ids = {str(row.get("StudentID")) for row in data_rows if row.get("StudentID") is not None}
    if len(student_ids) != 1:
        return None

    first = data_rows[0]
    full_name = format_value(first.get("FullName"))
    student_id = format_value(first.get("StudentID"))
    semester_rows = [
        row
        for row in data_rows
        if row.get("Semester") is not None
        and row.get("AcademicYear") is not None
        and row.get("SemesterGPA") is not None
    ]
    cumulative = next(
        (
            format_value(row.get("CumulativeGPA"))
            for row in data_rows
            if row.get("CumulativeGPA") is not None and format_value(row.get("CumulativeGPA")) != "not recorded"
        ),
        format_value(first.get("ThirdYearCumulativeGPA")),
    )
    if cumulative == "not recorded":
        cumulative = average_semester_gpa_from_rows(semester_rows)
    if not semester_rows and cumulative == "not recorded":
        return gpa_not_found_fallback(full_name, question)

    lines = [f"{full_name} (StudentID {student_id}) — Academic Record:"]
    for row in semester_rows:
        lines.append(
            f"- Semester {format_value(row.get('Semester'))} ({format_value(row.get('AcademicYear'))}): "
            f"GPA {format_value(row.get('SemesterGPA'))}"
        )
    if cumulative != "not recorded":
        lines.append(f"Overall Cumulative GPA: {cumulative}")
    return "\n".join(lines)


def fci_schedule_answer(columns: Sequence[str], rows: Sequence[Any]) -> Optional[str]:
    required = {
        "DayOfWeek",
        "StartTime",
        "EndTime",
        "CourseCode",
        "CourseName",
        "InstructorName",
        "RoomName",
        "TargetGroup",
    }
    if not required.issubset(set(columns)):
        return None

    data_rows = [dict(zip(columns, list(row))) for row in rows]
    if len(data_rows) == 1:
        row = data_rows[0]
        section_type = format_value(row.get("SectionType"))
        if section_type == "not recorded":
            section_type = "class"
        return (
            f"📅 {format_value(row.get('DayOfWeek'))} {format_value(row.get('StartTime'))}–{format_value(row.get('EndTime'))}\n"
            f"   📚 {format_value(row.get('CourseName'))} ({format_value(row.get('CourseCode'))})\n"
            f"   👤 {format_value(row.get('InstructorName'))}\n"
            f"   🏛️ {format_value(row.get('RoomName'))}\n"
            f"   👥 Group: {format_value(row.get('TargetGroup'))} | {section_type}"
        )

    lines = [f"I found {len(data_rows)} scheduled classes:"]
    for row in data_rows:
        lines.append(
            f"- {format_value(row.get('DayOfWeek'))} {format_value(row.get('StartTime'))}–{format_value(row.get('EndTime'))} | "
            f"{format_value(row.get('CourseName'))} | {format_value(row.get('InstructorName'))} | "
            f"{format_value(row.get('RoomName'))} | Group {format_value(row.get('TargetGroup'))}"
        )
    return "\n".join(lines)


def student_bulk_listing_line(data: Dict[str, Any]) -> str:
    return (
        f"- {format_value(data.get('FullName'))} "
        f"(StudentID {format_value(data.get('StudentID'))}), "
        f"group {format_value(data.get('GroupCode'))}, "
        f"{format_value(data.get('DepartmentName'))}"
    )


def student_bulk_listing_answer(
    columns: Sequence[str],
    rows: Sequence[Any],
    question: str = "",
    row_limit: int = 10,
) -> Optional[str]:
    column_set = set(columns)
    if len(rows) <= 1:
        return None
    required = {"StudentID", "FullName", "GroupCode", "DepartmentName"}
    if not required.issubset(column_set):
        return None
    detail_columns = {
        "AcademicYear",
        "SemesterGPA",
        "ThirdYearCumulativeGPA",
        "CumulativeGPA",
        "RawScore",
        "TotalMarks",
        "Percentage",
        "GradeLetter",
        "GradePoint",
        "PassStatus",
        "CourseCode",
        "CourseName",
        "DayOfWeek",
        "StartTime",
        "EndTime",
        "RoomName",
        "Attendance",
        "Exam_Score",
    }
    if column_set.intersection(detail_columns):
        return None

    shown_rows = rows[:row_limit]
    prefix = f"I found {len(rows)} matching students"
    if len(rows) > row_limit:
        prefix += f". Here are the first {row_limit}:"
    else:
        prefix += ":"
    lines = []
    for row in shown_rows:
        data = dict(zip(columns, list(row)))
        lines.append(student_bulk_listing_line(data))
    if len(rows) > row_limit:
        lines.append('Say "next" or "show more" to continue, or "all of them" to show the rest.')
    return prefix + "\n" + "\n".join(lines)


def fci_single_course_grade_answer(columns: Sequence[str], row: Any) -> Optional[str]:
    required = {"StudentID", "FullName", "CourseCode", "CourseName", "RawScore", "TotalMarks"}
    if not required.issubset(set(columns)):
        return None

    data = dict(zip(columns, list(row)))
    full_name = format_value(data.get("FullName"))
    student_id = format_value(data.get("StudentID"))
    course_code = format_value(data.get("CourseCode"))
    course_name = format_value(data.get("CourseName"))
    raw_score = format_value(data.get("RawScore"))
    total_marks = format_value(data.get("TotalMarks"))
    percentage = format_value(data.get("Percentage"))
    grade = format_value(data.get("GradeLetter"))
    pass_status = format_value(data.get("PassStatus"))

    answer = (
        f"{full_name} (StudentID {student_id}) got {raw_score}/{total_marks} "
        f"in {course_code} - {course_name}"
    )
    if percentage != "not recorded":
        answer += f", which is {percentage}%"
    if grade != "not recorded":
        answer += f" with grade {grade}"
    if pass_status != "not recorded":
        answer += f" ({pass_status})"
    return answer + "."


def count_answer(value: Any, question: str) -> str:
    count_text = format_value(value)
    count_num = as_float(value)
    student_word = "student" if count_num == 1 else "students"
    category = categorical_count_phrase(question)
    if category:
        if category in {"male", "female"}:
            return f"{count_text} {student_word} are {category}."
        if category == "private school students":
            return f"{count_text} {student_word} are from private schools."
        if category == "public school students":
            return f"{count_text} {student_word} are from public schools."
        return f"{count_text} {student_word} have {category}."
    column = metric_column_from_question(question)
    comparison = extract_numeric_comparison(question)
    if column and comparison:
        operator, threshold = comparison
        label = humanize_label(column)
        unit = "%" if column == "Attendance" else ""
        article = "an " if label[0].lower() in "aeiou" else "a "
        if column == "Attendance":
            return f"{count_text} {student_word} have attendance {comparison_words(operator)} {threshold}{unit}."
        return f"{count_text} {student_word} have {article}{label} {comparison_words(operator)} {threshold}{unit}."
    return f"I have {count_text} student records in this database right now."


def answer_from_rows(
    columns: Sequence[str],
    rows: Sequence[Any],
    question: str = "",
    row_limit: int = 10,
) -> str:
    lowered = normalize_question(question)

    if len(rows) == 1 and len(columns) == 1:
        label = humanize_label(columns[0])
        value = format_value(rows[0][0])
        if columns[0] == "StudentCount":
            return count_answer(rows[0][0], question)
        if columns[0] == "CourseCount":
            return f"I found {value} courses in the FCI database."
        if columns[0] == "MaleStudents":
            return f"{value} students are male."
        if columns[0] == "FemaleStudents":
            return f"{value} students are female."
        if columns[0].startswith("Average"):
            return average_answer(label, rows[0][0])
        if columns[0].startswith(("Highest", "Lowest", "Total", "StandardDeviation", "Variance")):
            return aggregate_answer(label, rows[0][0])
        if columns[0].startswith("Correlation"):
            return correlation_answer(rows[0][0])
        return f"The {label} is {value}."

    if len(rows) == 1 and {"MatchingStudents", "TotalStudents", "StudentPercent"}.issubset(set(columns)):
        return percent_answer(columns, rows[0], question)

    grouped_average = group_average_answer(columns, rows)
    if grouped_average:
        return grouped_average

    grouped_count = group_count_answer(columns, rows)
    if grouped_count:
        return grouped_count

    gpa_records = fci_gpa_records_answer(columns, rows, question)
    if gpa_records:
        return gpa_records

    schedule_answer = fci_schedule_answer(columns, rows)
    if schedule_answer:
        return schedule_answer

    if set(columns) == {"School_Type", "StudentCount"}:
        parts = [
            f"{format_value(row[0])}: {format_value(row[1])}"
            for row in rows
        ]
        return "The school types in this database are " + ", ".join(parts) + "."

    if len(rows) == 1 and {"StudentID", "Exam_Score"}.issubset(set(columns)) and len(columns) <= 3:
        data = dict(zip(columns, list(rows[0])))
        student_id = data.get("StudentID")
        score = data.get("Exam_Score")
        attendance = data.get("Attendance")
        if attendance is not None:
            return f"StudentID {student_id}'s exam score is {score}, with attendance at {attendance}%."
        return f"StudentID {student_id}'s exam score is {score}."

    if len(rows) == 1 and {"StudentID", "Attendance"} == set(columns):
        data = dict(zip(columns, list(rows[0])))
        return f"StudentID {data.get('StudentID')}'s attendance is {data.get('Attendance')}%."

    if "InstructorName" in columns and "InstructorID" in columns:
        first = dict(zip(columns, list(rows[0])))
        title = format_value(first.get("InstructorTitle"))
        name = format_value(first.get("InstructorName"))
        email = format_value(first.get("Email"))
        display_name = f"{title} {name}".replace("not recorded", "").replace("  ", " ").strip()
        lines = [f"I found {display_name} in the FCI instructor data."]
        if email != "not recorded":
            lines.append(f"Email: {email}.")
        assignments = []
        for row in rows:
            data = dict(zip(columns, list(row)))
            course_code = format_value(data.get("CourseCode"))
            course_name = format_value(data.get("CourseName"))
            if course_code == "not recorded" and course_name == "not recorded":
                continue
            assignments.append(
                f"- {course_code} {course_name} for {format_value(data.get('TargetGroup'))} "
                f"({format_value(data.get('SectionType'))})"
            )
        if assignments:
            lines.append("Teaching assignments I found:")
            lines.extend(assignments[:row_limit])
        return "\n".join(lines)

    if len(rows) == 1:
        percent_of_average = student_percent_of_average_answer(columns, rows[0])
        if percent_of_average:
            return percent_of_average

        student_fact = single_student_fact_answer(columns, rows[0])
        if student_fact:
            return student_fact

    if len(rows) == 1 and "StudentID" in columns and not is_analysis_question(question):
        course_grade = fci_single_course_grade_answer(columns, rows[0])
        if course_grade:
            return course_grade
        fci_profile = fci_student_profile_answer(columns, rows[0])
        if fci_profile:
            return fci_profile
        data = dict(zip(columns, list(rows[0])))
        return conversational_student_profile(data)

    if len(rows) == 1 and is_analysis_question(question) and "Exam_Score" in columns and "Hours_Studied" in columns:
        values = list(rows[0])
        data = dict(zip(columns, values))
        student_id = data.get("StudentID", "that student")
        strongest = [
            "exam score",
            format_value(data.get("Exam_Score")),
            "attendance",
            f"{format_value(data.get('Attendance'))}%",
            "previous score",
            format_value(data.get("Previous_Scores")),
            "study hours",
            format_value(data.get("Hours_Studied")),
            "sleep hours",
            format_value(data.get("Sleep_Hours")),
            "motivation",
            format_value(data.get("Motivation_Level")),
            "tutoring sessions",
            format_value(data.get("Tutoring_Sessions")),
            "resource access",
            format_column_value("Access_to_Resources", data.get("Access_to_Resources")),
        ]
        pairs = [f"{strongest[i]}: {strongest[i + 1]}" for i in range(0, len(strongest), 2)]
        return (
            f"I can't prove the exact cause from this database, but I can read the pattern. "
            f"For StudentID {student_id}, the main recorded factors are " + "; ".join(pairs) + ". "
            "So I would treat this as a data-based explanation, not a guaranteed cause."
        )

    student_listing = student_bulk_listing_answer(columns, rows, question, row_limit)
    if student_listing:
        return student_listing

    shown_rows = rows[:row_limit]
    lines = []
    for row in shown_rows:
        values = list(row)
        parts = []
        for column, value in zip(columns, values):
            rendered = format_column_value(column, value)
            suffix = "%" if column == "Attendance" and rendered != "not recorded" else ""
            parts.append(f"{humanize_label(column)}: {rendered}{suffix}")
        lines.append("- " + "; ".join(parts))

    if "CourseCode" in columns and ("RawScore" in columns or "GradeLetter" in columns):
        prefix = f"I found {len(rows)} matching course grade record"
        if len(rows) != 1:
            prefix += "s"
    elif "StudentID" in columns:
        prefix = f"Sure, I found {len(rows)} matching student"
        if len(rows) != 1:
            prefix += "s"
    else:
        prefix = f"I found {len(rows)} matching row"
        if len(rows) != 1:
            prefix += "s"

    if len(rows) > row_limit:
        prefix += f". Here are the first {row_limit}:"
    else:
        prefix += ":"
    more_hint = ""
    if "StudentID" in columns and len(rows) > row_limit:
        more_hint = '\nSay "next" or "show more" to continue, or "all of them" to show the rest.'
    return prefix + "\n" + "\n".join(lines) + more_hint


def infer_query_scope(columns: Sequence[str], next_student_id: Optional[str]) -> str:
    if next_student_id:
        return "student"
    if any(
        column.startswith(("Average", "Highest", "Lowest", "Total", "StandardDeviation", "Variance", "Correlation"))
        for column in columns
    ):
        return "aggregate"
    if "StudentPercent" in columns or ("GroupName" in columns and "StudentCount" in columns):
        return "aggregate"
    return "list"


def answer_student_why_followup(dispatcher: CollectingDispatcher, student_id: str) -> List[Dict[Text, Any]]:
    sql_query = fci_student_profile_sql(student_id)
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(adapt_sql_for_configured_database(sql_query))
        rows = cursor.fetchall()
        columns = cursor_column_names(cursor)

        if not rows:
            dispatcher.utter_message(text=database_no_match_fallback(f"student {student_id}"))
            return [SlotSet("student_id", student_id), SlotSet("last_query_scope", "student")]

        profile = answer_from_rows(columns, rows, "show this student profile")
        answer = (
            "The FCI database can show this student's profile, GPA, courses, and schedule, "
            "but it does not store causal factors like attendance, study hours, or behavior notes. "
            + profile
        )

        dispatcher.utter_message(text=answer)
        return [SlotSet("student_id", student_id), SlotSet("last_query_scope", "student")]
    except Exception:
        dispatcher.utter_message(text=student_not_found_fallback(student_id, f"student {student_id}"))
        return [SlotSet("student_id", student_id), SlotSet("last_query_scope", "student")]
    finally:
        if conn:
            conn.close()


class ActionShowStudents(Action):
    def name(self) -> Text:
        return "action_show_students"

    def run(self, dispatcher, tracker, domain):
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    s.student_id AS StudentID,
                    s.full_name AS FullName,
                    s.group_code AS GroupCode,
                    s.dept_name AS DepartmentName
                FROM v_rasa_students s
                ORDER BY s.group_code, s.full_name
            """)

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                dispatcher.utter_message(text=student_affairs_fallback("student"))
                return []

            lines = []
            for r in rows:
                lines.append(
                    f"- {format_value(r[1])} (StudentID {format_value(r[0])}), "
                    f"group {format_value(r[2])}, {format_value(r[3])}"
                )

            dispatcher.utter_message(
                text=f"Here are all {len(rows)} students:\n" + "\n".join(lines)
            )
            return []

        except Exception:
            dispatcher.utter_message(text=student_affairs_fallback(""))
            return []


class ActionCheckStudentExists(Action):
    def name(self) -> Text:
        return "action_check_student_exists"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        text = tracker.latest_message.get("text", "").lower()
        entities = tracker.latest_message.get("entities", [])

        extracted_name = None
        for entity in entities:
            if entity.get("entity") == "student_name":
                extracted_name = entity.get("value")
                break

        try:
            conn = get_connection()
            cursor = conn.cursor()

            if extracted_name:
                name_parts = extracted_name.strip().split()

                if len(name_parts) >= 2:
                    first_name = name_parts[0]
                    last_name = " ".join(name_parts[1:])
                    cursor.execute("""
                        SELECT roll_num, first_name, last_name
                        FROM students
                        WHERE LOWER(first_name) = LOWER(?)
                          AND LOWER(last_name) = LOWER(?)
                    """, first_name, last_name)
                else:
                    cursor.execute("""
                        SELECT roll_num, first_name, last_name
                        FROM students
                        WHERE LOWER(first_name) = LOWER(?)
                    """, extracted_name)
            else:
                cursor.execute("""
                    SELECT roll_num, first_name, last_name
                    FROM students
                    WHERE LOWER(?) LIKE '%' + LOWER(first_name) + '%'
                       OR LOWER(?) LIKE '%' + LOWER(first_name + ' ' + last_name) + '%'
                """, text, text)

            row = cursor.fetchone()
            conn.close()

            if row:
                full_name = f"{row[1]} {row[2]}"
                dispatcher.utter_message(
                    text=f"Yes â€” I found a student called {full_name} with roll number {row[0]}."
                )
                return [SlotSet("student_name", full_name)]

            dispatcher.utter_message(text=database_no_match_fallback(text))
            return []

        except Exception:
            dispatcher.utter_message(text=student_affairs_fallback(text))
            return []


class ActionRagQuery(Action):
    def name(self) -> Text:
        return "action_rag_query"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        user_message = tracker.latest_message.get("text", "")

        try:
            abuse_events = dispatch_abuse_answer(dispatcher, user_message)
            if abuse_events is not None:
                return abuse_events
            opener_events = dispatch_question_opener_answer(dispatcher, user_message)
            if opener_events is not None:
                return opener_events
            status_events = dispatch_status_answer(dispatcher, user_message)
            if status_events is not None:
                return status_events
            if is_thanks(user_message):
                dispatcher.utter_message(text=thanks_response(user_message))
                return [SlotSet("last_query_scope", "chat")]
            if is_greeting(user_message):
                dispatcher.utter_message(text=greeting_response(user_message))
                return [SlotSet("last_query_scope", "chat"), SlotSet("last_conversation_topic", "general_chat")]
            emotional_events = dispatch_emotional_support_answer(dispatcher, user_message)
            if emotional_events is not None:
                return emotional_events
            gibberish_events = dispatch_gibberish_answer(dispatcher, user_message)
            if gibberish_events is not None:
                return gibberish_events
            continuation_events = dispatch_conversation_continuation_answer(dispatcher, user_message, tracker)
            if continuation_events is not None:
                return continuation_events
            pending_events = dispatch_pending_clarification_answer(dispatcher, user_message, tracker, domain)
            if pending_events is not None:
                return pending_events
            instructor_course_followup = dispatch_instructor_profile_course_followup_answer(dispatcher, user_message, tracker)
            if instructor_course_followup is not None:
                return instructor_course_followup
            stats_events = dispatch_fci_stats_answer(dispatcher, user_message, tracker)
            if stats_events is not None:
                return stats_events
            if extract_student_id(user_message):
                return ActionTextToSQL().run(dispatcher, tracker, domain)
            if tracker.get_slot("student_id") and wants_current_student(user_message):
                return ActionTextToSQL().run(dispatcher, tracker, domain)
            if looks_like_result_continuation(user_message):
                return ActionTextToSQL().run(dispatcher, tracker, domain)
            if is_bot_identity_question(user_message):
                dispatcher.utter_message(text=BOT_IDENTITY_RESPONSE)
                return [SlotSet("last_query_scope", "chat")]
            fci_identity_events = dispatch_fci_identity_answer(dispatcher, user_message)
            if fci_identity_events is not None:
                return fci_identity_events
            academy_events = dispatch_sadat_academy_answer(dispatcher, user_message)
            if academy_events is not None:
                return academy_events
            compound_events = dispatch_compound_topic_answer(dispatcher, user_message, tracker)
            if compound_events is not None:
                return compound_events
            schedule_clarification = dispatch_schedule_clarification(dispatcher, user_message, tracker)
            if schedule_clarification is not None:
                return schedule_clarification
            arabic_events = dispatch_arabic_policy_answer(dispatcher, user_message, tracker)
            if arabic_events is not None:
                return arabic_events
            creator_answer = creator_response_from_text(user_message)
            if creator_answer:
                dispatcher.utter_message(text=creator_answer)
                return [SlotSet("last_query_scope", "project")]
            profile_events = dispatch_instructor_profile_answer(dispatcher, user_message, tracker)
            if profile_events is not None:
                return profile_events
            catalog_events = dispatch_fci_catalog_answer(dispatcher, user_message, tracker)
            if catalog_events is not None:
                return catalog_events
            student_name_events = dispatch_student_name_lookup_answer(dispatcher, user_message)
            if student_name_events is not None:
                return student_name_events
            if looks_like_official_knowledge_request(user_message):
                answer = query_rag_service(user_message)
                dispatcher.utter_message(text=answer)
                return [
                    SlotSet("last_query_scope", "knowledge"),
                    SlotSet("last_conversation_topic", conversation_topic_for_text(user_message, answer)),
                ]
            if has_pending_sql_clarification(tracker):
                return ActionTextToSQL().run(dispatcher, tracker, domain)
            if looks_like_database_request(user_message):
                return ActionTextToSQL().run(dispatcher, tracker, domain)
            sql_probe_events = try_sql_probe_before_fallback(dispatcher, tracker, user_message)
            if sql_probe_events is not None:
                return sql_probe_events
            answer = query_rag_service(user_message)
            dispatcher.utter_message(text=answer)
            return [
                SlotSet("last_query_scope", "knowledge"),
                SlotSet("last_conversation_topic", conversation_topic_for_text(user_message, answer)),
            ]

        except Exception as e:
            dispatcher.utter_message(text=unconfirmed_fallback(user_message))

        return []


class ActionGeneralConversation(Action):
    def name(self) -> Text:
        return "action_general_conversation"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        user_message = tracker.latest_message.get("text", "")

        abuse_events = dispatch_abuse_answer(dispatcher, user_message)
        if abuse_events is not None:
            return abuse_events

        opener_events = dispatch_question_opener_answer(dispatcher, user_message)
        if opener_events is not None:
            return opener_events

        status_events = dispatch_status_answer(dispatcher, user_message)
        if status_events is not None:
            return status_events

        if is_thanks(user_message):
            dispatcher.utter_message(text=thanks_response(user_message))
            return [SlotSet("last_query_scope", "chat")]

        if is_greeting(user_message):
            dispatcher.utter_message(text=greeting_response(user_message))
            return [SlotSet("last_query_scope", "chat"), SlotSet("last_conversation_topic", "general_chat")]

        emotional_events = dispatch_emotional_support_answer(dispatcher, user_message)
        if emotional_events is not None:
            return emotional_events

        gibberish_events = dispatch_gibberish_answer(dispatcher, user_message)
        if gibberish_events is not None:
            return gibberish_events

        if is_closing(user_message):
            dispatcher.utter_message(text=CLOSING_RESPONSE)
            return [SlotSet("student_id", None), SlotSet("last_query_scope", None)]

        continuation_events = dispatch_conversation_continuation_answer(dispatcher, user_message, tracker)
        if continuation_events is not None:
            return continuation_events

        pending_events = dispatch_pending_clarification_answer(dispatcher, user_message, tracker, domain)
        if pending_events is not None:
            return pending_events

        instructor_course_followup = dispatch_instructor_profile_course_followup_answer(dispatcher, user_message, tracker)
        if instructor_course_followup is not None:
            return instructor_course_followup

        stats_events = dispatch_fci_stats_answer(dispatcher, user_message, tracker)
        if stats_events is not None:
            return stats_events

        if extract_student_id(user_message) or (tracker.get_slot("student_id") and wants_current_student(user_message)):
            return ActionTextToSQL().run(dispatcher, tracker, domain)

        if is_short_why(user_message) and tracker.get_slot("student_id") and tracker.get_slot("last_query_scope") == "student":
            return answer_student_why_followup(dispatcher, tracker.get_slot("student_id"))

        if looks_like_result_continuation(user_message):
            return ActionTextToSQL().run(dispatcher, tracker, domain)

        if is_bot_identity_question(user_message):
            dispatcher.utter_message(text=BOT_IDENTITY_RESPONSE)
            return [SlotSet("last_query_scope", "chat")]

        fci_identity_events = dispatch_fci_identity_answer(dispatcher, user_message)
        if fci_identity_events is not None:
            return fci_identity_events

        academy_events = dispatch_sadat_academy_answer(dispatcher, user_message)
        if academy_events is not None:
            return academy_events
        compound_events = dispatch_compound_topic_answer(dispatcher, user_message, tracker)
        if compound_events is not None:
            return compound_events
        schedule_clarification = dispatch_schedule_clarification(dispatcher, user_message, tracker)
        if schedule_clarification is not None:
            return schedule_clarification
        arabic_events = dispatch_arabic_policy_answer(dispatcher, user_message, tracker)
        if arabic_events is not None:
            return arabic_events

        creator_answer = creator_response_from_text(user_message)
        if creator_answer:
            dispatcher.utter_message(text=creator_answer)
            return [SlotSet("last_query_scope", "project")]

        profile_events = dispatch_instructor_profile_answer(dispatcher, user_message, tracker)
        if profile_events is not None:
            return profile_events

        catalog_events = dispatch_fci_catalog_answer(dispatcher, user_message, tracker)
        if catalog_events is not None:
            return catalog_events
        student_name_events = dispatch_student_name_lookup_answer(dispatcher, user_message)
        if student_name_events is not None:
            return student_name_events

        route_decision = hybrid_route(user_message, tracker)
        if route_decision["route"] in {"policy_rag", "educational_rag", "file_retrieval"}:
            try:
                dispatcher.utter_message(text=query_rag_service(user_message))
            except Exception:
                dispatcher.utter_message(text=GENERAL_CHAT_FALLBACK_RESPONSE)
            return [SlotSet("last_query_scope", "knowledge")]
        if route_decision["route"] in {"structured_sql", "clarification"}:
            return ActionTextToSQL().run(dispatcher, tracker, domain)

        if looks_like_official_knowledge_request(user_message):
            try:
                dispatcher.utter_message(text=query_rag_service(user_message))
            except Exception:
                dispatcher.utter_message(text=GENERAL_CHAT_FALLBACK_RESPONSE)
            return [SlotSet("last_query_scope", "knowledge")]

        if has_pending_sql_clarification(tracker):
            return ActionTextToSQL().run(dispatcher, tracker, domain)

        creator_answer = None if looks_like_database_request(user_message) else creator_response_from_text(user_message)
        if creator_answer:
            dispatcher.utter_message(text=creator_answer)
            return [SlotSet("last_query_scope", "project")]

        if looks_like_database_request(user_message):
            return ActionTextToSQL().run(dispatcher, tracker, domain)

        sql_probe_events = try_sql_probe_before_fallback(dispatcher, tracker, user_message)
        if sql_probe_events is not None:
            return sql_probe_events

        if looks_like_knowledge_question(user_message):
            try:
                dispatcher.utter_message(text=query_rag_service(user_message))
            except Exception:
                dispatcher.utter_message(text=GENERAL_CHAT_FALLBACK_RESPONSE)
            return [SlotSet("last_query_scope", "knowledge")]

        dispatcher.utter_message(text=general_conversation_answer(user_message, tracker))
        return [
            SlotSet("last_query_scope", "chat"),
            SlotSet("last_conversation_topic", conversation_topic_for_text(user_message)),
        ]


class ActionConversationRouter(Action):
    def name(self) -> Text:
        return "action_conversation_router"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        user_message = tracker.latest_message.get("text", "")

        abuse_events = dispatch_abuse_answer(dispatcher, user_message)
        if abuse_events is not None:
            return abuse_events

        opener_events = dispatch_question_opener_answer(dispatcher, user_message)
        if opener_events is not None:
            return opener_events

        status_events = dispatch_status_answer(dispatcher, user_message)
        if status_events is not None:
            return status_events

        if is_thanks(user_message):
            dispatcher.utter_message(text=thanks_response(user_message))
            return [SlotSet("last_query_scope", "chat")]

        if is_greeting(user_message):
            dispatcher.utter_message(text=greeting_response(user_message))
            return [SlotSet("last_query_scope", "chat"), SlotSet("last_conversation_topic", "general_chat")]

        emotional_events = dispatch_emotional_support_answer(dispatcher, user_message)
        if emotional_events is not None:
            return emotional_events

        gibberish_events = dispatch_gibberish_answer(dispatcher, user_message)
        if gibberish_events is not None:
            return gibberish_events

        if is_closing(user_message):
            dispatcher.utter_message(text=CLOSING_RESPONSE)
            return [SlotSet("student_id", None), SlotSet("last_query_scope", None)]

        continuation_events = dispatch_conversation_continuation_answer(dispatcher, user_message, tracker)
        if continuation_events is not None:
            return continuation_events

        pending_events = dispatch_pending_clarification_answer(dispatcher, user_message, tracker, domain)
        if pending_events is not None:
            return pending_events

        instructor_course_followup = dispatch_instructor_profile_course_followup_answer(dispatcher, user_message, tracker)
        if instructor_course_followup is not None:
            return instructor_course_followup

        stats_events = dispatch_fci_stats_answer(dispatcher, user_message, tracker)
        if stats_events is not None:
            return stats_events

        if extract_student_id(user_message) or (tracker.get_slot("student_id") and wants_current_student(user_message)):
            return ActionTextToSQL().run(dispatcher, tracker, domain)

        if is_short_why(user_message) and tracker.get_slot("student_id") and tracker.get_slot("last_query_scope") == "student":
            return answer_student_why_followup(dispatcher, tracker.get_slot("student_id"))

        if looks_like_result_continuation(user_message):
            return ActionTextToSQL().run(dispatcher, tracker, domain)

        if is_bot_identity_question(user_message):
            dispatcher.utter_message(text=BOT_IDENTITY_RESPONSE)
            return [SlotSet("last_query_scope", "chat")]

        fci_identity_events = dispatch_fci_identity_answer(dispatcher, user_message)
        if fci_identity_events is not None:
            return fci_identity_events

        academy_events = dispatch_sadat_academy_answer(dispatcher, user_message)
        if academy_events is not None:
            return academy_events
        compound_events = dispatch_compound_topic_answer(dispatcher, user_message, tracker)
        if compound_events is not None:
            return compound_events
        schedule_clarification = dispatch_schedule_clarification(dispatcher, user_message, tracker)
        if schedule_clarification is not None:
            return schedule_clarification
        arabic_events = dispatch_arabic_policy_answer(dispatcher, user_message, tracker)
        if arabic_events is not None:
            return arabic_events

        creator_answer = creator_response_from_text(user_message)
        if creator_answer:
            dispatcher.utter_message(text=creator_answer)
            return [SlotSet("last_query_scope", "project")]

        profile_events = dispatch_instructor_profile_answer(dispatcher, user_message, tracker)
        if profile_events is not None:
            return profile_events

        catalog_events = dispatch_fci_catalog_answer(dispatcher, user_message, tracker)
        if catalog_events is not None:
            return catalog_events
        student_name_events = dispatch_student_name_lookup_answer(dispatcher, user_message)
        if student_name_events is not None:
            return student_name_events

        route_decision = hybrid_route(user_message, tracker)
        if route_decision["route"] in {"policy_rag", "educational_rag", "file_retrieval"}:
            try:
                dispatcher.utter_message(text=query_rag_service(user_message))
            except Exception:
                dispatcher.utter_message(text=GENERAL_CHAT_FALLBACK_RESPONSE)
            return [SlotSet("last_query_scope", "knowledge")]
        if route_decision["route"] in {"structured_sql", "clarification"}:
            return ActionTextToSQL().run(dispatcher, tracker, domain)

        if looks_like_official_knowledge_request(user_message):
            try:
                dispatcher.utter_message(text=query_rag_service(user_message))
            except Exception:
                dispatcher.utter_message(text=GENERAL_CHAT_FALLBACK_RESPONSE)
            return [SlotSet("last_query_scope", "knowledge")]

        if has_pending_sql_clarification(tracker):
            return ActionTextToSQL().run(dispatcher, tracker, domain)

        creator_answer = None if looks_like_database_request(user_message) else creator_response_from_text(user_message)
        if creator_answer:
            dispatcher.utter_message(text=creator_answer)
            return [SlotSet("last_query_scope", "project")]

        if looks_like_database_request(user_message):
            return ActionTextToSQL().run(dispatcher, tracker, domain)

        sql_probe_events = try_sql_probe_before_fallback(dispatcher, tracker, user_message)
        if sql_probe_events is not None:
            return sql_probe_events

        if looks_like_knowledge_question(user_message):
            try:
                dispatcher.utter_message(text=query_rag_service(user_message))
            except Exception:
                dispatcher.utter_message(text=GENERAL_CHAT_FALLBACK_RESPONSE)
            return [SlotSet("last_query_scope", "knowledge")]

        dispatcher.utter_message(text=general_conversation_answer(user_message, tracker))
        return [
            SlotSet("last_query_scope", "chat"),
            SlotSet("last_conversation_topic", conversation_topic_for_text(user_message)),
        ]


class ActionProjectPurpose(Action):
    def name(self) -> Text:
        return "action_project_purpose"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        text = tracker.latest_message.get("text", "")
        lowered = normalize_question(text).strip()
        abuse_events = dispatch_abuse_answer(dispatcher, text)
        if abuse_events is not None:
            return abuse_events
        opener_events = dispatch_question_opener_answer(dispatcher, text)
        if opener_events is not None:
            return opener_events
        status_events = dispatch_status_answer(dispatcher, text)
        if status_events is not None:
            return status_events
        if is_thanks(text):
            dispatcher.utter_message(text=thanks_response(text))
            return [SlotSet("last_query_scope", "chat")]
        if is_greeting(text):
            dispatcher.utter_message(text=greeting_response(text))
            return [SlotSet("last_query_scope", "chat"), SlotSet("last_conversation_topic", "general_chat")]
        gibberish_events = dispatch_gibberish_answer(dispatcher, text)
        if gibberish_events is not None:
            return gibberish_events
        if is_bot_identity_question(lowered):
            dispatcher.utter_message(text=BOT_IDENTITY_RESPONSE)
            return [SlotSet("last_query_scope", "chat")]
        current_student_id = tracker.get_slot("student_id")
        if is_short_why(lowered) and current_student_id and tracker.get_slot("last_query_scope") == "student":
            return answer_student_why_followup(dispatcher, current_student_id)

        if lowered in {"why", "why?", "why tho", "why though"} or "why" in lowered:
            dispatcher.utter_message(text=PROJECT_WHY_RESPONSE)
        else:
            dispatcher.utter_message(text=PROJECT_PURPOSE_RESPONSE)
        return [SlotSet("last_query_scope", "project")]


class ActionBotCreator(Action):
    def name(self) -> Text:
        return "action_bot_creator"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        text = tracker.latest_message.get("text", "")
        abuse_events = dispatch_abuse_answer(dispatcher, text)
        if abuse_events is not None:
            return abuse_events
        opener_events = dispatch_question_opener_answer(dispatcher, text)
        if opener_events is not None:
            return opener_events
        status_events = dispatch_status_answer(dispatcher, text)
        if status_events is not None:
            return status_events
        if is_thanks(text):
            dispatcher.utter_message(text=thanks_response(text))
            return [SlotSet("last_query_scope", "chat")]
        if is_greeting(text):
            dispatcher.utter_message(text=greeting_response(text))
            return [SlotSet("last_query_scope", "chat"), SlotSet("last_conversation_topic", "general_chat")]
        gibberish_events = dispatch_gibberish_answer(dispatcher, text)
        if gibberish_events is not None:
            return gibberish_events
        if is_bot_identity_question(text):
            dispatcher.utter_message(text=BOT_IDENTITY_RESPONSE)
            return [SlotSet("last_query_scope", "chat")]
        answer = creator_response_from_text(text)
        if answer is None and has_hard_database_signal(text):
            return ActionTextToSQL().run(dispatcher, tracker, domain)
        dispatcher.utter_message(text=answer or CREATOR_TEAM_RESPONSE)
        return [SlotSet("last_query_scope", "project")]


class ActionGetStudentRollNumber(Action):
    def name(self) -> Text:
        return "action_get_student_roll_number"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        text = tracker.latest_message.get("text", "").lower()
        entities = tracker.latest_message.get("entities", [])

        extracted_name = None
        for entity in entities:
            if entity.get("entity") == "student_name":
                extracted_name = entity.get("value")
                break

        try:
            conn = get_connection()
            cursor = conn.cursor()

            if extracted_name:
                name_parts = extracted_name.strip().split()

                if len(name_parts) >= 2:
                    first_name = name_parts[0]
                    last_name = " ".join(name_parts[1:])
                    cursor.execute("""
                        SELECT roll_num, first_name, last_name
                        FROM students
                        WHERE LOWER(first_name) = LOWER(?)
                          AND LOWER(last_name) = LOWER(?)
                    """, first_name, last_name)
                else:
                    cursor.execute("""
                        SELECT roll_num, first_name, last_name
                        FROM students
                        WHERE LOWER(first_name) = LOWER(?)
                    """, extracted_name)
            else:
                cursor.execute("""
                    SELECT roll_num, first_name, last_name
                    FROM students
                    WHERE LOWER(?) LIKE '%' + LOWER(first_name) + '%'
                       OR LOWER(?) LIKE '%' + LOWER(first_name + ' ' + last_name) + '%'
                """, text, text)

            row = cursor.fetchone()
            conn.close()

            if row:
                dispatcher.utter_message(
                    text=f"The roll number of {row[1]} {row[2]} is {row[0]}."
                )
            else:
                dispatcher.utter_message(text=database_no_match_fallback(text))

            return []

        except Exception:
            dispatcher.utter_message(text=student_affairs_fallback(text))
            return []
class ActionGetStudentDepartment(Action):
    def name(self) -> Text:
        return "action_get_student_department"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        text = tracker.latest_message.get("text", "").lower()
        entities = tracker.latest_message.get("entities", [])

        extracted_name = None
        for entity in entities:
            if entity.get("entity") == "student_name":
                extracted_name = entity.get("value")
                break

        if not extracted_name:
            extracted_name = tracker.get_slot("student_name")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            if extracted_name:
                parts = extracted_name.strip().split()
                if len(parts) >= 2:
                    first_name = parts[0]
                    last_name = " ".join(parts[1:])
                    cursor.execute("""
                        SELECT s.roll_num, s.first_name, s.last_name, d.name
                        FROM students s
                        JOIN departments d ON s.department_id = d.id
                        WHERE LOWER(s.first_name) = LOWER(?)
                          AND LOWER(s.last_name) = LOWER(?)
                    """, first_name, last_name)
                else:
                    cursor.execute("""
                        SELECT s.roll_num, s.first_name, s.last_name, d.name
                        FROM students s
                        JOIN departments d ON s.department_id = d.id
                        WHERE LOWER(s.first_name) = LOWER(?)
                    """, extracted_name)
            else:
                conn.close()
                dispatcher.utter_message(text=student_affairs_fallback(text))
                return []

            row = cursor.fetchone()
            conn.close()

            if row:
                full_name = f"{row[1]} {row[2]}"
                dispatcher.utter_message(
                    text=f"{full_name} belongs to the {row[3]} department."
                )
                return [SlotSet("student_name", full_name)]

            dispatcher.utter_message(
                text=database_no_match_fallback(text)
            )
            return []

        except Exception:
            dispatcher.utter_message(text=student_affairs_fallback(text))
            return []
class ActionCheckIfGPAExists(Action):
    def name(self) -> Text:
        return "action_check_if_gpa_exists"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        text = tracker.latest_message.get("text", "").lower()
        current_student = tracker.get_slot("student_name")

        if "gpa" in text or "cgpa" in text:
            if current_student:
                dispatcher.utter_message(text=gpa_not_found_fallback(current_student, text))
            else:
                dispatcher.utter_message(text=gpa_not_found_fallback("that student", text))
        elif "credit" in text or "credit hours" in text:
            dispatcher.utter_message(text=student_affairs_fallback(text))
        else:
            dispatcher.utter_message(text=student_affairs_fallback(text))

        return []
class ActionListSubjects(Action):
    def name(self) -> Text:
        return "action_list_subjects"

    def run(self, dispatcher, tracker, domain):
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT name
                FROM subjects
                ORDER BY name
            """)
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                dispatcher.utter_message(text=database_no_match_fallback(text))
                return []

            subjects = [row[0] for row in rows]
            dispatcher.utter_message(
                text="Here are the available subjects: " + ", ".join(subjects)
            )
            return []

        except Exception:
            dispatcher.utter_message(text=student_affairs_fallback(""))
            return []
class ActionGetSubjectFaculty(Action):
    def name(self) -> Text:
        return "action_get_subject_faculty"

    def run(self, dispatcher, tracker, domain):
        text = tracker.latest_message.get("text", "").lower()

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT sub.name, f.first_name, f.last_name
                FROM subjects sub
                JOIN faculty f ON sub.faculty_id = f.id
                WHERE LOWER(?) LIKE '%' + LOWER(sub.name) + '%'
            """, text)

            row = cursor.fetchone()
            conn.close()

            if row:
                dispatcher.utter_message(
                    text=f"{row[0]} is taught by {row[1]} {row[2]}."
                )
            else:
                dispatcher.utter_message(text=database_no_match_fallback(text))

            return []

        except Exception:
            dispatcher.utter_message(text=student_affairs_fallback(text))
            return []


class ActionTextToSQL(Action):
    def name(self) -> Text:
        return "action_text_to_sql"

    def run(self, dispatcher, tracker, domain):
        raw_user_question = (tracker.latest_message.get("text") or "").strip()
        user_question = strip_filler_prefix(raw_user_question) or raw_user_question
        if not user_question:
            dispatcher.utter_message(text="Please ask a university data question.")
            return []

        abuse_events = dispatch_abuse_answer(dispatcher, user_question)
        if abuse_events is not None:
            return abuse_events

        opener_events = dispatch_question_opener_answer(dispatcher, user_question)
        if opener_events is not None:
            return opener_events

        status_events = dispatch_status_answer(dispatcher, user_question)
        if status_events is not None:
            return status_events

        if is_thanks(user_question):
            dispatcher.utter_message(text=thanks_response(user_question))
            return [SlotSet("last_query_scope", "chat")]

        if is_greeting(user_question):
            dispatcher.utter_message(text=greeting_response(user_question))
            return [SlotSet("last_query_scope", "chat"), SlotSet("last_conversation_topic", "general_chat")]

        emotional_events = dispatch_emotional_support_answer(dispatcher, user_question)
        if emotional_events is not None:
            return emotional_events

        gibberish_events = dispatch_gibberish_answer(dispatcher, user_question)
        if gibberish_events is not None:
            return gibberish_events

        if is_closing(user_question):
            dispatcher.utter_message(text=CLOSING_RESPONSE)
            return [SlotSet("student_id", None), SlotSet("last_query_scope", None)]

        continuation_events = dispatch_conversation_continuation_answer(dispatcher, user_question, tracker)
        if continuation_events is not None:
            return continuation_events

        pending_events = dispatch_pending_clarification_answer(dispatcher, user_question, tracker, domain)
        if pending_events is not None:
            return pending_events

        instructor_course_followup = dispatch_instructor_profile_course_followup_answer(dispatcher, user_question, tracker)
        if instructor_course_followup is not None:
            return instructor_course_followup

        stats_events = dispatch_fci_stats_answer(dispatcher, user_question, tracker)
        if stats_events is not None:
            return stats_events

        if is_bot_identity_question(user_question):
            dispatcher.utter_message(text=BOT_IDENTITY_RESPONSE)
            return [SlotSet("last_query_scope", "chat")]

        fci_identity_events = dispatch_fci_identity_answer(dispatcher, user_question)
        if fci_identity_events is not None:
            return fci_identity_events

        academy_events = dispatch_sadat_academy_answer(dispatcher, user_question)
        if academy_events is not None:
            return academy_events
        compound_events = dispatch_compound_topic_answer(dispatcher, user_question, tracker)
        if compound_events is not None:
            return compound_events
        schedule_clarification = dispatch_schedule_clarification(dispatcher, user_question, tracker)
        if schedule_clarification is not None:
            return schedule_clarification
        arabic_events = dispatch_arabic_policy_answer(dispatcher, user_question, tracker)
        if arabic_events is not None:
            return arabic_events

        creator_answer = creator_response_from_text(user_question)
        if creator_answer:
            dispatcher.utter_message(text=creator_answer)
            return [SlotSet("last_query_scope", "project")]

        if (
            is_short_why(user_question)
            and tracker.get_slot("student_id")
            and tracker.get_slot("last_query_scope") == "student"
        ):
            return answer_student_why_followup(dispatcher, tracker.get_slot("student_id"))

        profile_events = dispatch_instructor_profile_answer(dispatcher, user_question, tracker)
        if profile_events is not None:
            return profile_events

        catalog_events = dispatch_fci_catalog_answer(dispatcher, user_question, tracker)
        if catalog_events is not None:
            return catalog_events

        student_name_events = dispatch_student_name_lookup_answer(dispatcher, user_question)
        if student_name_events is not None:
            return student_name_events

        resolved_suffix = resolve_student_id_suffix(user_question)
        if resolved_suffix:
            if resolved_suffix.get("answer"):
                dispatcher.utter_message(text=str(resolved_suffix["answer"]))
                return [SlotSet("last_query_scope", "student")]
            if resolved_suffix.get("student_id"):
                user_question = rewrite_student_id_suffix(user_question, str(resolved_suffix["student_id"]))

        if looks_like_result_continuation(user_question):
            try:
                engine_result = query_sql_engine_service(user_question, tracker)
                if engine_result and engine_result.get("handled"):
                    utter_sql_engine_result(dispatcher, engine_result, user_question, tracker)
                    return sql_engine_events(engine_result)
            except Exception:
                pass
            replay_question = continuation_replay_question(tracker)
            if replay_question:
                try:
                    engine_result = query_sql_engine_service(replay_question, tracker)
                    if engine_result and engine_result.get("handled"):
                        utter_sql_engine_result(dispatcher, engine_result, user_question, tracker)
                        return sql_engine_events(engine_result)
                except Exception:
                    pass

        message_student_id = extract_student_id(user_question)
        current_student_id = tracker.get_slot("student_id")
        if wants_current_student(user_question) and not current_student_id and not message_student_id:
            dispatcher.utter_message(
                text=(
                    "Which student do you mean? Please send the student ID or ask "
                    "\"show me student [name]\" first."
                )
            )
            return [SlotSet("last_query_scope", "student")]

        context_student_followup = bool(current_student_id and wants_current_student(user_question))
        explicit_student_id_lookup = bool(message_student_id)
        route_decision = hybrid_route(user_question, tracker)
        if (
            not context_student_followup
            and not explicit_student_id_lookup
            and route_decision["route"] in {"policy_rag", "educational_rag", "file_retrieval"}
        ):
            try:
                dispatcher.utter_message(text=query_rag_service(user_question))
            except Exception as e:
                dispatcher.utter_message(text=unconfirmed_fallback(user_question))
            return [SlotSet("last_query_scope", "knowledge")]

        creator_answer = None if looks_like_database_request(user_question) else creator_response_from_text(user_question)
        if creator_answer:
            dispatcher.utter_message(text=creator_answer)
            return [SlotSet("last_query_scope", "project")]

        if looks_like_general_conversation_request(user_question):
            dispatcher.utter_message(text=general_conversation_answer(user_question, tracker))
            return [SlotSet("last_query_scope", "chat")]

        last_query_scope = tracker.get_slot("last_query_scope")
        effective_question = expand_followup_question(user_question, last_query_scope)
        context_student_id = message_student_id or (
            current_student_id if should_use_context_student(user_question) else None
        )
        known_sql_query = build_fci_known_sql(effective_question, context_student_id)

        if (
            not context_student_followup
            and not explicit_student_id_lookup
            and looks_like_knowledge_question(user_question)
            and not looks_like_fci_database_request(user_question)
            and not has_hard_database_signal(user_question)
            and not known_sql_query
        ):
            try:
                dispatcher.utter_message(text=query_rag_service(user_question))
            except Exception as e:
                dispatcher.utter_message(text=unconfirmed_fallback(user_question))
            return [SlotSet("student_id", message_student_id)] if message_student_id else []

        if not known_sql_query:
            try:
                engine_result = query_sql_engine_service(user_question, tracker)
                if engine_result and (engine_result.get("handled") or engine_result.get("needs_clarification")):
                    utter_sql_engine_result(dispatcher, engine_result, user_question, tracker)
                    return sql_engine_events(engine_result)
            except Exception:
                # The modular SQL engine is optional during migration. If it is not
                # running, keep the older in-action SQL path available as fallback.
                pass

        context_hint = ""
        if context_student_id:
            context_hint = (
                f"\nContext: If the user says he, she, his, her, them, that student, "
                f"this student, or a short follow-up like 'what about attendance', "
                f"they mean StudentID {context_student_id}."
            )

        schema = """
Tables and exact columns in SQL Server database FCI_UNIVERSITY:

Departments(dept_id, dept_name, dept_code)
Students(student_id, full_name, email, current_year, current_semester, group_code, dept_id, status)
Instructors(instructor_id, full_name, email, title)
Rooms(room_id, room_name, room_type, capacity, building)
Courses(course_id, course_code, course_name, credit_hours, total_marks, course_year, course_semester, category, dept_id)
Schedules(schedule_id, course_id, instructor_id, room_id, academic_year, semester, target_group, day_of_week, start_time, end_time, section_type)
Student_Courses(enrollment_id, student_id, course_id, academic_year, semester, raw_score, total_marks, percentage, is_reset, original_year, status)
GPA_Records(gpa_id, student_id, academic_year, semester, is_baseline, baseline_gpa, baseline_credits, semester_gpa, cumulative_gpa, credits_earned, credits_attempted)

Useful views:
v_rasa_students(student_id, full_name, email, current_year, current_semester, group_code, dept_code, dept_name, schedule_group)
v_rasa_schedule(schedule_id, academic_year, semester, course_year, course_semester, target_group, course_code, course_name, credit_hours, instructor_title, instructor_name, room_name, room_type, day_of_week, start_time, end_time, section_type, day_order)
v_rasa_student_gpa(student_id, full_name, group_code, academic_year, semesters_count, third_year_cumulative_gpa, cumulative_gpa)
v_grades(enrollment_id, student_id, student_name, student_email, group_code, course_id, course_code, course_name, credit_hours, course_total_marks, academic_year, semester, raw_score, enrollment_total_marks, percentage, grade_letter, grade_point, pass_status, is_reset, original_year, enrollment_status)

Relationships:
- Students.dept_id = Departments.dept_id
- Courses.dept_id = Departments.dept_id
- Schedules.course_id = Courses.course_id
- Schedules.instructor_id = Instructors.instructor_id
- Schedules.room_id = Rooms.room_id
- Student_Courses.student_id = Students.student_id
- Student_Courses.course_id = Courses.course_id
- GPA_Records.student_id = Students.student_id

Meaning rules:
- Prefer the v_rasa_* views for student profiles, schedules, and GPA answers.
- Student identifiers are strings like 2122136. Quote them in SQL.
- Use full_name for student names.
- Use semester_gpa or third_year_cumulative_gpa for GPA questions.
- Use Schedules/v_rasa_schedule for timetable, instructor, room, lecture, lab, and class-time questions.
- For broad list questions, return TOP 20 unless the user explicitly asks for all rows.
- Alias student_id as StudentID and full_name as FullName so answers stay friendly.
- If the answer cannot be found in the schema, return exactly: SELECT 'DATA_NOT_AVAILABLE' AS result
"""

        prompt = f"""
You are a SQL expert for the FCI_UNIVERSITY SQL Server database.

Convert the user's question into one valid SQL Server SELECT query.

Strict rules:
- Use only the exact tables and columns listed in the schema.
- Never invent columns or tables.
- Return only raw SQL. No markdown, explanation, comments, or backticks.
- Use SQL Server syntax, including TOP instead of LIMIT.
- If the answer cannot be found in the schema, return exactly:
  SELECT 'DATA_NOT_AVAILABLE' AS result
{context_hint}

{schema}

Question: {user_question}
SQL:
"""

        conn = None
        try:
            sql_query = known_sql_query
            if not sql_query:
                raw_sql = call_ollama(prompt)
                sql_query = clean_sql(raw_sql)

            print("Generated SQL:", sql_query)

            if not sql_query:
                profile_events = dispatch_instructor_profile_answer(dispatcher, user_question, tracker)
                if profile_events is not None:
                    return profile_events
                catalog_events = dispatch_fci_catalog_answer(dispatcher, user_question, tracker)
                if catalog_events is not None:
                    return catalog_events
                dispatcher.utter_message(text=unanswered_question_fallback(user_question))
                return [SlotSet("student_id", message_student_id)] if message_student_id else []

            if "DATA_NOT_AVAILABLE" in sql_query.upper():
                profile_events = dispatch_instructor_profile_answer(dispatcher, user_question, tracker)
                if profile_events is not None:
                    return profile_events
                catalog_events = dispatch_fci_catalog_answer(dispatcher, user_question, tracker)
                if catalog_events is not None:
                    return catalog_events
                dispatcher.utter_message(text=unanswered_question_fallback(user_question))
                return [SlotSet("student_id", message_student_id)] if message_student_id else []

            if not is_read_only_select(sql_query):
                dispatcher.utter_message(text=unanswered_question_fallback(user_question))
                return []

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(adapt_sql_for_configured_database(sql_query))
            rows = cursor.fetchall()
            columns = cursor_column_names(cursor)

            if not rows:
                profile_events = dispatch_instructor_profile_answer(dispatcher, user_question, tracker)
                if profile_events is not None:
                    return profile_events
                catalog_events = dispatch_fci_catalog_answer(dispatcher, user_question, tracker)
                if catalog_events is not None:
                    return catalog_events
                if message_student_id:
                    dispatcher.utter_message(text=student_not_found_fallback(message_student_id, user_question))
                else:
                    dispatcher.utter_message(text=unanswered_question_fallback(user_question))
                return [SlotSet("student_id", message_student_id)] if message_student_id else []

            if len(rows) == 1 and str(rows[0][0]) == "DATA_NOT_AVAILABLE":
                dispatcher.utter_message(text=unanswered_question_fallback(user_question))
                return [SlotSet("student_id", message_student_id)] if message_student_id else []

            context_from_rows = single_student_id_from_rows(columns, rows)
            next_student_id = (
                context_from_rows
                if context_from_rows and (not message_student_id or len(message_student_id) < 7)
                else message_student_id or context_from_rows
            )
            answer = None
            if is_analysis_question(user_question) and next_student_id and explain_student_with_gnn:
                row_context = dict(zip(columns, list(rows[0]))) if len(rows) == 1 else {}
                answer = explain_student_with_gnn(next_student_id, row_context)
            if not answer:
                row_limit = student_initial_page_size(effective_question) if "StudentID" in columns and "FullName" in columns else 10
                answer = answer_from_rows(columns, rows, effective_question, row_limit=row_limit)

            dispatcher.utter_message(text=answer)
            events = [SlotSet("last_query_scope", infer_query_scope(columns, next_student_id))]
            events.extend(legacy_student_cache_events(columns, rows, effective_question))
            if next_student_id:
                events.append(SlotSet("student_id", next_student_id))
            return events

        except Exception as e:
            dispatcher.utter_message(text=unanswered_question_fallback(user_question))
            return [SlotSet("student_id", message_student_id)] if message_student_id else []
        finally:
            if conn:
                conn.close()

