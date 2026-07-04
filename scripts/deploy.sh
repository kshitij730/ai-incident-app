#!/bin/bash
set -e   # Koi command fail ho toh script turant ruk jaye

echo "🚀 Starting deployment..."

IMAGE_NAME="YOUR_DOCKERHUB_USERNAME/aiops-incident-app"
TAG=$(git rev-parse --short HEAD)

echo "📦 Building Docker image: ${IMAGE_NAME}:${TAG}"
docker build -t "${IMAGE_NAME}:${TAG}" -t "${IMAGE_NAME}:latest" .

echo "☁️ Pushing to DockerHub..."
docker push "${IMAGE_NAME}:${TAG}"
docker push "${IMAGE_NAME}:latest"

echo "🔄 Updating Kubernetes deployment..."
kubectl set image deployment/aiops-incident-app \
  aiops-incident-app="${IMAGE_NAME}:${TAG}" \
  --record

echo "⏳ Waiting for rollout to complete..."
kubectl rollout status deployment/aiops-incident-app --timeout=120s

echo "✅ Deployment successful! Image: ${TAG}"
