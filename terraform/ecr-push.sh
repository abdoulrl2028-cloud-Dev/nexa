#!/usr/bin/env bash
# Builda a imagem da API e faz push para o ECR do NEXA.
# Uso: ./ecr-push.sh <registry_id> <region> [tag]
set -euo pipefail

AWS_ACCOUNT="${1:?uso: ./ecr-push.sh <account> <region> [tag]}"
REGION="${2:?uso: ./ecr-push.sh <account> <region> [tag]}"
TAG="${3:-latest}"

REPO="${AWS_ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE="${REPO}/nexa-api:${TAG}"

aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$REPO"

cd "$(dirname "$0")/.."
docker build -f deploy/Dockerfile -t "$IMAGE" .
docker push "$IMAGE"
echo "OK -> $IMAGE"
echo "Defina no Terraform: image = \"$IMAGE\" (ou use o ECR criado pelo próprio Terraform)."