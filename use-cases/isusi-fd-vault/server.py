import os
import json
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="ISUSI Hybrid AI Backend")

class AgentRequest(BaseModel):
    agent: str

# 1. HARDCODED FIXED DEPOSIT PORTFOLIO (IN LKR)
MY_HARDCODED_FDS = [
    {"id": "FD-8821", "bank": "Commercial Bank", "amount": "LKR 1,500,000", "rate": "8.5%", "maturity": "2026-11-15"},
    {"id": "FD-3042", "bank": "HNB Vault", "amount": "LKR 3,500,000", "rate": "5.2%", "maturity": "2026-08-10"},
    {"id": "FD-7091", "bank": "Sampath Premium", "amount": "LKR 2,000,000", "rate": "7.8%", "maturity": "2027-03-01"}
]

# 2. HARDCODED AGENT RESPONSES
FALLBACK_RESPONSES = {
    "fd_advisor": {
        "summary": "Hybrid Agent Audit: Evaluated 3 Fixed Deposits (LKR 7,000,000 total portfolio value).",
        "recommendations": [
            {
                "id": "FD-8821",
                "bank": "Commercial Bank (LKR 1,500,000)",
                "action": "RENEW",
                "badge_color": "#28a745",
                "reason": "Locked in at peak 8.5% rate. Yield is significantly higher than current market averages."
            },
            {
                "id": "FD-3042",
                "bank": "HNB Vault (LKR 3,500,000)",
                "action": "WITHDRAW",
                "badge_color": "#dc3545",
                "reason": "Matures shortly. Low 5.2% yield. Reallocate funds into higher-yielding term deposits."
            },
            {
                "id": "FD-7091",
                "bank": "Sampath Premium (LKR 2,000,000)",
                "action": "HOLD",
                "badge_color": "#ffc107",
                "reason": "Mid-term maturity with steady 7.8% yield. Maintain active until 2027."
            }
        ]
    },
    "portfolio_health": {
        "overall_grade": "A-",
        "metrics": [
            {"category": "Diversification", "score": "B+", "note": "Spread across 3 major Sri Lankan financial institutions."},
            {"category": "Rate Quality", "score": "A", "note": "Weighted average rate is solid at 7.16%."},
            {"category": "Maturity Laddering", "score": "A-", "note": "Maturities staggered across late 2026 and early 2027."},
            {"category": "Liquidity Buffer", "score": "B", "note": "LKR 3,500,000 maturing within 30 days."},
            {"category": "Legacy Readiness", "score": "A", "note": "Nominees verified on all vaulted accounts."}
        ]
    },
    "legacy_guardian": {
        "status": "VAULT_SECURE",
        "action_required": "SCHEDULE_CHECK_IN",
        "inactivity_timer": "45 Days / 90 Day Limit",
        "nominee_alert_status": "STANDBY",
        "reason": "No owner inactivity detected. Vault status is currently active and secure."
    }
}

@app.post("/run")
async def run_agent(req: AgentRequest):
    agent_key = req.agent.lower()
    groq_api_key = os.getenv("GROQ_API_KEY")

    if groq_api_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key)

            system_prompts = {
                "fd_advisor": f"You are the ISUSI FD Advisor. Review these Sri Lankan Fixed Deposits: {json.dumps(MY_HARDCODED_FDS)}. Recommend RENEW, HOLD, or WITHDRAW for each. Return JSON with keys: summary, recommendations (array of id, bank, action, badge_color, reason). All monetary values must be in LKR.",
                "portfolio_health": f"You are the Portfolio Health agent. Score these FDs: {json.dumps(MY_HARDCODED_FDS)}. Return JSON with keys: overall_grade, metrics (array of category, score, note).",
                "legacy_guardian": "You are Legacy Guardian. Return JSON with keys: status, action_required, inactivity_timer, nominee_alert_status, reason."
            }

            prompt = system_prompts.get(agent_key, system_prompts["fd_advisor"])

            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Analyze the portfolio and output structured JSON."}
                ],
                response_format={"type": "json_object"}
            )
            result_data = json.loads(completion.choices[0].message.content)
        except Exception:
            result_data = FALLBACK_RESPONSES.get(agent_key, FALLBACK_RESPONSES["fd_advisor"])
    else:
        result_data = FALLBACK_RESPONSES.get(agent_key, FALLBACK_RESPONSES["fd_advisor"])

    return {
        "result": result_data,
        "session_id": "sess_isusi_hybrid_101"
    }

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
