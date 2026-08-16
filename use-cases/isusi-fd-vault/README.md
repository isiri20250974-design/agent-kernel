<p align="center">
  <img src="logo.png" alt="ISUSI Logo" width="200">
</p>

<h1 align="center"> ISUSI Private FD Portfolio Manager</h1>

<p align="center"><b>Your Money. Your Secret. Your Legacy.</b></p>

ISUSI is a mobile-first web app for Sri Lankan Fixed Deposit holders to privately track FDs across all banks, get smart maturity reminders, and pass on FD details to a trusted beneficiary through an AI-powered Digital Legacy System.

Built for **IDEALIZE 2026 Mini-Competition** — powered by [Yaala Labs Agent Kernel](https://github.com/yaalalabs/agent-kernel).

---

## 🎯 Problem Statement

| Problem                                   | Impact                                     |
| ------------------------------------------ | ------------------------------------------- |
| No way to track FDs across multiple banks | Miss maturity dates, lose interest         |
| No privacy from family members             | Elderly savers feel financially vulnerable |
| No secure way to pass FD info after death  | Millions in FDs go unclaimed               |

> ⚠️ **Under Sri Lankan law**, if an FD or bank account sees no transactions or correspondence for **over 10 years**, it is classified as *abandoned property* under the Finance Business Act No. 42 of 2011 and reported to the Central Bank of Sri Lanka (CBSL). The funds don't disappear — the rightful owner or heir can still reclaim them with proof of identity — but locating, tracking, and proving ownership of "forgotten" FDs becomes far harder once this happens. This is exactly the gap ISUSI's Digital Legacy System is built to close: keeping FD records visible to a trusted beneficiary *before* an account ever goes dormant.

---

## 💡 Solution Overview

ISUSI solves this with three parts working together:

1. **FD Portfolio Tracker** — add FDs from any Sri Lankan bank manually; the app auto-calculates maturity date, interest earned, and maturity amount, with colour-coded reminders (30 / 7 / matured days out).
2. **Private Vault** — every FD and legacy setting is encrypted **in the browser** with AES-256-GCM (Web Crypto API), key derived from your own passphrase via PBKDF2 (150,000 iterations). Nothing leaves the device unencrypted, and nothing syncs to the cloud.
3. **Digital Legacy System** — nominate one trusted beneficiary with a check-in / alert threshold. A **Legacy Guardian** AI agent conservatively decides whether to send a check-in reminder or alert the beneficiary, framed around Sri Lanka's Wills Ordinance and Nominee Law.

### 🤖 AI Agent System (Powered by Yaala Labs Agent Kernel)

Three specialist agents, built on the **OpenAI Agents SDK** and run through **[Agent Kernel](https://github.com/yaalalabs/agent-kernel)** (`agentkernel` on PyPI), with **Groq's Llama 3.3 70B** as the underlying model:

| Agent                                          | What it does                                                            |
| ----------------------------------------------- | -------------------------------------------------------------------------- |
| **FD Advisor Agent** (`fd_advisor`)             | Analyses each FD, gives RENEW / HOLD / WITHDRAW advice with reasoning     |
| **Portfolio Health Agent** (`health_scorer`)    | Scores the portfolio across 5 dimensions, gives grade A–F                |
| **Legacy Guardian Agent** (`legacy_guardian`)   | Decides when to check in on / alert the beneficiary                      |

A `triage` agent sits in front and hands off to whichever specialist a request needs — the standard Agent Kernel / OpenAI Agents SDK pattern.

---

## 🏗️ Architecture

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

## 🛠️ Tech Stack

| Layer                | Technology                                                                                                         |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **Frontend**          | React 18 (via CDN, no build step), Web Crypto (AES-256-GCM + PBKDF2), CSS                                          |
| **AI Agent Runtime**  | [Yaala Labs Agent Kernel](https://github.com/yaalalabs/agent-kernel) (`agentkernel` on PyPI)                       |
| **Agent Framework**   | OpenAI Agents SDK (via Agent Kernel's `OpenAIModule`), tools defined with the SDK's own `@function_tool` decorator |
| **AI Model**          | Groq's Llama 3.3 70B, called through Groq's OpenAI-compatible endpoint (30 requests/minute free tier)              |
| **API Server**        | Agent Kernel's built-in `RESTAPI` (FastAPI under the hood)                                                         |
| **Encryption**        | AES-256-GCM, entirely client-side                                                                                  |

---

## 🚀 Setup Instructions

### Prerequisites

- Python 3.12 – 3.13.x (Agent Kernel's supported range)
- A modern browser (Web Crypto & `crypto.randomUUID` support)
- A Groq API key — free, no card required, at [console.groq.com/keys](https://console.groq.com/keys)

### 1. Clone the fork and enter this use case

```bash
git clone https://github.com/isiri20250974-design/agent-kernel.git
cd agent-kernel/use-cases/isusi-fd-vault
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

---

## ▶️ How to Run the Solution

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
  ✅ isusi_fd_advisor      (fd_advisor)
  ✅ isusi_health_scorer   (health_scorer)
  ✅ isusi_legacy_guardian (legacy_guardian)
  ✅ isusi_triage          (triage)

  🚀 Server running on http://localhost:8000
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

This serves `index.html` **from the same backend**, so the page and the API share one origin and the browser never blocks the AI Agents tab's requests.

> Double-clicking `index.html` directly also works for the FD tracker and vault, but the browser will block calls to the AI Agents tab as cross-origin — always use the URL above once the backend is running.

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

## 📁 Project Structure

```
use-cases/isusi-fd-vault/
├── index.html          # Full frontend app (React via CDN, vault, dashboard, agents)
├── isusi_agent.py      # Agent Kernel backend: triage + 3 specialist OpenAI-SDK agents
├── server.py            # FastAPI server wiring
├── config.yaml           # Agent Kernel config (REST API port)
├── requirements.txt      # agentkernel[openai,api]
├── .env.example           # Template for GROQ_API_KEY
├── logo.png                # ISUSI logo
└── README.md              # This file
```

---

## 🌿 Digital Legacy — Legal Framework

- **Wills Ordinance** — FD holders retain full control over who receives their assets
- **Nominee Law** — a nominated beneficiary receives FD info as a trustee, not as owner
- **PDPA Sri Lanka** — all data stays encrypted on-device and is never sold or shared
- **Finance Business Act No. 42 of 2011 / CBSL Abandoned Property Directions** — FDs and accounts with no activity or correspondence for over 10 years are classified as abandoned property and transferred to a control account at the Central Bank of Sri Lanka. Ownership doesn't transfer to the state, but reclaiming the funds afterward requires the depositor or heir to formally prove identity and ownership to CBSL — a slow, document-heavy process ISUSI's Legacy Guardian is designed to help families avoid entirely.

> ⚠️ ISUSI is an organisational tool only. It does not transfer funds and does not replace a formal Last Will and Testament.

---

## 🇱🇰 About

Built for **IDEALIZE 2026** — organised by AIESEC in University of Moratuwa.

**Founder:** Isiri Masinghe
**University:** IIT — Informatics Institute of Technology, Colombo
**Degree:** BSc Business Data Analytics
**Contact:** isiriwathsala2003@gmail.com
**GitHub:** [@isiri20250974-design](https://github.com/isiri20250974-design)

---

## 📄 License

MIT License — free to use and build upon. Agent Kernel itself is Apache-2.0 licensed by Yaala Labs.

---

<p align="center"><i>ISUSI — Your Money. Your Secret. Your Legacy. 🏦🔒🌿</i></p>
