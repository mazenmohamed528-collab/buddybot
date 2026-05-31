import re
import unicodedata
from typing import Optional, Sequence, Tuple


def _clean(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def _normalize(text: str) -> str:
    cleaned = unicodedata.normalize("NFKC", text or "")
    cleaned = re.sub(r"[\u064b-\u065f\u0670]", "", cleaned)
    cleaned = cleaned.replace("\u0640", "")
    for old, new in {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "ة": "ه",
        "’": "'",
        "“": '"',
        "”": '"',
    }.items():
        cleaned = cleaned.replace(old, new)
    cleaned = cleaned.lower().strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" /?!.؟")


def _trigger_matches(text: str, trigger: str) -> bool:
    trigger_norm = _normalize(trigger)
    if not trigger_norm:
        return False
    if re.fullmatch(r"[a-z0-9]{1,4}", trigger_norm):
        return bool(re.search(rf"\b{re.escape(trigger_norm)}\b", text))
    if re.fullmatch(r"[a-z0-9]+", trigger_norm):
        return bool(re.search(rf"\b{re.escape(trigger_norm)}\b", text))
    if trigger_norm in text:
        return True
    trigger_tokens = re.findall(r"[a-z0-9]+|[\u0621-\u063a\u0641-\u064a]+", trigger_norm)
    text_tokens = set(re.findall(r"[a-z0-9]+|[\u0621-\u063a\u0641-\u064a]+", text))
    if len(trigger_tokens) >= 2:
        overlap = sum(1 for token in trigger_tokens if token in text_tokens)
        return overlap / max(len(trigger_tokens), 1) >= 0.70
    return False


