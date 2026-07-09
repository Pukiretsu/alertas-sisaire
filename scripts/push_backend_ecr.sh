#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

REGION="${1:-us-east-1}"
ACCOUNT_ID="${2:?Debes enviar el AWS account id}"
REPOSITORY="${3:-air-quality-alerts-prod-backend}"
TAG="${4:-latest}"
IMAGE_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPOSITORY}:${TAG}"

aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
docker build -t "${IMAGE_URI}" "${REPO_ROOT}/backend"
docker push "${IMAGE_URI}"

echo "${IMAGE_URI}"
