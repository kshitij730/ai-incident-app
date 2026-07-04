#!/bin/bash
set -e

echo "⏪ Rolling back to previous deployment..."

kubectl rollout undo deployment/aiops-incident-app

echo "⏳ Waiting for rollback to complete..."
kubectl rollout status deployment/aiops-incident-app --timeout=120s

echo "✅ Rollback complete!"
kubectl get pods -l app=aiops-incident-app