EXTENDED_TOPICS: Sequence[Tuple[Sequence[str], str]] = [
    (
        [
            "how to study",
            "study tips",
            "study techniques",
            "how to memorize",
            "كيف أذاكر",
            "نصايح مذاكرة",
            "طرق المذاكرة",
            "مش قادر أذاكر",
            "how to focus",
            "concentration tips",
        ],
        _clean(
            """
            Study tips that actually work for CS/IT students:

            📅 Planning:
            - Use a weekly schedule — block specific hours for each subject.
            - Study the hardest subject when your energy is highest.
            - Don't study more than 90 minutes without a 15-minute break
              (Pomodoro technique: 25 min study / 5 min break).

            📖 How to study each type of material:
            - Math / Algorithms → solve problems, don't just read theory.
              Practice at least 10 problems per concept.
            - Programming → write actual code. Reading code is not enough.
              Break down each concept and implement it yourself.
            - Theory courses → summarise in your own words, use mind maps.
            - Memorisation heavy → spaced repetition (Anki app is great).

            🧠 Before exams:
            - Review past exam papers — patterns repeat.
            - Teach the concept to someone else — best test of understanding.
            - Sleep 7–8 hours the night before. Sleep consolidates memory.
            - Don't pull all-nighters before finals — they hurt more than help.

            💡 Tools:
            - Notion or Obsidian — organised notes.
            - Anki — flashcard-based spaced repetition.
            - YouTube (CS50, 3Blue1Brown, StatQuest) — visual explanations.
            - ChatGPT — explain concepts, generate practice problems.
            """
        ),
    ),
    (
        [
            "time management",
            "إدارة الوقت",
            "مش قادر أنظم وقتي",
            "how to manage my time",
            "procrastination",
            "تسويف",
            "كيف أنظم يومي",
            "daily routine",
        ],
        _clean(
            """
            Time management for university students:

            ⏰ Core principle: plan the week, not just the day.
            - Every Sunday (start of the week): list all deadlines and tasks.
            - Assign each task to a specific day and time slot — not 'later'.
            - Use Google Calendar or Notion to block study, rest, and social time.

            🎯 Beat procrastination:
            - The 2-minute rule: if it takes less than 2 minutes, do it now.
            - Start with the smallest piece of a big task — momentum builds.
            - Remove your phone from the room during study blocks.
            - Apps: Forest (stay focused), Cold Turkey (block distractions).

            ⚖️ Balance:
            - Schedule rest — guilt-free. Burnout kills productivity.
            - Set a 'shutdown' time each day — after that, no studying.
            - Exercise, even 20 minutes, significantly improves focus.

            📌 FCI-specific tip:
            With 15–18 credit hours per semester, you have roughly
            5–6 subjects running simultaneously. Treat each like a job —
            1–2 focused hours per subject per week minimum, more before exams.
            """
        ),
    ),
    (
        [
            "exam stress",
            "anxiety",
            "قلق",
            "خايف من الامتحان",
            "nervous about exams",
            "stressed",
            "متوتر",
            "ضغط",
            "how to calm down",
            "exam fear",
            "panic",
        ],
        _clean(
            """
            Feeling stressed before exams is completely normal.
            Here's what actually helps:

            🧘 Before the exam:
            - Prepare early — last-minute cramming increases anxiety.
            - The night before: light review, then stop. Sleep is more
              valuable than another 2 hours of stressed studying.
            - Eat a proper meal before the exam. Don't sit on an empty stomach.
            - Arrive early so you're not rushed walking in.

            😤 In the exam room:
            - Read all questions first — 2 minutes well spent.
            - Start with questions you know — build confidence, then tackle hard ones.
            - If you blank on something, skip and come back. Don't freeze.
            - Breathe slowly — 4 counts in, 4 counts hold, 4 counts out.

            💬 If anxiety is persistent:
            - Talk to a friend, family member, or trusted professor.
            - Some anxiety is useful — it means you care. Channel it into preparation.
            - If it's severely affecting your life, consider speaking to a counsellor.
              The Student Affairs office may be able to guide you to support services.

            📍 Student Affairs — FCI, Sadat Academy, Maadi Campus.
            """
        ),
    ),
    (
        [
            "cv",
            "resume",
            "how to write a cv",
            "سيرة ذاتية",
            "كيف أكتب cv",
            "cv tips",
            "what to put in cv",
            "cv for internship",
            "cv for job",
        ],
        _clean(
            """
            Writing a strong CV as an FCI student:

            📄 Structure (1 page for students):
            1. Name + contact (email, LinkedIn, GitHub) — at the top.
            2. Education — Sadat Academy, FCI, your major, expected graduation year, GPA if ≥ 3.0.
            3. Skills — programming languages, tools, frameworks relevant to your major.
            4. Projects — 2–4 projects with: what it does, tech stack, your role.
               Link to GitHub repo if possible.
            5. Experience — internships, part-time work, freelance.
            6. Certifications — Coursera, Google, Microsoft, AWS, etc.
            7. Activities — student union, hackathons, competitions (optional but good).

            ✅ Tips:
            - Tailor your CV to each job — highlight the skills they asked for.
            - Use action verbs: 'built', 'designed', 'automated', 'deployed'.
            - No photo required for international applications.
            - Use clean formatting — avoid tables and heavy design in Word/PDF.
            - Tools: Canva (visual), Overleaf (LaTeX, very professional),
              or simple Google Docs template.

            🔴 Common mistakes to avoid:
            - Listing 'Microsoft Office' as a skill for a tech role.
            - Spelling or grammar errors — always proofread.
            - Generic objectives like 'I want to grow in a dynamic environment'.
            - Lying about skills — you'll be tested.

            📌 GitHub profile is as important as your CV for tech roles.
               Make sure your repos have README files and clean code.
            """
        ),
    ),
    (
        [
            "linkedin",
            "linkedin profile",
            "how to use linkedin",
            "linkedin tips",
            "كيف أعمل linkedin",
            "linkedin for students",
        ],
        _clean(
            """
            LinkedIn for FCI students — getting started:

            🖼️ Profile basics:
            - Professional photo — clear face, neutral background.
            - Headline: don't just put 'Student'. Use:
              'Computer Science Student at FCI | Python | Machine Learning'
            - About section: 3–5 lines about your interests, skills, and goals.

            🎓 Education:
            - Add Sadat Academy, FCI, your major, and graduation year.
            - Add relevant coursework if you have no work experience yet.

            💼 Experience & Projects:
            - Add internships, part-time work, freelance projects.
            - Add your graduation project and any academic projects.
            - Each entry: what you did + what tech you used + what the outcome was.

            🤝 Connections:
            - Connect with classmates, professors, and alumni.
            - Message professionally — don't just send blank requests.
            - Follow companies you want to work at.

            📢 Activity:
            - Share things you learned, projects you completed, certifications.
            - Engage with posts in your field — even commenting builds visibility.
            - Recruiters find you through activity, not just your profile.

            🔑 Keywords:
            - Add all your technical skills in the Skills section.
            - Use the same words companies use in job postings for your target role.
            """
        ),
    ),
    (
        [
            "how to find a job",
            "job search",
            "how to get hired",
            "where to apply",
            "job tips",
            "career advice",
            "فين أدور على شغل",
            "كيف أحصل على وظيفة",
            "job hunting",
        ],
        _clean(
            """
            Job search tips for FCI graduates and students:

            🔍 Where to look:
            - LinkedIn Jobs — set up job alerts for your target role.
            - WUZZUF — largest Egyptian job board for tech roles.
            - Forasna — another Egyptian platform, more entry-level roles.
            - Indeed Egypt — international companies with Egyptian offices.
            - Company career pages — apply directly (less competition).
            - GitHub Jobs / Remote OK — for remote or international roles.

            📬 How to apply effectively:
            - Apply to 10–15 positions per week, not 1–2.
            - Customise your cover letter for each company — 3 short paragraphs:
              why you're interested, what you bring, what you want to learn.
            - Follow up once after 1 week if no response.

            🤝 Networking:
            - 70% of jobs are filled through connections, not job boards.
            - Tell everyone you know you're looking — professors, alumni, friends.
            - LinkedIn connections at companies you want → ask for a coffee chat.

            📅 Timeline:
            - Start applying 3–6 months before graduation.
            - For internships: apply 1–2 months before the semester/summer starts.

            🇪🇬 High-demand roles in Egypt's tech market:
            - Software Developer / Full-Stack — highest volume.
            - Data Analyst / Data Scientist — fast growing.
            - Cyber Security Analyst — shortage of talent.
            - DevOps / Cloud Engineer — well paid.
            - Mobile Developer (Flutter/React Native) — strong demand.
            """
        ),
    ),
    (
        [
            "freelancing",
            "freelance",
            "فريلانس",
            "شغل فري لانس",
            "upwork",
            "fiverr",
            "كيف أبدأ فريلانس",
            "online work",
            "remote work",
            "شغل من البيت",
        ],
        _clean(
            """
            Freelancing as an FCI student:

            🚀 Getting started:
            - Build 2–3 solid portfolio projects before applying for work.
            - Start on Upwork, Fiverr, or Mostaql (Arabic platform).
            - Offer competitive rates at first — get reviews, then raise prices.

            💡 In-demand skills for Egyptian freelancers:
            - Web development (React, Next.js, WordPress).
            - Mobile apps (Flutter, React Native).
            - Data analysis and dashboards (Power BI, Python).
            - Graphic design + web (if you have design sense).
            - Content writing and translation (especially Arabic↔English).

            📋 Platforms:
            - Upwork — best for long-term clients, higher rates.
            - Fiverr — good for packaged services, quick gigs.
            - Mostaql — Arabic platform, Egyptian and Gulf clients.
            - LinkedIn — direct B2B clients, highest rates.
            - Toptal — elite platform, very competitive, for experienced devs.

            ⚠️ Common mistakes:
            - Taking on more than you can deliver while studying.
            - Not having a contract or written agreement.
            - Underpricing so much you attract difficult clients.
            - Not saving a portion of each payment for taxes/savings.

            💰 Realistic expectations:
            - First 3 months are hardest — focus on getting rated clients.
            - Income is irregular — don't rely on it as your only income source.
            - Treat it professionally — meet deadlines, communicate proactively.
            """
        ),
    ),
    (
        [
            "how to learn programming",
            "where to start coding",
            "كيف أتعلم برمجة",
            "ابدأ منين في البرمجة",
            "programming for beginners",
            "which language to learn first",
            "أي لغة أبدأ بيها",
        ],
        _clean(
            """
            How to start learning programming as an FCI student:

            🐍 Start with Python — it's readable, powerful, and used in
               AI, data science, web, and automation. Most FCI courses use it.

            📚 Free resources to start:
            - CS50 (Harvard, free on edX) — best intro to CS ever made.
            - Python.org official tutorial — solid foundation.
            - freeCodeCamp YouTube — full Python course, project-based.
            - Automate the Boring Stuff with Python — free online book.

            🗺️ Learning path after basics:
            1. Variables, loops, conditions, functions (Week 1–2)
            2. Lists, dicts, file I/O, error handling (Week 3–4)
            3. Object-oriented programming (Week 5–6)
            4. Pick a direction: web / data / AI / security
            5. Build a project — even a simple one. Projects teach more than tutorials.

            ⚠️ Avoid tutorial hell:
            - Don't watch tutorial after tutorial without building anything.
            - After each tutorial section, close it and rebuild from memory.
            - Projects you struggle through teach 10× more than watched solutions.

            🔁 Practice:
            - LeetCode — algorithm and interview prep.
            - HackerRank — structured challenges by topic.
            - Codewars — fun kata-style challenges.
            - Kaggle — data science competitions and datasets.
            """
        ),
    ),
    (
        [
            "certifications",
            "certificates",
            "شهادات",
            "which certification",
            "google certificate",
            "aws certificate",
            "coursera",
            "udemy",
            "online courses",
            "شهادة أونلاين",
            "أي كورس أعمل",
        ],
        _clean(
            """
            Certifications worth your time as an FCI student:

            🆓 Free / low cost (high value):
            - Google IT Support Certificate (Coursera, financial aid available)
            - Google Data Analytics Certificate (Coursera)
            - IBM Data Science Certificate (Coursera)
            - Meta Front-End Developer Certificate (Coursera)
            - Microsoft Azure Fundamentals AZ-900 (free learning path)
            - AWS Cloud Practitioner (free prep materials on AWS)

            🔐 Cyber Security:
            - CompTIA Security+ — most recognised entry-level security cert.
            - CEH (Certified Ethical Hacker) — good for CSCS students.
            - Google Cybersecurity Certificate (Coursera) — good starter.
            - TryHackMe / Hack The Box completion paths — practical skill proof.

            📊 Data Science / AI:
            - IBM Data Science Professional (Coursera).
            - TensorFlow Developer Certificate (Google).
            - Kaggle micro-courses — free, quick, respected in DS community.
            - DeepLearning.AI specialisations (Andrew Ng on Coursera).

            ☁️ Cloud:
            - AWS Cloud Practitioner → Solutions Architect Associate.
            - Microsoft AZ-900 → AZ-104.
            - Google Cloud Associate Cloud Engineer.

            💡 Tips:
            - Coursera offers financial aid — apply if you can't afford it.
            - Prioritise certificates from Google, IBM, Microsoft, AWS — employers recognise them.
            - A GitHub project showing the skills > any certificate alone.
            """
        ),
    ),
    (
        [
            "overwhelmed",
            "burnt out",
            "burnout",
            "محتاج مساعدة",
            "تعبت",
            "مش قادر",
            "depressed",
            "lonely",
            "alone",
            "feeling lost",
            "don't know what to do",
            "dont know what to do",
            "إيه اللي المفروض أعمله",
            "حاسس إني مش كافي",
            "imposter syndrome",
            "mental health",
        ],
        _clean(
            """
            What you're feeling is real and more common than you think.
            University is genuinely hard — academically, socially, and emotionally.

            💙 Right now:
            - Give yourself permission to not be okay for a moment.
            - Talk to someone — a friend, a family member, a professor
              you trust. You don't have to figure this out alone.
            - Small steps: drink water, eat something, go outside briefly.
              These matter more than they sound.

            🎓 If it's academic:
            - Go to your academic advisor — they've seen this before.
            - Failing one course or one semester is not the end.
              Many successful people had hard semesters.
            - If your GPA is at risk, check the academic warning options —
              there are structured paths to recover.

            🧠 Imposter syndrome:
            - Almost every student feels like they don't belong or aren't smart enough.
            - It's not evidence of inability — it's evidence you care.
            - Look at how far you've come, not just how far you have to go.

            🆘 If you need to speak to someone professionally:
            - Student Affairs at FCI can guide you to support services.
            - Don't wait until it's a crisis to ask for help.

            📍 Student Affairs — FCI, Sadat Academy, Maadi Campus.
            You're not alone in this.
            """
        ),
    ),
    (
        [
            "how to talk to professor",
            "email professor",
            "كيف أكلم الدكتور",
            "أكتب إيميل للدكتور",
            "office hours",
            "professor etiquette",
            "how to ask for help from professor",
        ],
        _clean(
            """
            How to communicate with professors professionally:

            📧 Email format:
            Subject: [Course Code] — [Your Name] — [Topic]
            Example: 'ISDS352 — Mazen Badawi — Question about Assignment 2'

            Body:
            - Start with: 'Dear Dr [Last Name],'
            - One paragraph: who you are and what you need.
            - Be specific — don't say 'I don't understand the material'.
              Say 'I'm confused about the difference between ARIMA and SARIMA'.
            - End with: 'Thank you for your time.'
            - Sign with your full name and student ID.

            🏫 Office hours:
            - Come prepared with specific questions — not 'can you explain everything'.
            - Arrive on time or slightly early.
            - Show you've tried — 'I attempted X and got Y result, I think
              the issue is Z' shows effort and gets better help.

            ⚠️ Things to avoid:
            - Emailing 'will this be on the exam?' — this annoys professors.
            - Asking for extensions without a genuine reason.
            - Going over their head (to the Dean) without talking to them first.

            ✅ Professors respect students who:
            - Come to class consistently.
            - Ask thoughtful questions.
            - Admit when they're confused rather than pretending.
            - Show improvement over the semester.
            """
        ),
    ),
    (
        [
            "group project",
            "team project",
            "مشروع جماعي",
            "مشكلة في الجروب",
            "how to work in a team",
            "team conflict",
            "teammate not working",
            "زميل مش شاغل بال",
        ],
        _clean(
            """
            Making group projects work at university:

            🚀 At the start:
            - Meet in the first week and divide responsibilities clearly.
            - Set internal deadlines before the actual deadline — at least 3 days earlier.
            - Agree on a communication channel: WhatsApp group, Discord, or Slack.
            - Use GitHub for code projects — separate branches, pull requests.

            🛠️ Tools that help:
            - Trello or Notion — task tracking, who owns what.
            - Google Docs — shared documents and real-time collaboration.
            - Figma — shared design work.
            - GitHub / GitLab — code collaboration (mandatory for CS projects).

            ⚠️ When someone isn't contributing:
            1. Have a direct, calm conversation with them first — privately.
            2. Redistribute fairly if they have a genuine problem.
            3. If it continues: document everything (screenshots of group chat).
            4. Involve the professor early — don't wait until submission day.

            📌 Professional mindset:
            - Group work is a life skill — it mirrors actual job teams.
            - Be the person who communicates clearly and meets deadlines.
            - Give credit generously when someone does good work.
            """
        ),
    ),
    (
        [
            "how to get to sadat academy",
            "maadi campus location",
            "transport to fci",
            "مواصلات للأكاديمية",
            "كيف أوصل",
            "الأكاديمية فين بالظبط",
            "address of sadat academy",
            "metro to sadat academy",
        ],
        _clean(
            """
            Getting to Sadat Academy for Management Sciences — Maadi Campus:

            📍 Address:
            Sadat Academy for Management Sciences
            Maadi, Cairo, Egypt.
            (Located near Maadi Metro Station — Line 1, yellow line)

            🚇 Metro:
            - Take Line 1 (yellow) to Maadi Station.
            - From the station, the academy is reachable by microbus or
              a short taxi/Uber ride (5–10 minutes).

            🚌 Microbus / Bus:
            - Several lines pass through Maadi from central Cairo,
              Heliopolis, Nasr City, and Giza.
            - Ask for 'أكاديمية السادات المعادي' — most drivers know it.

            🚗 Uber / Careem / inDrive:
            - Most reliable option for first-time visitors.
            - Search: 'Sadat Academy Maadi' in the app.

            🕐 Office hours at the campus: generally 9 AM – 4 PM, Saturday–Thursday.
            """
        ),
    ),
    (
        [
            "prayer room",
            "mosque",
            "مسجد",
            "مصلى",
            "أماكن الصلاة",
            "cafeteria",
            "كافيتريا",
            "gym",
            "library",
            "مكتبة",
            "campus facilities",
            "مرافق الكلية",
            "printing",
            "طباعة",
        ],
        _clean(
            """
            Campus facilities at FCI, Sadat Academy Maadi:

            🕌 Prayer:
            - There is a prayer area (مصلى) on campus.
            - For exact location ask at reception or Student Affairs on arrival.

            ☕ Cafeteria:
            - A cafeteria is available on campus for meals and refreshments.

            📚 Library:
            - The academy has a library with academic books and references.
            - Students can borrow books with their student card.
            - Check library hours — typically 9 AM – 3 PM.

            🖨️ Printing:
            - Printing services are available near the admin building.
            - Bring your document on a USB drive or email it to the print shop.

            🏋️ Sports:
            - Some sports facilities are available — check with Student Affairs
              for current availability and booking.

            📍 For the most accurate and up-to-date information on any facility:
            Student Affairs office — FCI, Sadat Academy, Maadi Campus.
            """
        ),
    ),
    (
        [
            "chatgpt",
            "ai tools for students",
            "copilot",
            "gemini",
            "أدوات الذكاء الاصطناعي",
            "ai for studying",
            "can i use chatgpt for assignments",
            "how to use ai",
        ],
        _clean(
            """
            AI tools useful for FCI students:

            🤖 General Purpose:
            - ChatGPT (OpenAI) — explain concepts, generate practice problems,
              debug code, review essays. Use it as a tutor, not a ghostwriter.
            - Google Gemini — similar to ChatGPT, integrates with Google Docs.
            - Claude (Anthropic) — great for long documents and analysis.
            - Microsoft Copilot — free with .edu email on many plans.

            💻 Coding:
            - GitHub Copilot — AI code completion inside VS Code.
              Free for students with GitHub Student Developer Pack.
            - Cursor — AI-powered code editor, excellent for learning.
            - Codeium — free alternative to Copilot.

            📄 Writing & Research:
            - Grammarly — grammar and style checking (free tier).
            - Elicit.org — AI for finding and summarising research papers.
            - Perplexity.ai — AI-powered search with citations.
            - Consensus.app — finds academic consensus on research questions.

            🎨 Design:
            - Canva AI — presentations, posters, social media.
            - Midjourney / DALL-E — image generation for projects.

            ⚠️ Academic integrity note:
            - Using AI to understand concepts = great study tool.
            - Submitting AI-generated text as your own work = academic dishonesty.
            - If your professor hasn't stated the policy, ask them directly.
            - Use AI to learn faster, not to skip learning.
            """
        ),
    ),
    (
        [
            "github student pack",
            "github free",
            "student developer pack",
            "free tools for students",
            "github education",
            "how to get github student pack",
        ],
        _clean(
            """
            GitHub Student Developer Pack — completely free for students:

            🎁 What you get (highlights):
            - GitHub Copilot — AI code completion (worth $100/year alone).
            - GitHub Pro — private repos, advanced features.
            - Namecheap — free .me domain for 1 year.
            - JetBrains IDEs — PyCharm, IntelliJ, WebStorm (all free).
            - Microsoft Azure — $100 credit.
            - DigitalOcean — $200 cloud credit.
            - Canva Pro — free for 1 year.
            - DataCamp — 3 months free.
            - Many more (100+ offers).

            📋 How to get it:
            1. Go to: education.github.com/pack
            2. Sign in with your GitHub account.
            3. Click 'Get student benefits'.
            4. Verify with your .edu email or upload your student ID.
            5. Approval usually takes 1–7 days.

            📧 Use your Sadat Academy email:
              [YourName]@sadatacademy.edu.eg
            This increases approval speed significantly.
            """
        ),
    ),
    (
        [
            "open source",
            "contribute to open source",
            "github contribution",
            "how to contribute",
            "first contribution",
            "مساهمة في مشاريع مفتوحة المصدر",
        ],
        _clean(
            """
            Contributing to open source as a student:

            🌱 Why it matters:
            - Real experience on real codebases — more impressive than tutorials.
            - Visible on your GitHub profile — employers look at this.
            - You learn how professional teams write and review code.

            🚀 How to start:
            1. Find beginner-friendly issues — search GitHub for:
               'good first issue' + your language/framework.
            2. Read the project's CONTRIBUTING.md carefully.
            3. Fork the repo, create a branch, make your change.
            4. Write a clear pull request description.
            5. Be responsive to review comments.

            🔍 Good places to find projects:
            - goodfirstissue.dev — curated list of beginner issues.
            - up-for-grabs.net — filter by language and difficulty.
            - First Timers Only (firsttimersonly.com).
            - Any tool you actually use — you understand the problem domain.

            📌 Start small:
            - Fix a typo in documentation — it counts and gets you comfortable.
            - Add a test case.
            - Fix a simple bug.
            - Don't start by building a new feature.
            """
        ),
    ),
    (
        [
            "scholarship",
            "منحة",
            "منح دراسية",
            "financial aid",
            "مساعدة مالية",
            "كيف أحصل على منحة",
            "تخفيض رسوم",
            "fee waiver",
            "study abroad scholarship",
        ],
        _clean(
            """
            Scholarships and financial support for Egyptian students:

            🏛️ Within Sadat Academy:
            - Some academic excellence awards exist for top-performing students.
            - Check with Student Affairs about current fee reduction programmes.
            - Ask about instalment payment plans if fees are a burden.

            🌍 External scholarships:
            - DAAD (Germany) — fully funded Masters and PhD.
            - Chevening (UK) — fully funded Masters for Egyptian students.
            - Fulbright (USA) — for graduate study in the US.
            - MEXT (Japan) — Japanese government scholarship.
            - Erasmus+ — European exchange programmes.
            - Egyptian Ministry of Higher Education scholarships — check their website.

            💻 Tech-specific:
            - Google Generation Scholarship — for CS students in MENA.
            - Udacity scholarships — periodic tech nanodegree scholarships.
            - Coursera financial aid — apply per course, usually approved.

            📋 How to apply:
            - Start preparing 12–18 months before the deadline.
            - Requirements usually: strong GPA, English proficiency, recommendation letters.
            - Most scholarships are for graduate study — focus on your undergrad GPA now.

            📍 For academy-specific financial support:
            Student Affairs — FCI, Sadat Academy, Maadi Campus.
            """
        ),
    ),
    (
        [
            "study abroad",
            "exchange programme",
            "exchange program",
            "erasmus",
            "دراسة بالخارج",
            "برنامج تبادل",
            "how to study abroad",
            "international exchange",
            "semester abroad",
        ],
        _clean(
            """
            Studying abroad from Sadat Academy:

            🌍 Options available:
            - Erasmus+ — European exchange programmes.
              Some Egyptian universities have bilateral agreements.
              Check with the International Relations office at the academy.
            - Bilateral agreements — the academy may have exchange agreements
              with universities in Europe or the Arab region.
            - Independent applications — apply directly to foreign universities
              for a semester or year as a visiting student.

            📋 What you generally need:
            - Strong GPA (usually 3.0+).
            - English or target language proficiency (IELTS/TOEFL for English).
            - Recommendation letters from professors.
            - Personal statement.
            - Financial proof (unless scholarship covered).

            🔍 Where to find programmes:
            - Ask the International Relations or Student Affairs office at the academy.
            - Erasmus+ official website: erasmus-plus.ec.europa.eu
            - DAAD database: daad.de

            📌 Timeline: start preparing 12–18 months in advance.
            📍 International Relations / Student Affairs — Sadat Academy, Maadi.
            """
        ),
    ),
    (
        [
            "what gpa do i need",
            "good gpa",
            "gpa meaning",
            "معدل كويس قد ايه",
            "ايه المعدل الكويس",
            "gpa for masters",
            "gpa for scholarship",
            "معدل للدراسات العليا",
        ],
        _clean(
            """
            What your GPA means at FCI (4.0 scale):

            3.7 – 4.0 → Excellent (A) — top 5–10% of class.
                         Scholarship eligible, strong masters applications.
            3.2 – 3.69 → Very Good (B) — strong academic standing.
                          Good for most graduate programmes and jobs.
            2.6 – 3.19 → Good (C) — acceptable, competitive for most roles.
            2.0 – 2.59 → Pass (D) — minimum to graduate. Work harder.
            Below 2.0  → Academic Warning — urgent action needed.

            🎯 Targets by goal:
            - Graduation: minimum 2.0 cumulative.
            - Honour distinction: 3.7+ with no failures.
            - Masters (local): usually 2.5+ minimum, 3.0+ competitive.
            - Masters (abroad): 3.0+ minimum, 3.5+ for top programmes.
            - Scholarship: usually 3.5+ required.
            - Employment: most tech companies don't filter by GPA —
              they care about skills and projects.
            """
        ),
    ),
    (
        [
            "email format",
            "student email",
            "فورمات الإيميل",
            "كيف يكون إيميلي",
            "what is my email",
            "sadatacademy email",
        ],
        _clean(
            """
            FCI student email format:
            [FirstName].[LastName].[YearJoined+ID]@sadatacademy.edu.eg

            Example:
            Student: Mazen Mohamed Abd Elmageed Badawi
            ID: 2122209
            Email: Mazen.Badawy.22209@sadatacademy.edu.eg

            Use your student email for:
            - GitHub Student Developer Pack verification.
            - Official Coursera/edX student discounts.
            - Microsoft Office 365 (may be available free via the academy).
            - Any academic or professional communications.
            """
        ),
    ),
    (
        [
            "courses in arabic or english",
            "الكورسات بالعربي ولا الإنجليزي",
            "language of instruction",
            "هل الدراسة بالعربي",
        ],
        _clean(
            """
            Language of instruction at FCI:
            All specialisation courses (Year 3 and 4) are taught in English.
            Some general/foundation courses in Years 1 and 2 may be delivered
            in Arabic or bilingual depending on the instructor.

            Exams and assignments are also in English for major courses.

            💡 Tip: if English is a challenge, improve it now.
               • Duolingo or BBC Learning English for daily practice.
               • Watch lectures on YouTube in English (CS50, Coursera).
               • Read tech documentation in English — it's the global standard.
            """
        ),
    ),
]


