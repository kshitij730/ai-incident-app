import requests
import os
import logging
from pinecone import Pinecone

logger = logging.getLogger(__name__)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "incident-index")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")

# ─── NAYA: Updated endpoints ────────────────────────────────
HF_ROUTER_URL = "https://router.huggingface.co/v1/chat/completions"
HF_EMBED_URL = "https://router.huggingface.co/hf-inference/models/sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"

pc_client = None
pc_index = None


def init_pinecone():
    global pc_client, pc_index
    pc_client = Pinecone(api_key=PINECONE_API_KEY)
    pc_index = pc_client.Index(PINECONE_INDEX_NAME)
    logger.info("Pinecone connected for incident analysis")


def get_embedding(text: str):
    """Text ko vector mein convert karta hai (naya router endpoint)"""
    response = requests.post(
        HF_EMBED_URL,
        headers={"Authorization": f"Bearer {HF_API_TOKEN}"},
        json={"inputs": text},
        timeout=15
    )
    if response.status_code != 200:
        raise Exception(f"Embedding API failed: {response.text}")
    return response.json()


def retrieve_similar_incidents(error_log: str, top_k: int = 3):
    embedding = get_embedding(error_log)
    results = pc_index.query(vector=embedding, top_k=top_k, include_metadata=True)
    incidents = []
    for match in results.get("matches", []):
        incidents.append({
            "text": match["metadata"].get("text", ""),
            "resolution": match["metadata"].get("resolution", "No prior resolution logged"),
            "similarity_score": round(match["score"], 3)
        })
    return incidents


def call_llm_for_diagnosis(error_log: str, similar_incidents: list):
    """NAYA: OpenAI-compatible chat completion format use karta hai"""
    context = "\n".join(
        [f"- Past Issue: {i['text']} | Resolution: {i['resolution']}" for i in similar_incidents]
    ) or "No similar past incidents found."

    prompt = f"""You are an SRE assistant. Analyze this production error log.

Error Log:
{error_log}

Similar Past Incidents:
{context}

Provide:
1. Likely Root Cause (1-2 lines)
2. Suggested Fix (numbered steps)
3. Severity (Low/Medium/High/Critical)"""

    response = requests.post(
        HF_ROUTER_URL,
        headers={
            "Authorization": f"Bearer {HF_API_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "model": "meta-llama/Meta-Llama-3-8B-Instruct:fastest",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 350,
            "temperature": 0.2
        },
        timeout=40
    )
    if response.status_code != 200:
        raise Exception(f"LLM API failed: {response.text}")

    result = response.json()
    return result["choices"][0]["message"]["content"]


def extract_severity(diagnosis_text: str):
    text_lower = diagnosis_text.lower()
    if "critical" in text_lower:
        return "Critical"
    elif "high" in text_lower:
        return "High"
    elif "medium" in text_lower:
        return "Medium"
    return "Low"


def analyze_incident(error_log: str):
    similar = retrieve_similar_incidents(error_log)
    diagnosis = call_llm_for_diagnosis(error_log, similar)
    severity = extract_severity(diagnosis)
    return {
        "diagnosis": diagnosis,
        "severity": severity,
        "similar_incidents_found": len(similar),
        "similar_incidents": similar
    }
