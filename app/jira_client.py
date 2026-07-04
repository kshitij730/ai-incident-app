import requests
import os
import logging
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "")          # e.g. https://yourcompany.atlassian.net
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "ML")

SEVERITY_TO_PRIORITY = {
    "Critical": "Highest",
    "High": "High",
    "Medium": "Medium",
    "Low": "Low"
}


def is_jira_configured():
    return bool(JIRA_BASE_URL and JIRA_EMAIL and JIRA_API_TOKEN)


def create_jira_ticket(service_name: str, error_log: str, diagnosis: str, severity: str):
    """
    Incident detect hote hi automatically Jira ticket banata hai.
    Real SRE workflow: koi manual ticket banane ki zaroorat nahi.
    """
    if not is_jira_configured():
        logger.warning("Jira not configured, skipping ticket creation")
        return None

    url = f"{JIRA_BASE_URL}/rest/api/3/issue"

    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": f"[AUTO] Incident detected in {service_name} — {severity} severity",
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": f"Error Log:\n{error_log}\n\nAI Diagnosis:\n{diagnosis}"}
                        ]
                    }
                ]
            },
            "issuetype": {"name": "Bug"},
            "priority": {"name": SEVERITY_TO_PRIORITY.get(severity, "Medium")}
        }
    }

    try:
        response = requests.post(
            url,
            json=payload,
            auth=HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN),
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if response.status_code == 201:
            ticket_key = response.json().get("key")
            logger.info(f"Jira ticket created: {ticket_key}")
            return ticket_key
        else:
            logger.error(f"Jira ticket creation failed: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Jira API error: {e}")
        return None
