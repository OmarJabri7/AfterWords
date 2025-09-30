# 🌌 AfterWords – Conversations Beyond  

**AfterWords** is an experimental application that lets users recreate and speak with the voices of their loved ones.  
It combines **FastAPI**, **AWS Lambda**, **DynamoDB**, **EventBridge**, and **ElevenLabs** to deliver ephemeral, voice-based chat sessions.  

⚠️ **Disclaimer:** This is a technical proof-of-concept. It is **not a medical, therapeutic, or spiritual product** and must not be used as a substitute for professional guidance.

---

## ✨ Features
- 🎙️ **Voice Cloning** – Upload a short `.wav` sample and generate a cloned voice via ElevenLabs.  
- 💬 **Conversational Agent** – Powered by GPT models to answer as a chosen persona (`who`, `relation`, `lang`).  
- 🌍 **Translation** – Responses can be auto-translated into Arabic, English, or French.  
- ⏱️ **Ephemeral Sessions** – Each chat session lasts 10 minutes, with automatic cleanup of cloned voices and session data.  
- ☁️ **Serverless Architecture** – Runs on AWS Lambda, stores session metadata in DynamoDB, and uses EventBridge to schedule cleanup.  
- 🖥️ **Streamlit Frontend** – Simple chat UI with live audio playback, countdown timers, and session restoration.  

---

## 🗂️ Project Structure
```
AfterWords/
├── LICENSE
├── README.md
├── app.py                   # FastAPI entrypoint
├── run_app.sh               # Script to run API
├── deploy_app.sh            # Script to deploy app
├── test_local_app.sh        # Local test runner
├── voice_cleanup.py         # Cleanup Lambda
├── tests/                   # Test suite
│   └── __init__.py
├── terraform/               # Terraform IaC
│   ├── dynamo_db.tf
│   ├── ecr.tf
│   ├── event_hub.tf
│   ├── lambda.tf
│   ├── main.tf
│   ├── terraform.tfstate
│   └── terraform.tfstate.backup
├── membox/
│   ├── Dockerfile.api
│   ├── Dockerfile.cleanup
│   ├── README.md
│   ├── deploy.sh
│   ├── poetry.lock
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── containers/
│   │   ├── Dockerfile.api
│   │   └── Dockerfile.cleanup
│   ├── membox/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── utils.py
│   │   └── voice_cleanup.py
│   └── tests/
│       └── __init__.py
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.12+
- AWS account with credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)  
- ElevenLabs API key (`ELEVEN_API_KEY`)  
- OpenAI API key (`OPENAI_API_KEY`)  
- [Terraform](https://developer.hashicorp.com/terraform/downloads) for infra  

### 2. Install dependencies
```bash
pip install -r membox/requirements.txt
```

### 3. Environment Variables
Create a `.env` file in project root:
```env
OPENAI_API_KEY=sk-xxxx
ELEVEN_API_KEY=eleven-xxxx
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_REGION=us-east-2
LEASES_TABLE=leases
SCHEDULER_GROUP=after_words-session-schedules
SCHEDULER_ROLE_ARN=arn:aws:iam::...:role/after_words-scheduler-invoke-cleanup
CLEANUP_LAMBDA_ARN=arn:aws:lambda:us-east-2:...:function:lambda_cleanup
```

### 4. Run API locally
```bash
uvicorn app:app --reload --port 8000
```

### 5. Run Streamlit frontend
```bash
streamlit run streamlit_app.py
```

---

## 🔌 API Endpoints

| Method | Endpoint   | Description |
|--------|------------|-------------|
| GET    | `/`        | Healthcheck – returns simple JSON |
| POST   | `/tts`     | Clone or reuse a voice and return synthesized speech |

---

## 🛠️ Deployment

### With Docker
- API container: `membox/Dockerfile.api`  
- Cleanup container: `membox/Dockerfile.cleanup`  

### With Terraform
- `terraform/main.tf` provisions:
  - Lambda for API
  - Lambda for cleanup
  - DynamoDB for session leases
  - EventBridge Scheduler for cleanup tasks
  - ECR repositories

---

## 📌 Next Steps
- [ ] Add auth to secure API endpoints  
- [ ] Extend supported languages  
- [ ] Improve session UX (longer chats, storage)  
- [ ] CI/CD with GitHub Actions  

---

👤 Author: Omar Jabri  
🔗 GitHub: [OmarJabri7](https://github.com/OmarJabri7)  
