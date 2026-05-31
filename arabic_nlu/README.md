# BuddyBot Arabic CAMeLBERT Intent Router

This module adds an optional Arabic transformer layer to BuddyBot's hybrid routing.

It uses:

```python
CAMeL-Lab/bert-base-arabic-camelbert-mix
```

Important: do not use the older car-listing/fraud CAMeLBERT checkpoint for BuddyBot routing. BuddyBot needs a separate fine-tune on Arabic university questions. The runtime rejects unsupported label maps such as `fraud` / `legitimate`.

The goal is not to replace Rasa DIET. It is a second-stage Arabic intent classifier used by the action server before choosing SQL, RAG, file retrieval, or normal conversation.

## Intent Labels

The BuddyBot-specific fine-tune uses these labels:

- `greeting`
- `attendance_policy`
- `gpa_query`
- `academic_warning`
- `schedule_query`
- `student_lookup`
- `educational`
- `registration`
- `fees_query`
- `file_request`

Runtime route mapping:

- `greeting` -> `conversational`
- `attendance_policy`, `academic_warning`, `registration`, `fees_query` -> `policy_rag`
- `gpa_query`, `schedule_query`, `student_lookup` -> `structured_sql`
- `educational` -> `educational_rag`
- `file_request` -> `file_retrieval`

The older route-label config is kept for compatibility, but the default training config is now the BuddyBot intent config.

## Training Data

Training examples live in:

```text
data/arabic_buddybot_intent_training.jsonl
```

Each line has:

```json
{"text": "الغياب", "label": "attendance_policy"}
```

## Train

Install the optional ML dependencies inside the Rasa environment:

```powershell
cd C:\dev\rasa_project
.\.venv\Scripts\python.exe -m pip install -r arabic_nlu\requirements-camelbert-router.txt
```

Train:

```powershell
.\.venv\Scripts\python.exe arabic_nlu\train_camelbert_router.py --config arabic_nlu\camelbert_intent_config.json
```

The model is saved to:

```text
models/arabic_camelbert_intent_router
```

## Runtime Integration

The action server automatically looks for:

```text
C:\dev\rasa_project\models\arabic_camelbert_intent_router
```

You can override the path:

```powershell
$env:BUDDYBOT_ARABIC_ROUTER_MODEL_DIR="C:\path\to\model"
```

You can tune the confidence threshold:

```powershell
$env:BUDDYBOT_ARABIC_ROUTER_THRESHOLD="0.75"
```

You can disable it:

```powershell
$env:BUDDYBOT_ENABLE_CAMELBERT_ARABIC_ROUTER="0"
```

If the model or dependencies are missing, BuddyBot falls back to deterministic Arabic routing.

## Routing Order

Arabic query:

```text
pre-router greeting/continuation guards
-> CAMeLBERT intent classifier
-> route if confidence >= 0.75
-> deterministic/semantic fallback
```

This prevents entity matching from overpowering semantic intent:

- `هات طلبة الداتا ساينس` -> SQL
- `ايه هو علم البيانات` -> RAG explanation
- `الغياب` -> official policy RAG
- `ابعتلي ملف الجدول` -> schedule/file handling
