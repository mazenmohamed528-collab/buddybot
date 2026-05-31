# BuddyBot Testing Plan

This plan verifies BuddyBot after the smart-routing, SQL, RAG/Q&A, Arabic normalization, and context-memory fixes.

## Goals

1. Confirm short keywords no longer fail.
2. Confirm SQL questions do not fall into official-guide fallback.
3. Confirm official policy/student-guide questions cite official Q&A/RAG sources.
4. Confirm Arabic, English, Egyptian Arabic, and mixed Arabic-English all route correctly.
5. Confirm context memory works across turns.
6. Confirm old failed examples stay fixed.

## Services Required

Run these in separate PowerShell windows:

```powershell
cd C:\dev\rag_service
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
cd C:\dev\sql_engine_service
C:\dev\rag_service\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8010
```

```powershell
cd C:\dev\rasa_project
.\.venv\Scripts\rasa.exe run actions
```

```powershell
cd C:\dev\rasa_project
.\.venv\Scripts\rasa.exe run --enable-api --cors "*" -p 5005
```

For manual testing only:

```powershell
cd C:\dev\rasa_project
.\.venv\Scripts\rasa.exe shell
```

## Test Checklist

### 1. Preflight

- `rasa data validate` passes.
- Rasa action server is using the latest code, not a stale process.
- SQL engine on `8010` is restarted after SQL code changes.
- RAG service on `8000` is restarted or auto-reloaded after RAG changes.
- Latest model is trained after NLU/domain/rules changes.
- REST channel exists in `credentials.yml`.

### 2. Conversational Routing

- `hi` returns BuddyBot greeting.
- `اهلا` returns BuddyBot greeting.
- `ازيك` is handled conversationally, not RAG.
- `hru` is handled conversationally, not official guide fallback.

### 3. Short Arabic Keywords

- `التخصص` answers specialization rules.
- `تغيير التخصص` answers change-specialization policy.
- `تغيير المسار` maps to change-specialization policy.
- `الاقسام` lists FCI departments.
- `الغياب` answers attendance/absence policy.
- `الرسوم` answers fees/refund policy.
- `الانذار الاكاديمي` answers academic warning policy.

### 4. Database Routing

- `student 22209` finds `Mazen Mohamed Abd Elmageed Badawi`.
- `show me student 209` resolves partial ID to `2122209`.
- `who teaches data science?` returns `Dr. Ahmed Esmat`.
- `who teaches human rights?` returns teaching assignments.
- `who's dr Ahmed Esmat?` returns instructor assignments.
- `show me all students in data sciencs` still returns Data Science only, not all students.
- `how manay students in software engineering` returns a count, not a list.
- Schedule, room, free-room, department analytics, and course-teacher queries route to SQL.

### 5. Official Guide / Policy Routing

- Admission requirements answer from official Q&A/RAG.
- Required documents answer from official Q&A/RAG.
- Attendance uses the 25% absence rule.
- Exam grading uses 15% midterm, 60% final, 25% coursework.
- GPA rules explain grading scale and cumulative GPA.
- Academic warning uses GPA below 2.0 and 15-hour cap.
- Fees mention refund windows/percentages.
- Discipline mentions violations/penalties.

### 6. Educational RAG Routing

- `what's data science?` explains Data Science, not student list.
- `tell me about software engineering` explains the department, not SE students.
- `علوم الحاسب` explains the department, not first-year courses.
- `what courses should i take if i'm in data science` gives guidance, not students.
- `what's the difference between Data Science and AI?` returns the AI-vs-Data-Science comparison and does not include unrelated API chunks.

### 7. Context Memory

Manual sequence:

```text
show me student 22209
what's his gpa?
what courses does he take?
```

Expected:

- First answer identifies Mazen.
- Second answer uses Mazen automatically and returns his GPA.
- Third answer uses Mazen automatically and returns course/enrollment information.

Pagination sequence:

```text
show me all students in data science
all of them
all of them
```

Expected:

- First answer shows 1-10 of 38.
- Second answer shows remaining results.
- Third answer says the result set is already finished.

### 8. Fallbacks

- Unknown guide question says the official guide/knowledge base does not include it.
- Unknown database record says matching database data was not found.
- Unclear casual nonsense does not pretend to know; it asks for clarification or gives a helpful fallback.

### 9. Old Failure Regression List

These must stay fixed:

| Query | Expected |
|---|---|
| `who teaches data science?` | SQL teacher lookup, Dr. Ahmed Esmat |
| `who teaches human rights?` | SQL teacher assignments |
| `who's dr Ahmed Esmat?` | SQL instructor lookup |
| `what's data science?` | Educational RAG, no student list |
| `what's the difference between Data Science and AI?` | Clean comparison, no API chunk |
| `what's software engineering?` | Educational RAG |
| `التخصص` | Official specialization info |
| `تغيير التخصص` | Official change-specialization policy |
| `تغيير المسار` | Official change-specialization policy |
| `الاقسام` | Departments list |
| `الغياب` | Attendance policy, no course list |
| `علوم الحاسب` | Department explanation, no CP101 course list |
| `الاوراق المطلوبة للالتحاق؟` | Admission documents, no SE department chunk |
| `show me all students in data sciencs` | Data Science students only |
| `al of them` | Pagination continuation, no 503 |
| `and the rest?` | Pagination continuation, no 503 |

## Automated Test Dataset

The acceptance dataset lives at:

```text
C:\dev\rasa_project\tests\buddybot_acceptance_cases.json
```

It contains English, Arabic, Egyptian Arabic, and mixed-language cases for:

- conversational routing
- short keywords
- student lookup
- GPA lookup
- instructor lookup
- course teacher lookup
- schedule
- departments
- rooms
- official guide policy
- educational RAG
- context memory
- fallbacks
- old regression failures

Each case can specify:

- `message`
- `expected_route`
- `expected_intents`
- `expected_actions`
- `expected_keywords_all`
- `expected_keywords_any`
- `forbidden_keywords`
- `session_id` for multi-turn context tests

## Automated Test Runner

Script:

```text
C:\dev\rasa_project\tests\run_buddybot_acceptance_tests.py
```

Run all tests:

```powershell
cd C:\dev\rasa_project
.\.venv\Scripts\python.exe tests\run_buddybot_acceptance_tests.py
```

Run only Arabic cases:

```powershell
.\.venv\Scripts\python.exe tests\run_buddybot_acceptance_tests.py --include ar
```

Run only database cases:

```powershell
.\.venv\Scripts\python.exe tests\run_buddybot_acceptance_tests.py --include database_query
```

Run without intent/action inspection:

```powershell
.\.venv\Scripts\python.exe tests\run_buddybot_acceptance_tests.py --no-inspect-api
```

Make missing `/model/parse` or tracker API fail the run:

```powershell
.\.venv\Scripts\python.exe tests\run_buddybot_acceptance_tests.py --require-inspection
```

Failure report:

```text
C:\dev\rasa_project\tests\buddybot_acceptance_failures.json
```

## Pass Criteria

- 100% pass for regression-old-failures cases.
- 95%+ pass for full acceptance dataset.
- 100% pass for database safety checks: no policy question returns SQL lists, no educational question returns student lists.
- No 500/503 responses.
- No stale sources in policy answers.
- No old wrong chunks for admission documents, attendance, specialization, or departments.

## What To Do When A Case Fails

1. Check whether Rasa was retrained after NLU/domain/rules changes.
2. Restart `rasa run actions`.
3. Restart SQL engine if SQL compiler/router/validator changed.
4. Check `tests\buddybot_acceptance_failures.json`.
5. If intent is wrong but action response is correct, add NLU examples and retrain.
6. If intent is correct but response is wrong, inspect the action/SQL/RAG handler.
7. If RAG has wrong chunks, update metadata filtering or query expansion and reingest.
