# ISUSI — Private FD Portfolio Manager

> **Your Money. Your Secret. Your Legacy.**

ISUSI is a mobile-first web app for Sri Lankan Fixed Deposit holders to privately track FDs across all banks, get smart maturity reminders, and pass on FD details to a trusted beneficiary through an AI-powered Digital Legacy System.

---

## Problem Statement

| Problem | Impact |
|---|---|
| No way to track FDs across multiple banks | Miss maturity dates, lose interest |
| No privacy from family members | Elderly savers feel financially vulnerable |
| No secure way to pass FD info after death | Millions in FDs go unclaimed |

---

## Key Features

### FD Portfolio Tracker
- Add FDs from any Sri Lankan bank manually
- Auto-calculates maturity date, interest earned, and maturity amount
- Colour-coded maturity reminders (30 / 7 / matured)
- Works fully offline — the tracker itself needs no backend

### Private Vault
- Every FD and legacy setting is encrypted **in your browser** with **AES-256-GCM** (Web Crypto API), key derived from your own passphrase via PBKDF2 (150,000 iterations)
- Nothing is stored unencrypted, and nothing leaves the device — no cloud sync
- Forget the passphrase and the vault cannot be recovered, by design

### Digital Legacy System
- Nominate one trusted beneficiary with a check-in / alert threshold (in days)
- The **Legacy Guardian** agent decides — conservatively — whether to send a check-in or alert the beneficiary
- Framed around Sri Lanka's Wills Ordinance and Nominee Law (see in-app Legal Framework panel)

