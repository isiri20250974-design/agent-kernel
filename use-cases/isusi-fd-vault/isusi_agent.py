"""
ISUSI — AI Agent Backend
=========================

Built on Yaala Labs' Agent Kernel (https://github.com/yaalalabs/agent-kernel,
PyPI: `agentkernel`), running the OpenAI Agents SDK with Groq's Llama 3.3 70B
plugged in as the model (via Groq's OpenAI-compatible endpoint). Groq's free
tier has a much higher requests-per-minute limit than most alternatives,
which matters a lot for interactive testing/demoing.

Four agents, wired exactly the way Agent Kernel expects:
  - triage           routes the request to the right specialist (OpenAI SDK handoff)
  - fd_advisor        RENEW / HOLD / WITHDRAW advice per FD
  - health_scorer      scores the portfolio A-F across 5 dimensions
  - legacy_guardian    decides whether to check in on / alert the beneficiary

Each specialist is a plain `agents.Agent` with a small tool (a plain Python
function decorated with the OpenAI Agents SDK's `@function_tool`) that
computes exact numbers — maturity dates, amounts, portfolio stats — so the
LLM only has to reason over already-correct data, never do the arithmetic
itself.

Agent Kernel's `OpenAIModule` registers the agents with the Runtime, and
`RESTAPI.run()` exposes them over HTTP with zero extra code. The real,
installed endpoints (confirmed via the auto-generated docs at
http://localhost:8000/docs — the actual package's routes differ from what
the hosted docs site describes) are:
  POST /run                {"agent": "fd_advisor", "prompt": "...", "session_id": "..."}
                            → returns the agent's raw text response as a
                              plain JSON string (NOT wrapped in an object)
  GET  /agents
  GET  /health

This same server also serves the frontend (index.html) from a same-origin
custom route at GET /custom/app, so the browser never blocks the AI Agents
tab's requests as cross-origin.

Setup:
    pip install "agentkernel[openai,api]"
    export GROQ_API_KEY="..."
    python isusi_agent.py
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime

from agents import Agent as OpenAIAgent
from agents import OpenAIChatCompletionsModel, function_tool, set_tracing_disabled
from fastapi import APIRouter
from fastapi.responses import FileResponse
from openai import AsyncOpenAI

from agentkernel.api import RESTAPI
from agentkernel.openai import OpenAIModule

# ---------------------------------------------------------------------------
# Groq, plugged into the OpenAI Agents SDK via Groq's OpenAI-compatible
# endpoint. Agent Kernel is framework-agnostic about the *agent* framework
# (OpenAI Agents SDK here) but the *model* underneath is entirely swappable —
# this is the officially documented way to point the OpenAI Agents SDK at
# Groq instead of OpenAI's own models. Groq's free tier has a much higher
# requests-per-minute limit than Gemini's, which is why we're using it here.
# ---------------------------------------------------------------------------

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is not set. Get a free key at https://console.groq.com/keys "
        "and run: export GROQ_API_KEY=your_key_here"
    )

set_tracing_disabled(True)  # we're not using OpenAI's own trace backend

_groq_client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)
LLM_MODEL = OpenAIChatCompletionsModel(
    model="llama-3.3-70b-versatile",
    openai_client=_groq_client,
)


# ---------------------------------------------------------------------------
# Tools — plain Python functions decorated with @function_tool (the OpenAI
# Agents SDK's own mechanism). These do all the exact math; the agents only
# reason over the result.
# ---------------------------------------------------------------------------

def _days_until(iso_date: str) -> int:
    try:
        target = datetime.fromisoformat(iso_date).date()
    except ValueError:
        target = date.today()
    return (target - date.today()).days


def _maturity_amount(principal: float, rate: float, term_months: float) -> float:
    return round(float(principal) * (1 + (float(rate) / 100) * (float(term_months) / 12)), 2)


@function_tool
def get_fd_metrics(fds_json: str) -> str:
    """Given a JSON array of fixed deposits (each with bank, principal, rate,
    termMonths, maturityDate, and optionally nominee), returns the same list
    with two fields added to every FD: days_to_maturity and maturity_amount."""
    fds = json.loads(fds_json)
    enriched = []
    for fd in fds:
        enriched.append({
            **fd,
            "days_to_maturity": _days_until(fd.get("maturityDate", "")),
            "maturity_amount": _maturity_amount(
                fd.get("principal", 0), fd.get("rate", 0), fd.get("termMonths", 12)
            ),
        })
    return json.dumps(enriched)


@function_tool
def compute_portfolio_stats(fds_json: str) -> str:
    """Given a JSON array of fixed deposits, returns raw portfolio statistics:
    distinct_banks, average_rate, distinct_maturity_months, short_term_count
    (FDs with termMonths <= 12), total_fds, and fds_with_nominee."""
    fds = json.loads(fds_json)
    if not fds:
        return json.dumps({"empty": True, "total_fds": 0})
    banks = len({fd.get("bank") for fd in fds})
    avg_rate = sum(float(fd.get("rate", 0)) for fd in fds) / len(fds)
    months = len({_days_until(fd.get("maturityDate", "")) // 30 for fd in fds})
    short_term = sum(1 for fd in fds if float(fd.get("termMonths", 12)) <= 12)
    with_nominee = sum(1 for fd in fds if fd.get("nominee"))
    return json.dumps({
        "distinct_banks": banks,
        "average_rate": round(avg_rate, 2),
        "distinct_maturity_months": months,
        "short_term_count": short_term,
        "total_fds": len(fds),
        "fds_with_nominee": with_nominee,
    })


@function_tool
def get_inactivity_status(
    inactive_days: int,
    checkin_threshold_days: int,
    alert_threshold_days: int,
    checkin_already_sent: bool,
) -> str:
    """Given Digital Legacy dead-man's-switch inputs, returns whether the
    check-in and alert thresholds have been crossed, for the agent to reason
    over conservatively."""
    return json.dumps({
        "inactive_days": inactive_days,
        "checkin_threshold_days": checkin_threshold_days,
        "alert_threshold_days": alert_threshold_days,
        "checkin_already_sent": checkin_already_sent,
        "checkin_threshold_crossed": inactive_days >= checkin_threshold_days,
        "alert_threshold_crossed": inactive_days >= alert_threshold_days,
    })


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

fd_advisor_agent = OpenAIAgent(
    name="fd_advisor",
    handoff_description="Analyses fixed deposits and recommends RENEW, HOLD, or WITHDRAW for each.",
    instructions=(
        "You are isusi_fd_advisor, a cautious Sri Lankan fixed-deposit advisor.\n"
        "The prompt you receive IS a JSON array of fixed deposits — pass it through "
        "exactly as-is as the fds_json argument, do not wrap, reformat, or re-nest it.\n"
        "1. Call get_fd_metrics with that FD list to get accurate days-to-maturity and "
        "maturity amounts — never compute these yourself.\n"
        "2. For EACH fixed deposit, decide RENEW, HOLD, or WITHDRAW and give one short "
        "reasoning sentence. Consider days to maturity and whether the rate is competitive "
        "(~10-11% p.a. is a fair 2026 LKR benchmark).\n"
        "3. Also give one short 'weekly_action' sentence summarising what to do this week "
        "across the whole portfolio.\n"
        "Reply with ONLY raw JSON, no markdown fences, no commentary: "
        '{"advice": [{"id": "...", "action": "RENEW|HOLD|WITHDRAW", "reasoning": "..."}], '
        '"weekly_action": "..."}'
    ),
    tools=[get_fd_metrics],
    model=LLM_MODEL,
)

health_scorer_agent = OpenAIAgent(
    name="health_scorer",
    handoff_description="Scores an FD portfolio A-F across diversification, rate quality, "
    "maturity spread, liquidity, and legacy readiness.",
    instructions=(
        "You are isusi_health_scorer.\n"
        "The prompt you receive IS a JSON array of fixed deposits — pass it through "
        "exactly as-is as the fds_json argument, do not wrap, reformat, or re-nest it.\n"
        "1. Call compute_portfolio_stats with that FD list to get accurate raw "
        "statistics — never compute these yourself.\n"
        "2. Turn those raw stats into a 0-100 score for exactly 5 dimensions: "
        "'diversification' (spread across banks), 'rate_quality' (average rate vs the "
        "~10-11% market benchmark), 'maturity_spread' (are maturities staggered, avoiding a "
        "single cliff-edge), 'liquidity_buffer' (mix of short vs long terms), and "
        "'legacy_readiness' (fraction of FDs with a nominee set).\n"
        "3. Compute an overall 0-100 score as their average, map it to a letter grade "
        "(A>=90, B>=80, C>=70, D>=60, else F), and give one short sentence per dimension.\n"
        "Reply with ONLY raw JSON, no markdown fences, no commentary: "
        '{"dimensions": {"diversification": {"score": N, "note": "..."}, "rate_quality": '
        '{...}, "maturity_spread": {...}, "liquidity_buffer": {...}, "legacy_readiness": '
        '{...}}, "overall_score": N, "grade": "A-F"}'
    ),
    tools=[compute_portfolio_stats],
    model=LLM_MODEL,
)

legacy_guardian_agent = OpenAIAgent(
    name="legacy_guardian",
    handoff_description="Decides whether to check in on, or alert the nominated beneficiary "
    "about, an inactive FD owner.",
    instructions=(
        "You are isusi_legacy_guardian, part of a Dead Man's Switch for a fixed-deposit "
        "legacy app.\n"
        "1. Call get_inactivity_status with the inputs you were given to see whether the "
        "check-in and alert thresholds have been crossed — never compute this yourself.\n"
        "2. Decide ONE action: 'NONE' (do nothing yet), 'SEND_CHECKIN' (ask the owner to "
        "confirm they're okay), or 'ALERT_BENEFICIARY' (share the encrypted FD summary with "
        "the nominee). Be conservative: never choose ALERT_BENEFICIARY unless a check-in was "
        "already sent AND the alert threshold was crossed.\n"
        "Reply with ONLY raw JSON, no markdown fences, no commentary: "
        '{"decision": "NONE|SEND_CHECKIN|ALERT_BENEFICIARY", "confidence": "LOW|MEDIUM|HIGH", '
        '"reasoning": "..."}'
    ),
    tools=[get_inactivity_status],
    model=LLM_MODEL,
)

triage_agent = OpenAIAgent(
    name="triage",
    instructions=(
        "You determine which specialist agent should handle the user's request: "
        "fd_advisor for RENEW/HOLD/WITHDRAW advice on fixed deposits, health_scorer for "
        "portfolio health scoring, legacy_guardian for Digital Legacy / beneficiary "
        "check-in decisions. Hand off immediately — do not answer directly yourself."
    ),
    handoffs=[fd_advisor_agent, health_scorer_agent, legacy_guardian_agent],
    model=LLM_MODEL,
)

# Registers all four agents with the Agent Kernel Runtime.
OpenAIModule([triage_agent, fd_advisor_agent, health_scorer_agent, legacy_guardian_agent])


# ---------------------------------------------------------------------------
# Serve index.html from the SAME origin as the API (Agent Kernel's documented
# "Custom Routes" pattern: https://kernel.yaala.ai/docs/api/rest-api#custom-routes).
# This matters: if you instead open index.html by double-clicking it, the page
# runs on the file:// origin and the browser blocks its fetch() calls to
# http://localhost:8000 as cross-origin. Serving it from this same backend
# means both the page and the API are on http://localhost:8000, so no
# cross-origin request ever happens.
# ---------------------------------------------------------------------------

_frontend_router = APIRouter()
_INDEX_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")


@_frontend_router.get("/app")
async def serve_frontend():
    return FileResponse(_INDEX_HTML_PATH, media_type="text/html")


RESTAPI.add(router=_frontend_router)


if __name__ == "__main__":
    print("=" * 44)
    print("  🏦 ISUSI — AI Agent Backend")
    print("  Powered by Yaala Labs Agent Kernel")
    print("=" * 44)
    print()
    print("  Agents ready:")
    print("  ✅ isusi_fd_advisor      (fd_advisor)")
    print("  ✅ isusi_health_scorer   (health_scorer)")
    print("  ✅ isusi_legacy_guardian (legacy_guardian)")
    print("  ✅ isusi_triage          (triage)")
    print()
    print("  🚀 Open the app at:      http://localhost:8000/custom/app")
    print("     API running on:       http://localhost:8000")
    RESTAPI.run()
