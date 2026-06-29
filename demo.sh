#!/usr/bin/env bash
# Provenance Guard — demo runbook
# Run the main flow, then restart the server and run the rate-limit section last.
# Requires: jq, a running server. Adjust PORT if not 5000.

set -e
BASE="http://localhost:${PORT:-5000}"

CLEAR_AI="Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment."
CLEAR_HUMAN="ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably won't go back unless someone drags me there"
FORMAL_HUMAN="The relationship between monetary policy and asset price inflation has been extensively studied in the literature. Central banks face a fundamental tension between their mandate for price stability and the unintended consequences of prolonged low interest rates on equity and real estate valuations."

submit () {  # $1 text, $2 creator_id
  local payload
  payload=$(jq -nc --arg t "$1" --arg c "$2" '{text:$t, creator_id:$c}')
  curl -s -X POST "$BASE/submit" -H "Content-Type: application/json" -d "$payload"
}

echo "=== 1. Submit clearly-AI text (structured response + label) ==="
RESP=$(submit "$CLEAR_AI" demo-ai)
echo "$RESP" | jq .
echo "--- the label a user would see: ---"
echo "$RESP" | jq -r '.label'
echo

echo "=== 2. Submit clearly-human text (confidence difference vs #1) ==="
submit "$CLEAR_HUMAN" demo-human | jq .
echo

echo "=== 3. Submit formal-human text (fairness guard -> Uncertain) ==="
RESP=$(submit "$FORMAL_HUMAN" demo-formal)
echo "$RESP" | jq .
CID=$(echo "$RESP" | jq -r '.content_id')
echo "captured content_id for appeal: $CID"
echo

echo "=== 4. Appeal that result ==="
APPEAL=$(jq -nc --arg id "$CID" --arg r "I wrote this myself. I am a non-native English speaker and my formal style can read as machine-generated." '{content_id:$id, creator_reasoning:$r}')
curl -s -X POST "$BASE/appeal" -H "Content-Type: application/json" -d "$APPEAL" | jq .
echo

echo "=== 5. Audit log (3+ entries; appeal beside original, original intact) ==="
curl -s "$BASE/log" | jq .
echo

echo "=== 6. Analytics dashboard (stretch) ==="
curl -s "$BASE/analytics" | jq .
echo

echo "=== 7. Provenance certificate — request verification ==="
VERIFY=$(jq -nc --arg c "demo-formal" --arg t "$FORMAL_HUMAN" --arg a "I wrote this myself. I am an economist and this is my professional writing style." '{creator_id:$c, sample_text:$t, attestation:$a}')
curl -s -X POST "$BASE/verify" -H "Content-Type: application/json" -d "$VERIFY" | jq .
echo

echo "=== 8. Reviewer approves the verification ==="
REVIEW=$(jq -nc --arg c "demo-formal" '{creator_id:$c, approve:true}')
curl -s -X POST "$BASE/verify/review" -H "Content-Type: application/json" -d "$REVIEW" | jq .
echo

echo "=== 9. Verified creator submits — response includes certificate ==="
submit "$FORMAL_HUMAN" demo-formal | jq '{label_key,label,certificate}'
echo

echo "=== DONE. Now restart the server, then run rate_limit_demo below ==="

# ----------------------------------------------------------------------
# RATE LIMIT — run this AFTER restarting the server (fresh limiter window).
# The audit log persists (SQLite); the in-memory limiter resets on restart,
# so you get a clean 200-run then 429 instead of an early trip.
#
# for i in $(seq 1 12); do
#   curl -s -o /dev/null -w "%{http_code}\n" -X POST "$BASE/submit" \
#     -H "Content-Type: application/json" \
#     -d '{"text":"i went there yesterday. the food was fine but honestly way too expensive for what you actually get in the end.","creator_id":"rl"}'
# done
# ----------------------------------------------------------------------