### 🤖 AI Agent System (Powered by Yaala Labs Agent Kernel)
Three specialist agents, built on the **OpenAI Agents SDK** and run through **[Agent Kernel](https://github.com/yaalalabs/agent-kernel)** (`pip install agentkernel`), with **Groq's Llama 3.3 70B** plugged in as the underlying model (chosen for its high free-tier rate limit):

| Agent | What it does |
|---|---|
| **FD Advisor Agent** (`fd_advisor`) | Analyses each FD, gives RENEW / HOLD / WITHDRAW advice with reasoning |
| **Portfolio Health Agent** (`health_scorer`) | Scores the portfolio across 5 dimensions, gives grade A–F |
| **Legacy Guardian Agent** (`legacy_guardian`) | Decides when to check in on / alert the beneficiary |

A `triage` agent sits in front and hands off to whichever specialist a request needs — the standard Agent Kernel / OpenAI Agents SDK pattern.

---

##  Architecture

```
┌─────────────────────────────────────────────┐
│         ISUSI Frontend (React, CDN)          │
│  Dashboard │ Add FD │ AI Agents │ Legacy      │
│  AES-256-GCM vault (Web Crypto, local only)  │
└──────────────────┬──────────────────────────┘
                    │ POST /run  (Agent Kernel REST API)
                    ▼
┌─────────────────────────────────────────────┐
│      Agent Kernel Runtime (isusi_agent.py)   │
│                                               │
│                  triage                      │
│       │            │            │            │
│       ▼            ▼            ▼            │
│  fd_advisor   health_scorer  legacy_guardian  │
│   (OpenAI Agents SDK agents, each with a      │
│    small tool for exact FD math)             │
│                     │                        │
│         Llama 3.3 70B (via Groq)              │
│   (via Groq's OpenAI-compatible endpoint)     │
└─────────────────────────────────────────────┘
```

---

##  Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18 (via CDN, no build step), Web Crypto (AES-256-GCM + PBKDF2), CSS |
| **AI Agent Runtime** | [Yaala Labs Agent Kernel](https://github.com/yaalalabs/agent-kernel) (`agentkernel` on PyPI) |
| **Agent Framework** | OpenAI Agents SDK (via Agent Kernel's `OpenAIModule`), tools defined with the SDK's own `@function_tool` decorator |
| **AI Model** | Groq's Llama 3.3 70B, called through Groq's OpenAI-compatible endpoint (30 requests/minute free tier) |
| **API Server** | Agent Kernel's built-in `RESTAPI` (FastAPI under the hood) |
| **Encryption** | AES-256-GCM, entirely client-side |

---

##  Setup Instructions

### Prerequisites
- Python 3.12 – 3.13.x (Agent Kernel's supported range)
- A modern browser (Web Crypto & `crypto.randomUUID` support)
- A Groq API key — free, no card required, at [console.groq.com/keys](https://console.groq.com/keys)

### 1. Clone the repository
```bash
git clone https://github.com/isiri20250974-design/ISUSI.git
cd ISUSI
```

### 2. Install Agent Kernel + the OpenAI Agents SDK + API extras
```bash
pip install -r requirements.txt
# equivalent to: pip install "agentkernel[openai,api]"
```

### 3. Set your Groq API key
```bash
cp .env.example .env
# edit .env and paste your key, then:
export GROQ_API_KEY="your_groq_api_key_here"
```

### 4. Start the AI agent backend
```bash
python isusi_agent.py
```
You should see:
```
============================================
  🏦 ISUSI — AI Agent Backend
  Powered by Yaala Labs Agent Kernel
============================================

  Agents ready:
  isusi_fd_advisor      (fd_advisor)
  isusi_health_scorer   (health_scorer)
  isusi_legacy_guardian (legacy_guardian)
  isusi_triage          (triage)

  Server running on http://localhost:8000
```
`config.yaml` pins the REST API to port 8000, matching the frontend's `AGENT_BASE_URL`.

You can also test the backend directly, independent of the frontend:
```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"agent": "fd_advisor", "prompt": "[{\"id\":\"1\",\"bank\":\"Sampath Bank\",\"principal\":500000,\"rate\":11.5,\"termMonths\":12,\"maturityDate\":\"2026-08-10\"}]"}'
```

### 5. Open the app
With the backend from step 4 still running, open your browser to:
```
http://localhost:8000/custom/app
```
This serves `index.html` **from the same backend**, so the page and the API share one origin and the browser never blocks the AI Agents tab's requests. (Double-clicking `index.html` directly also works for the FD tracker and vault, but the browser will block calls to the AI Agents tab as cross-origin — always use the URL above once the backend is running.)

---

## 🤖 AI Agent Workflow

### FD Advisor Agent
```
User taps "Run FD Advisor"
→ Frontend POSTs {agent: "fd_advisor", prompt: <FD list as JSON>} to /run
→ Agent Kernel's Runtime resolves the fd_advisor agent and runs it via the OpenAI Agents SDK
→ The agent calls its get_fd_metrics tool for exact days-to-maturity & maturity amounts
→ Llama 3.3 70B reasons step-by-step through each FD using those exact numbers
→ Returns RENEW / HOLD / WITHDRAW per FD + a weekly action, as raw JSON
→ Frontend parses the JSON and displays results as cards
```

### Legacy Guardian Agent
```
Owner inactive for N days
→ Frontend POSTs {agent: "legacy_guardian", prompt: <inactivity JSON>} to /run
→ Agent calls get_inactivity_status to see which thresholds are crossed
→ Agent reasons: "alert threshold crossed, but no check-in was sent yet —
                  send a check-in before ever alerting the beneficiary"
→ Decision: SEND_CHECKIN / NONE / ALERT_BENEFICIARY, with confidence + reasoning
```

---

##  Project Structure

```
ISUSI/
├── index.html          # Full frontend app (React via CDN, vault, dashboard, agents)
├── isusi_agent.py       # Agent Kernel backend: triage + 3 specialist OpenAI-SDK agents
├── config.yaml           # Agent Kernel config (REST API port)
├── requirements.txt      # agentkernel[openai,api]
├── .env.example          # Template for GROQ_API_KEY
├── .gitignore
├── README.md             # This file
└── docs/
    ├── architecture.png  # (add your own diagram export here)
    └── screenshots/
```

---

## Digital Legacy — Legal Framework

- **Wills Ordinance** — FD holders retain full control over who receives their assets
- **Nominee Law** — a nominated beneficiary receives FD info as a trustee, not as owner
- **PDPA Sri Lanka** — all data stays encrypted on-device and is never sold or shared

> ⚠️ ISUSI is an organisational tool only. It does not transfer funds and does not replace a formal Last Will and Testament.

---

## 🇱🇰 About

Built for IDEALIZE 2026 — organised by AIESEC in University of Moratuwa.

**Founder:** Isiri Masinghe
**University:** IIT — Informatics Institute of Technology, Colombo
**Degree:** BSc Business Data Analytics
**Contact:** isiriwathsala2003@gmail.com

---

## 📄 License

MIT License — free to use and build upon. Agent Kernel itself is Apache-2.0 licensed by Yaala Labs.

---

*ISUSI — Your Money. Your Secret. Your Legacy.*🌿
