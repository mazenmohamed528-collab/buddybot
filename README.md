# BuddyBot

BuddyBot is the FCI campus assistant for Sadat Academy for Management Sciences.
It connects a Rasa REST chatbot to the SAMS website and answers questions about
students, GPA, courses, schedules, instructors, policies, documents, services,
and campus support in Arabic or English.

## Local Docker Run

```powershell
cd C:\dev\rasa_project
docker compose up -d
```

Rasa REST webhook:

```text
http://127.0.0.1:5005/webhooks/rest/webhook
```

Action server:

```text
http://127.0.0.1:5055
```

## Deployment

See `DEPLOYMENT.md` for Railway/Render deployment notes and Supabase database
configuration.
