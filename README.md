# APT Portfolio Pulse

A robust real estate portfolio AI backend serving document ingestion, semantic search / RAG, lease & invoice intelligence, user/billing workflows, and admin analytics.

---

## 🚀 Overview

APT Portfolio Pulse combines property management workflows with advanced document AI and conversational retrieval, designed for:

- Real estate property and lease admin teams
- Portfolio asset management with document versioning
- AI-assisted lease summarization, invoice extraction, and email drafting
- Subscription-based SaaS with usage protections

The backend is built with FastAPI, SQLModel, Pinecone, and Google Gemini.

---

## 🧩 Core Features

### 1) Authentication & Authorization

- User signup / login (`/auth/register`, `/auth/login`)
- JWT issuance with expiration using `SECRET_KEY` and `ACCESS_TOKEN_EXPIRE_HOURS`
- OTP verification (`/auth/forgot-password`, `/auth/verify-otp`, `/auth/reset-password`)
- Superadmin guard (`/admin` endpoints) using `get_current_superadmin`

### 2) User Profiles

- Fetch current user (`/users/me`)
- Update profile details + upload profile/banner images

### 3) Building Management

- Create/list/read/update/delete building entities (`/buildings`)
- Per-user ownership & category validation

### 4) File Management + AI Ingestion

- Upload + update + delete files (`/files/{category}`)
- Text extraction (PDF/DOCX) and indexing
- Universal chunking + vectorization in Pinecone
- File-to-user/building scoping

### 5) Conversational AI / RAG

- Chat sessions (`/chat/sessions`)
- Context-aware queries using Pinecone + Gemini (`/chat/ask`, `/chat/ask_summary`)
- Direct Gemini chatbot mode (`/chat/gemini`)

### 6) Document AI Workloads

- Document cleaner/extractor (`/doc_ai/cleaner`)
- Lease abstract generation (`/doc_ai/lease_abstract`)
- Lease content generation (`/doc_ai/lease-generator`)
- PDF report summarizer (`/doc_ai/report-summarizer`)

### 7) Invoice Service

- Invoice upload + metadata extraction (`/services/invoice/upload`)
- Conversation over invoice data (`/services/invoices/chat`)

### 8) Subscription + Stripe Billing

- Setup plan / trial (`/billing/setup`)
- Status / history endpoints
- Cancel (`/billing/cancel`) and renew (`/billing/renew`)
- Stripe webhook processing (`/billing/webhook`)

### 9) Admin Analytics

- Global metrics: users, subscriptions, buildings, docs, chat sessions
- User list + failed payment report
- Building and subscription reports

### 10) User Dashboard

- Summary endpoints on counts, recent docs, category counts

### 11) DB Health

- `GET /db/health`

---

## 🗂️ Data Model

- `User`, `OTP`
- `Building`
- `File`
- `ChatSession`, `Message`
- `Subscription`, `SubscriptionHistory`, `ProcessedWebhook`
- Email templates, tenants, tenant keys (email drafting features)

---

## 🛠️ Architecture

- FastAPI service in `app/main.py`
- Routers in `app/routers/*`
- SQLModel/SQLAlchemy async DB in `app/core/database.py`
- Pinecone setup in `app/services/index_manager.py`
- Gemini AI logic in `app/services/ai/llm.py`
- RAG service in `app/services/ai/rag.py`
- Document chunking/intelligence in `app/services/ai/smart_chunker.py`
- Stripe provider in `app/services/payments/*`

---

## 📦 Requirements

See `requirements.txt`:

- `fastapi`, `uvicorn`, `sqlmodel`, `asyncpg`
- `pinecone`, `google-generativeai`
- `stripe`, `python-multipart`, `python-docx`, `PyPDF2`

---

## ⚙️ Configuration

Copy `.env` from sample (not provided; create manually):

- `DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<host>/<db>`
- `SECRET_KEY=<very-secret>`
- `PINECONE_API_KEY`, `PINECONE_INDEX`
- `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`
- `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`
- `TRIAL_DAYS` (default 7)

---

## ▶️ Run Locally

1. `python -m venv .venv`
2. `.venv\Scripts\activate` (Windows)
3. `pip install -r requirements.txt`
4. `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

Swagger: `http://localhost:8000/docs`

---

## 🔐 Security Governance

- JWT used for auth
- Subscription enforced at endpoint level (`check_subscription`)
- `get_current_superadmin` permission gates for admin
- File operations require owner check via user + building match

---

## 📜 Recommended Extensions

- Add robust tests (`tests/`) for services, routers, and auth flows
- Add data migration path (Alembic)
- Implement role-based scopes/permissions beyond superadmin

---

## 🧪 QA & Health

- `GET /db/health`
- Verify `GET /dashboard/summary` after onboarding and dataset ingestion
- Validate Stripe webhook events and subscription state updates

---

## ✨ Contribution

1. Fork repo
2. Create feature branch
3. Add tests
4. `pytest` and lint
5. PR with description

---

## 📬 Support

For questions about integration, configuration, or extension points (RAG, Pinecone, Gemini), open an issue or contact project maintainer.
