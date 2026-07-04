#!/bin/bash
# Cron job ya manual run ke liye — app health check karta hai

API_URL="${1:-http://localhost:8000}"
MAX_RETRIES=5
RETRY_COUNT=0

echo "🏥 Checking health of ${API_URL}..."

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}/health")

    if [ "$HTTP_STATUS" -eq 200 ]; then
        echo "✅ Service is healthy (HTTP $HTTP_STATUS)"
        exit 0
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "⚠️  Attempt $RETRY_COUNT/$MAX_RETRIES failed (HTTP $HTTP_STATUS), retrying in 5s..."
    sleep 5
done

echo "❌ Service is unhealthy after $MAX_RETRIES attempts!"
exit 1
