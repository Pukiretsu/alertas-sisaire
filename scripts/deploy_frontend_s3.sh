#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BUCKET="${1:?Debes enviar el bucket S3 del frontend}"
DISTRIBUTION_ID="${2:?Debes enviar el ID de CloudFront}"

cd "${REPO_ROOT}/frontend"
npm ci || npm install
npm run build
aws s3 sync dist "s3://${BUCKET}" --delete
aws cloudfront create-invalidation --distribution-id "${DISTRIBUTION_ID}" --paths "/*"
