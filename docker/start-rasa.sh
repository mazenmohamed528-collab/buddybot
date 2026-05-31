#!/bin/sh
set -eu

ACTION_ENDPOINT_URL="${ACTION_ENDPOINT_URL:-http://actions:5055/webhook}"
ACTION_ENDPOINT_TIMEOUT="${ACTION_ENDPOINT_TIMEOUT:-60}"
RASA_PORT="${PORT:-5005}"
RASA_MODEL_PATH="${RASA_MODEL_PATH:-models/}"

cat > /tmp/endpoints.runtime.yml <<EOF
action_endpoint:
  url: "${ACTION_ENDPOINT_URL}"
  timeout: ${ACTION_ENDPOINT_TIMEOUT}
EOF

exec rasa run \
  --enable-api \
  --cors "*" \
  --port "${RASA_PORT}" \
  --endpoints /tmp/endpoints.runtime.yml \
  --model "${RASA_MODEL_PATH}"
