from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import logging
import requests
import os

from log_analyzer import init_pinecone, analyze_incident
from jira_client import create_jira_ticket, is_jira_configured

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AIOps Incident Response Assistant",
    description="RAG-powered root cause analysis with ChatOps and Jira integration",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# ─── In-memory SLO tracking (SRE concept) ──────────────────
slo_stats = {
    "total_incidents": 0,
    "critical_incidents": 0,
    "auto_resolved_hint_given": 0
}


class IncidentRequest(BaseModel):
    error_log: str
    service_name: str = "unknown-service"


class IncidentResponse(BaseModel):
    service_name: str
    diagnosis: str
    severity: str
    similar_incidents_found: int
    jira_ticket: str | None
    status: str


@app.on_event("startup")
async def startup():
    try:
        init_pinecone()
    except Exception as e:
        logger.error(f"Pinecone init failed: {e}")


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {"message": "AIOps Incident Assistant running", "docs": "/docs"}


# ─── SRE Observability: SLO/Error Budget Endpoint ──────────
@app.get("/slo-status")
async def slo_status():
    """
    SRE concept: agar 99.9% uptime target hai, ye endpoint
    batata hai kitne incidents aaye aur error budget kitna bacha.
    """
    total = slo_stats["total_incidents"]
    critical = slo_stats["critical_incidents"]
    error_budget_used_pct = round((critical / max(total, 1)) * 100, 2)
    return {
        "total_incidents_analyzed": total,
        "critical_incidents": critical,
        "error_budget_used_percent": error_budget_used_pct,
        "slo_target": "99.9% uptime"
    }


@app.post("/analyze-incident", response_model=IncidentResponse)
async def analyze(request: IncidentRequest):
    if not request.error_log.strip():
        raise HTTPException(status_code=400, detail="Error log empty nahi ho sakta")

    try:
        result = analyze_incident(request.error_log)

        slo_stats["total_incidents"] += 1
        if result["severity"] in ["Critical", "High"]:
            slo_stats["critical_incidents"] += 1

        jira_ticket = None
        if is_jira_configured() and result["severity"] in ["Critical", "High"]:
            jira_ticket = create_jira_ticket(
                request.service_name, request.error_log,
                result["diagnosis"], result["severity"]
            )

        if SLACK_WEBHOOK_URL:
            notify_slack(request.service_name, result["diagnosis"], result["severity"], jira_ticket)

        return IncidentResponse(
            service_name=request.service_name,
            diagnosis=result["diagnosis"],
            severity=result["severity"],
            similar_incidents_found=result["similar_incidents_found"],
            jira_ticket=jira_ticket,
            status="success"
        )

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── ChatOps: Slack Slash Command Endpoint ─────────────────
@app.post("/slack/incident-check")
async def slack_slash_command(request: Request):
    """
    ChatOps endpoint. Slack se '/incident-check <service> <error text>'
    command aayega, ye seedha analysis karke Slack mein reply karega.
    """
    form_data = await request.form()
    text = form_data.get("text", "")
    response_url = form_data.get("response_url", "")

    if not text.strip():
        return {"response_type": "ephemeral", "text": "Usage: /incident-check <service_name> <error_log>"}

    parts = text.split(" ", 1)
    service_name = parts[0] if len(parts) > 0 else "unknown"
    error_log = parts[1] if len(parts) > 1 else text

    # Turant acknowledge karo (Slack 3 sec mein response maangta hai)
    try:
        result = analyze_incident(error_log)
        slack_message = (
            f"*Service:* {service_name}\n"
            f"*Severity:* {result['severity']}\n\n"
            f"*Diagnosis:*\n{result['diagnosis'][:600]}"
        )
        # Async response Slack ko bhejo
        if response_url:
            requests.post(response_url, json={"response_type": "in_channel", "text": slack_message})

        return {"response_type": "ephemeral", "text": "Analyzing... result will appear shortly."}

    except Exception as e:
        return {"response_type": "ephemeral", "text": f"Error: {str(e)}"}


def notify_slack(service_name: str, diagnosis: str, severity: str, jira_ticket: str | None):
    try:
        ticket_line = f"\n📋 Jira Ticket: {jira_ticket}" if jira_ticket else ""
        requests.post(
            SLACK_WEBHOOK_URL,
            json={
                "text": f"🚨 *Incident: {service_name}* | Severity: *{severity}*{ticket_line}\n\n{diagnosis[:500]}"
            },
            timeout=5
        )
    except Exception as e:
        logger.warning(f"Slack notification failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