CS_EXTENDED_TOPICS: Sequence[Tuple[Sequence[str], str]] = [
    (
        [
            "انصحني",
            "نصيحة",
            "نصحني",
            "advise me",
        ],
        _clean(
            """
            بكل سرور! 😊 أنصحك بإيه بالظبط؟
            - 📚 طرق المذاكرة والتركيز
            - ⏰ تنظيم الوقت وعمل جدول
            - 💻 ابدأ منين في البرمجة
            - 🎯 اختيار التخصص المناسب
            - 💼 التخطيط للمسيرة المهنية
            - 😤 التعامل مع الضغط والإرهاق
            قولي أكتر عايز تعرف ايه وهساعدك!
            """
        ),
    ),
    (
        [
            "عاوز اذاكر",
            "عايز اذاكر",
            "مش عارف اذاكر",
            "بذاكر ازاي",
            "اذاكر ازاي",
            "ازاي اذاكر",
            "طريقة المذاكرة",
            "عاوز أفهم",
            "مش فاهم",
            "مش قادر أفهم",
            "i want to study better",
            "help me study",
            "how to study",
            "study tips",
        ],
        _clean(
            """
            نصايح مذاكرة حقيقية لطلاب CS / FCI:

            🧠 الأسلوب الأقوى — Active Recall:
            بدل ما تعيد قراءة النوتس، اقفلها وحاول تتذكر كل حاجة من دماغك.
            اللي هتتذكره هو اللي اتعلمته فعلاً.

            📅 Spaced Repetition:
            ذاكر المادة، راجعها بعد يوم، بعد أسبوع، بعد 3 أسابيع.
            الـ app المجاني Anki بيعمل ده أوتوماتيك.

            🍅 Pomodoro:
            25 دقيقة مذاكرة → استراحة 5 دقايق → بعد 4 جولات استراحة 20 دقيقة.
            بيخلي المذاكرة أقل إرهاقاً وأكثر تركيزاً.

            🧑‍🏫 Feynman Technique:
            اشرح المادة لنفسك زي ما بتشرحها لحد ما بيعرفش حاجة.
            لما تتعتع في جزء — ارجع ذاكر التعتعة دي بالظبط.

            💻 للبرمجة خصوصاً:
            ما تكتفيش بقراءة الكود — اكتبه بإيدك حتى لو من غير ما تبص.
            المشاريع الصغيرة بتعلمك أكتر من 10 تيوتوريال.

            🛠️ أدوات بتساعد:
            - Anki — كاردات مذاكرة ذكية (مجاني)
            - Notion أو Obsidian — نوتس منظمة
            - Forest app — يساعدك تبعد عن التليفون وقت المذاكرة
            - YouTube: CS50, 3Blue1Brown, Fireship — شرح بصري ممتاز
            """
        ),
    ),
    (
        [
            "ازاي انظم وقتي",
            "ازاي أنظم",
            "عاوز انظم وقتي",
            "عايز انظم وقتي",
            "عاوز انظم",
            "عايز انظم",
            "انظم وقتي ازاي",
            "وقتي بيضيع",
            "مش قادر أنظم",
            "مفيش وقت",
            "معنديش وقت",
            "معنديس وقت",
            "ما عنديش وقت",
            "ماعنديش وقت",
            "الوقت بيعدي",
            "تنظيم الوقت",
            "time management",
            "manage my time",
            "i need to manage my time",
        ],
        _clean(
            """
            تنظيم الوقت لطالب CS — نظام عملي:

            📅 خطوة 1 — تخطيط الأسبوع (مش اليوم):
            كل أحد قبل ما الأسبوع يبدأ:
            - اكتب كل المهام اللي المفروض تخلصها الأسبوع ده.
            - قدّر الوقت لكل مهمة — وزوّد التقدير بـ 50%.
            - حط كل مهمة في يوم ووقت محدد — مش 'بكره إن شاء الله'.

            ⏰ خطوة 2 — هيكل اليوم:
            - الصبح (طاقة عالية): المادة الصعبة — خوارزميات، رياضيات، كود.
            - بعد الظهر: مذاكرة متوسطة — قراءة، نوتس، لاب.
            - بالليل: خفيف — مراجعة Anki، تفرج على محاضرة، تخطيط بكرة.
            - ما تحطش حاجة مهمة بعد 11 بالليل — دماغك مش هتستحمل.

            🏁 خطوة 3 — هزيمة التسويف:
            - كسّر المهمة لأصغر خطوة ممكنة.
              مش 'أخلص الـ assignment' — 'افتح الملف واكتب سطر'.
            - ضع تايمر 5 دقايق فقط. غالباً هتكمل بعدها.
            - التليفون — حطه في أوضة تانية وقت المذاكرة.

            📚 مع 15–18 ساعة معتمدة:
            كل مادة محتاج على الأقل ساعتين في الأسبوع خارج المحاضرة.
            مواد البرمجة محتاج 4–6 ساعات أسبوعياً عشان تتحسن فعلاً.
            ابدأ المذاكرة للامتحانات 3 أسابيع قبل — مش 3 أيام.
            """
        ),
    ),
    (
        [
            "تعبت",
            "زهقت",
            "مش قادر أكمل",
            "مبقتش قادر",
            "محتاج مساعدة",
            "ضايقني",
            "مضغوط",
            "خايف أرسب",
            "هرسب",
            "رسبت",
            "stressed",
            "burnt out",
            "i give up",
            "this is too hard",
            "too hard",
            "so hard",
            "i failed",
            "i'm failing",
            "im failing",
            "afraid to fail",
            "cs is hard",
        ],
        _clean(
            """
            اللي بتحس بيه ده طبيعي تماماً وعندك حق فيه.
            CS صعبة فعلاً — مش معناها إنك مش كفيء.

            💙 دلوقتي:
            - وقف. خد 24 ساعة استراحة لو قادر.
              المذاكرة وانت محترق أقل فايدة من ما تذاكرش خالص.
            - نام نومة كويسة. نوم واحد صح بيرجع أكتر من 4 ساعات مذاكرة مرهقة.
            - اطلع بره شوية — حتى 15 دقيقة هواء طازة بتعمل فرق.
            - اتكلم مع حد — صاحب، أهل، دكتور بتثق فيه.

            📉 لو بتأخر أو في خطر رسوب:
            - روح للمرشد الأكاديمي دلوقتي — قبل ما الوضع يتأزم.
            - فيه نظام إنذار أكاديمي فيه فرص للتعافي — مش نهاية الطريق.
            - رسوب في فصل واحد مش معناه رسوب في حياتك.

            🧠 Imposter Syndrome:
            تقريباً كل طالب CS بيحس إنه مش كفايه.
            اللي بتحس بيه ده دليل إنك بتهتم — مش دليل إنك غلط.
            انظر إيه اللي قدرت تعمله من 6 شهور لحد دلوقتي.

            📍 لو الضغط بيأثر على حياتك اليومية بجدية:
            مكتب شؤون الطلاب ممكن يدلك على خدمات الدعم.
            📍 كلية الحاسبات والمعلومات، أكاديمية السادات، المعادي.
            """
        ),
    ),
    (
        [
            "what is computer science",
            "what is cs",
            "computer science overview",
            "cs explained",
            "what do cs students study",
            "ايه علوم الحاسب",
        ],
        _clean(
            """
            Computer Science (CS) is the study of computation, algorithms,
            data structures, programming languages, computer architecture,
            and the theoretical foundations of computing, alongside practical
            applications in software, AI, networks, and security.

            CS is split into several major areas:

            🧠 Theory & Mathematics:
            - Algorithms and complexity
            - Discrete mathematics
            - Computability theory
            - Information theory and cryptography

            💻 Systems:
            - Operating systems
            - Computer architecture
            - Compilers
            - Networks
            - Databases

            🤖 Intelligent Systems:
            - Artificial intelligence and machine learning
            - Natural language processing
            - Computer vision
            - Robotics

            🌐 Applied:
            - Web and mobile development
            - Cloud computing and distributed systems
            - Cybersecurity
            - Human-computer interaction

            📌 At FCI, the CS specialisation covers these areas across
            Years 3 and 4, with 24 major courses.
            """
        ),
    ),
    (
        [
            "programming languages",
            "which language to learn",
            "best programming language",
            "python vs java",
            "c++ vs python",
            "أي لغة برمجة",
            "لغات البرمجة",
            "what language should i learn",
            "difference between languages",
            "which language",
            "what language",
            "where to start coding",
            "ازاي أبدأ برمجة",
            "ازاي ابدأ برمجة",
            "ازاي أبدأ",
            "ازاي ابدأ",
            "أتعلم ايه",
            "اتعلم ايه",
            "أبدأ منين",
            "ابدأ منين",
            "i would like to learn python",
            "i want to learn python",
            "i need to learn python",
            "i want to learn",
            "i need to learn",
            "learn python",
        ],
        _clean(
            """
            Programming languages — a practical guide for FCI students:

            🐍 Python
            Best for AI, data science, scripting, web backends, and automation.
            It is the easiest language to start with and is heavily used across
            AI, ISDS, CS, and CSCS work.

            ☕ Java
            Best for enterprise software, Android development, and backend systems.
            It teaches object-oriented programming deeply.

            ⚙️ C / C++
            Best for systems programming, embedded systems, game engines,
            competitive programming, operating systems, and understanding memory.

            🌐 JavaScript / TypeScript
            Best for web development. JavaScript runs in the browser, while
            TypeScript adds type safety and is common in industry.

            🗄️ SQL
            Essential for databases, backend development, and data analysis.
            Every serious software or data role needs SQL.

            🎯 Suggested path at FCI:
            - Year 1-2: Python first, then C++ for systems understanding.
            - CS: Python + Java + C++ + JavaScript.
            - AI: Python deeply, plus some Prolog.
            - CSCS: Python + Bash + some C.
            - ISDS: Python + SQL + optional R.
            - SE: Python or Java + JavaScript + SQL.
            """
        ),
    ),
    (
        [
            "data structures",
            "algorithms",
            "dsa",
            "why dsa",
            "data structures and algorithms",
            "هياكل البيانات",
            "الخوارزميات",
            "leetcode",
            "why study algorithms",
        ],
        _clean(
            """
            Data Structures & Algorithms (DSA) — why every CS student needs them:

            📦 Data structures organise data for efficient access and modification:
            - Arrays, linked lists, stacks, queues
            - Hash tables for fast lookup
            - Trees, heaps, and tries
            - Graphs for networks, maps, and relationships

            ⚡ Algorithms solve problems efficiently:
            - Sorting: merge sort, quick sort
            - Searching: linear and binary search
            - Graphs: BFS, DFS, Dijkstra, Bellman-Ford
            - Dynamic programming
            - Greedy algorithms
            - Divide and conquer

            🎯 Why it matters:
            - Top tech interviews test DSA heavily.
            - It teaches efficiency, not just correctness.
            - It makes production code faster and cleaner.

            📚 At FCI, DSA foundations appear in AAD201 and later CS courses.

            🔗 Practice:
            - LeetCode
            - HackerRank
            - Codeforces
            - NeetCode.io
            """
        ),
    ),
    (
        [
            "operating systems",
            "os",
            "what is an os",
            "نظم التشغيل",
            "how does an os work",
            "linux",
            "unix",
        ],
        _clean(
            """
            Operating Systems — what FCI students learn in COS201:

            🖥️ An operating system manages CPU time, memory, storage,
            files, devices, and communication between software and hardware.

            📚 Key topics:
            - Processes and threads
            - CPU scheduling: Round Robin, SJF, priority scheduling
            - Memory management: virtual memory, paging, segmentation
            - Page replacement: LRU, FIFO, Optimal
            - File systems: FAT, NTFS, ext4, inodes
            - Synchronisation: race conditions, semaphores, deadlocks
            - I/O management, interrupts, and device drivers

            🐧 Linux matters because most servers, cloud systems,
            cybersecurity tools, and developer workflows rely on it.

            📌 Practice: install Ubuntu in VirtualBox and learn the Linux
            command line. OverTheWire and freeCodeCamp are great starting points.
            """
        ),
    ),
    (
        [
            "databases",
            "sql",
            "database systems",
            "nosql",
            "قواعد البيانات",
            "what is a database",
            "how databases work",
            "relational database",
            "database design",
        ],
        _clean(
            """
            Databases — covered in DBS201 at FCI:

            🗄️ Databases store, organise, and retrieve data efficiently and reliably.

            📚 Core concepts:
            - Relational model: tables, rows, columns, keys
            - SQL: SELECT, INSERT, UPDATE, DELETE, JOIN, GROUP BY
            - ER diagrams for database design
            - Normalisation: 1NF, 2NF, 3NF, BCNF
            - Transactions and ACID properties
            - Indexes, views, stored procedures, and triggers

            🆕 NoSQL:
            - MongoDB: document database
            - Redis: key-value cache
            - Cassandra: massive-scale writes
            - Neo4j: graph relationships

            🔧 Tools to know:
            - PostgreSQL or MySQL
            - MongoDB Atlas
            - DBeaver
            """
        ),
    ),
    (
        [
            "computer networks",
            "networking",
            "how internet works",
            "شبكات الحاسب",
            "tcp ip",
            "osi model",
            "what is networking",
        ],
        _clean(
            """
            Computer Networks — covered in CN201 at FCI:

            🌐 The internet in simple form:
            browser → DNS lookup → TCP connection → HTTP request
            → server response → your screen renders it.

            📚 Core concepts:
            - OSI model: Physical, Data Link, Network, Transport,
              Session, Presentation, Application
            - TCP/IP model
            - IP addressing, IPv4, IPv6, subnetting, CIDR
            - DNS
            - HTTP/HTTPS and status codes
            - TCP vs UDP
            - Routing, NAT, DHCP, VPNs, and firewalls

            🔧 Practice tools:
            - Wireshark
            - Cisco Packet Tracer
            - TryHackMe networking rooms
            """
        ),
    ),
    (
        [
            "software engineering principles",
            "clean code",
            "solid principles",
            "design patterns",
            "what is se",
            "مبادئ هندسة البرمجيات",
            "software development best practices",
        ],
        _clean(
            """
            Software Engineering principles every CS/SE student should know:

            📐 SOLID:
            - Single Responsibility
            - Open/Closed
            - Liskov Substitution
            - Interface Segregation
            - Dependency Inversion

            🧹 Clean code:
            - Use meaningful names.
            - Keep functions small.
            - Explain why in comments, not obvious what.
            - Avoid repetition.
            - Do not over-engineer features you do not need yet.

            🏗️ Design patterns:
            - Creational: Factory, Builder, Singleton
            - Structural: Adapter, Facade, Decorator
            - Behavioural: Observer, Strategy, Command

            ⚙️ Professional development:
            - Agile, Scrum, Kanban
            - Git and pull requests
            - CI/CD
            - Unit tests and linting
            - Code review
            """
        ),
    ),
    (
        [
            "what is ai",
            "ai basics",
            "how does ai work",
            "machine learning basics",
            "what is machine learning",
            "neural networks",
            "deep learning basics",
            "ما هو الذكاء الاصطناعي",
            "كيف يعمل الذكاء الاصطناعي",
        ],
        _clean(
            """
            Artificial Intelligence — from basics to deep learning:

            🧠 AI means systems that perform tasks normally requiring
            human intelligence: perception, reasoning, learning,
            decision-making, and language understanding.

            📊 Machine Learning:
            - Supervised learning: learns from labelled examples.
            - Unsupervised learning: finds patterns in unlabelled data.
            - Reinforcement learning: learns through rewards and trial/error.

            🔗 Neural Networks:
            Input layer → hidden layers → output layer.
            Training uses forward passes, loss calculation, backpropagation,
            and weight updates.

            🖼️ Deep Learning:
            - CNNs for images and video
            - RNN/LSTM for sequences
            - Transformers for language models
            - GANs for generation

            📝 NLP:
            Tokenisation, embeddings, BERT, GPT, and other transformer models.

            📌 At FCI, AI foundations start in BAI202, then continue in
            AI and CS major courses.
            """
        ),
    ),
    (
        [
            "cybersecurity basics",
            "how to start in cyber",
            "what is hacking",
            "ethical hacking",
            "penetration testing",
            "كيف أبدأ في السيبر",
            "أساسيات الأمن السيبراني",
            "what is ctf",
            "ctf competitions",
        ],
        _clean(
            """
            Cybersecurity — a roadmap for beginners:

            🛡️ Cybersecurity protects systems, networks, applications,
            and data from attacks and unauthorised access.

            Key domains:
            - Network security
            - Application security and OWASP Top 10
            - Cryptography
            - Digital forensics
            - Ethical hacking and penetration testing
            - Incident response
            - Risk management

            🧪 CTF competitions:
            Capture The Flag challenges teach practical security skills:
            web exploitation, forensics, cryptography, OSINT, reverse
            engineering, and binary exploitation.

            Learning roadmap:
            1. Linux basics
            2. Networking fundamentals
            3. Web fundamentals
            4. TryHackMe Pre-Security and Jr Penetration Tester paths
            5. HackTheBox Starting Point
            6. CompTIA Security+ or eJPT prep
            """
        ),
    ),
    (
        [
            "web development",
            "how to build a website",
            "front end",
            "back end",
            "full stack",
            "html css javascript",
            "تطوير الويب",
            "كيف أعمل موقع",
            "react",
            "node js",
            "web dev roadmap",
        ],
        _clean(
            """
            Web Development roadmap for FCI students:

            🎨 Frontend:
            - HTML for structure
            - CSS for styling, Flexbox, Grid, and responsive layouts
            - JavaScript for interactivity
            - React for component-based UIs
            - Next.js for production React apps

            ⚙️ Backend:
            - Node.js + Express, or Python + FastAPI/Django
            - PostgreSQL for SQL databases
            - MongoDB for NoSQL
            - REST APIs
            - Authentication with JWT, OAuth, or sessions

            🐋 DevOps basics:
            - Git + GitHub
            - Docker
            - Deployment on Vercel, Railway, Render, or similar services

            Shortest full-stack path:
            1. HTML + CSS
            2. JavaScript
            3. React
            4. Node.js/Express or FastAPI
            5. PostgreSQL
            6. Deploy one complete project
            """
        ),
    ),
    (
        [
            "git",
            "version control",
            "how to use git",
            "git commands",
            "كيف أستخدم git",
            "what is git",
            "git tutorial",
            "branches",
            "pull request",
        ],
        _clean(
            """
            Git — every FCI student must learn this:

            🔧 Git tracks changes in your code over time and makes teamwork possible.

            Essential commands:
              git init              — start tracking a folder
              git clone [url]       — copy a remote repo
              git add .             — stage changes
              git commit -m "msg"   — save a snapshot
              git push              — upload to GitHub
              git pull              — download latest changes
              git branch [name]     — create a branch
              git checkout [branch] — switch branches
              git merge [branch]    — merge another branch
              git log               — see history
              git diff              — see changes
              git stash             — temporarily save work

            Professional workflow:
            1. Create a feature branch.
            2. Make changes and commit.
            3. Push the branch.
            4. Open a Pull Request.
            5. Review, fix comments, then merge.

            📌 Also apply for the GitHub Student Developer Pack.
            """
        ),
    ),
    (
        [
            "study techniques",
            "how to study cs",
            "study tips",
            "study tip",
            "study advice",
            "best way to study",
            "كيف أذاكر cs",
            "طرق مذاكرة",
            "study methods",
            "active recall",
            "spaced repetition",
            "feynman technique",
        ],
        _clean(
            """
            Study techniques that actually work for CS students:

            🧠 Active Recall:
            Close your notes and try to recall the idea from memory.
            Then check what you missed. This beats passive rereading.

            📅 Spaced Repetition:
            Review at increasing intervals: Day 1, Day 3, Day 7, Day 21.
            Anki is excellent for definitions, formulas, protocols, and commands.

            🧑‍🏫 Feynman Technique:
            Explain a concept like you are teaching a younger student.
            If you get stuck, restudy that part and simplify again.

            🍅 Pomodoro:
            25 minutes focused work, 5 minutes break. After 4 cycles,
            take a longer break. This helps prevent mental fatigue.

            💡 CS-specific study:
            - Algorithms: solve problems.
            - Programming: write code and build projects.
            - Math/statistics: solve exercises daily.
            - Networks/OS/security: draw diagrams and use flashcards.

            Tools: Anki, Notion, Obsidian, Excalidraw, CS50, 3Blue1Brown.
            """
        ),
    ),
    (
        [
            "time management",
            "manage my time",
            "time management tips",
            "how to manage time",
            "daily schedule",
            "weekly plan",
            "إدارة الوقت",
            "كيف أنظم وقتي",
            "procrastination",
            "تسويف",
            "i keep procrastinating",
            "i waste time",
        ],
        _clean(
            """
            Time management for CS students — practical system:

            📅 Weekly planning:
            1. List all assignments, labs, projects, and study tasks.
            2. Estimate time honestly, then multiply by 1.5.
            3. Assign tasks to specific days and time blocks.
            4. Leave buffer time for overflow.

            📆 Daily structure:
            - Morning: hardest task, like algorithms or coding.
            - Afternoon: review, labs, reading.
            - Evening: light flashcards, planning, or videos.

            ⚡ Beat procrastination:
            - Start with a 5-minute timer.
            - Break big tasks into tiny first actions.
            - Put your phone away during study blocks.
            - Use accountability with a friend.

            ⚖️ With 15-18 credit hours:
            - Each subject needs at least 2 hours/week outside class.
            - Programming subjects need 4-6 hours/week.
            - Start exam prep 3 weeks before finals, not 3 days.
            """
        ),
    ),
    (
        [
            "stress",
            "stressed",
            "burnout",
            "burnt out",
            "overwhelmed",
            "too much",
            "can't handle it",
            "exhausted",
            "i give up",
            "this is too hard",
            "too hard",
            "so hard",
            "cs is hard",
            "struggling",
            "ضغط",
            "تعبت",
            "مش قادر أكمل",
            "مبقتش قادر",
            "i'm behind",
            "i failed",
            "i'm failing",
            "im failing",
            "afraid to fail",
            "imposter syndrome",
            "حاسس إني مش كافي",
        ],
        _clean(
            """
            What you're feeling is valid. CS is genuinely hard —
            you're not struggling because you're not smart enough.

            🔥 Why CS feels overwhelming:
            - Concepts build on each other.
            - Programming takes months of practice, not days.
            - Some classmates had prior exposure.
            - 15+ credit hours is a heavy load.

            💙 If you're burned out now:
            1. Take a real break if you can.
            2. Sleep properly before trying to grind more.
            3. Go outside briefly.
            4. Talk to a friend, family member, professor, or advisor.

            📉 If you're failing or at risk:
            - Speak to your academic advisor early.
            - Check academic warning options before the crisis grows.
            - One rough semester is not the end.

            🧠 Imposter syndrome:
            Almost every CS student feels behind sometimes. Compare yourself
            with your past self, not with someone's highlight reel.

            📍 If stress is seriously affecting daily life:
            Student Affairs can guide you to support services.
            📍 FCI, Sadat Academy, Maadi Campus.
            """
        ),
    ),
    (
        [
            "cs career",
            "jobs with cs degree",
            "what can i do with cs",
            "career paths cs",
            "cs jobs",
            "وظائف cs",
            "what should i specialise in",
            "which major is better",
            "career in tech",
            "tech jobs egypt",
            "هعمل ايه بعدين",
            "هعمل ايه",
            "أعمل ايه في المستقبل",
            "اعمل ايه في المستقبل",
            "أعمل ايه",
            "اعمل ايه",
            "مش عارف أختار",
            "مش عارف اختار",
            "هشتغل ايه",
            "في شغل ولا لا",
        ],
        _clean(
            """
            Career paths with an FCI degree:

            💻 Software Development:
            Frontend, backend, full-stack, and mobile development.

            🤖 AI & Data:
            Machine Learning Engineer, Data Scientist, Data Engineer,
            AI Research Scientist.

            🔐 Cybersecurity:
            Penetration Tester, SOC Analyst, Security Engineer,
            Digital Forensics Analyst.

            ☁️ Cloud & DevOps:
            Cloud Engineer, DevOps Engineer, Site Reliability Engineer.

            🎮 Game Development:
            Unity, Unreal Engine, gameplay programming, tools programming.

            📊 Business & Tech:
            Business Analyst, Product Manager, IT Consultant,
            Technical Project Manager.

            🇪🇬 High demand in Egypt right now:
            - Flutter/mobile developers
            - React + Node.js full-stack
            - Data analysts with Power BI/Python
            - Cybersecurity analysts
            - AI/ML engineers
            - Cloud engineers
            """
        ),
    ),
    (
        [
            "how long to learn programming",
            "how long to get a job",
            "am i learning fast enough",
            "is this normal",
            "programming is hard",
            "i can't code",
            "i'm bad at coding",
            "how long does it take",
            "مش فاهم البرمجة",
            "البرمجة صعبة",
            "مش فاهم كود",
            "مش قادر أفهم",
        ],
        _clean(
            """
            How long it really takes — honest answer:

            📅 Realistic timelines:
            - Basic programs: 4-8 weeks of consistent practice.
            - Comfortable in one language: 3-6 months.
            - Building projects independently: 6-12 months.
            - Junior job or internship readiness: 1-2 years.
            - Genuinely strong programmer: 3-5 years.

            🧠 Normal learning curve:
            - Weeks 1-4: everything feels confusing.
            - Months 2-3: small ideas start clicking.
            - Months 4-6: you can read code more comfortably.
            - Months 6-12: you solve problems you could not solve before.

            ⚠️ Normal signs:
            - Bugs take hours.
            - Tutorials make sense but solo coding is hard.
            - You forget concepts and need to revisit them.
            - You feel slower than classmates.

            🔑 The fastest learners build before they feel ready.
            Small projects teach more than endless tutorials.
            """
        ),
    ),
]


EXTENDED_TOPICS = tuple(CS_EXTENDED_TOPICS) + tuple(EXTENDED_TOPICS)


def extended_topic_answer(question: str) -> Optional[str]:
    lowered = _normalize(question)
    for triggers, response in EXTENDED_TOPICS:
        if any(_trigger_matches(lowered, trigger) for trigger in triggers):
            return response
    return None


def extended_topic_trigger_words() -> set[str]:
    words: set[str] = set()
    for triggers, _ in EXTENDED_TOPICS:
        for trigger in triggers:
            words.update(re.findall(r"[a-z0-9]+|[\u0621-\u063a\u0641-\u064a]+", _normalize(trigger)))
    return {word for word in words if len(word) >= 2}
