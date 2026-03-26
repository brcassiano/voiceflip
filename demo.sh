#!/bin/bash
# =============================================================================
# VoiceFlip Pipeline — Demo Script
# Runs all scenarios automatically and displays formatted results.
# Created outside the test scope to facilitate demonstrations.
#
# Usage: with the server running (uvicorn app.main:app --reload), run:
#   chmod +x demo.sh && ./demo.sh
# =============================================================================

BASE_URL="http://127.0.0.1:8000"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

divider() {
  echo ""
  echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
  echo -e "${BOLD}  $1${NC}"
  echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
  echo ""
}

extract_id() {
  python3 -c "import sys,json; print(json.load(sys.stdin)['request_id'])"
}

show_result() {
  local id=$1
  local response
  response=$(curl -s "$BASE_URL/requests/$id")

  local status=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  local degraded=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['degraded'])")
  local reason=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['degradation_reason'] or '-')")
  local p_success=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['primary_result']['success'] if d['primary_result'] else 'N/A')")
  local p_attempts=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['primary_result']['attempts']) if d['primary_result'] else 0)")
  local o_success=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['optional_result']['success'] if d['optional_result'] else 'N/A')")
  local o_attempts=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['optional_result']['attempts']) if d['optional_result'] else 0)")

  if [ "$status" = "completed" ] && [ "$degraded" = "False" ]; then
    echo -e "  Status:       ${GREEN}$status${NC}"
  elif [ "$status" = "completed" ] && [ "$degraded" = "True" ]; then
    echo -e "  Status:       ${YELLOW}$status (DEGRADED)${NC}"
  else
    echo -e "  Status:       ${RED}$status${NC}"
  fi

  echo -e "  Degraded:     $degraded"
  echo -e "  Reason:       $reason"
  echo -e "  Primary:      success=$p_success  attempts=$p_attempts"
  echo -e "  Optional:     success=$o_success  attempts=$o_attempts"

  echo ""
  echo -e "  ${BOLD}Full JSON:${NC}"
  echo "$response" | python3 -m json.tool | sed 's/^/  /'
}

# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${CYAN}  VoiceFlip Resilient Processing Pipeline — Demo${NC}"
echo -e "  $(date)"
echo ""

# 1. OK
divider "1/5  Scenario: OK (happy path)"
echo -e "  Sending request..."
ID_OK=$(curl -s -X POST "$BASE_URL/requests" -H "Content-Type: application/json" -d '{"payload": {"scenario": "ok"}}' | extract_id)
echo -e "  Request ID: ${BOLD}$ID_OK${NC}"
echo -e "  Waiting for processing..."
sleep 1
show_result "$ID_OK"

# 2. TRANSIENT FAIL THEN OK (both recover)
divider "2/5  Scenario: TRANSIENT_FAIL_THEN_OK (fail_times=2, both recover)"
echo -e "  Sending request..."
ID_TRANSIENT=$(curl -s -X POST "$BASE_URL/requests" -H "Content-Type: application/json" -d '{"payload": {"scenario": "transient_fail_then_ok", "fail_times": 2}}' | extract_id)
echo -e "  Request ID: ${BOLD}$ID_TRANSIENT${NC}"
echo -e "  Waiting for retries + processing..."
sleep 4
show_result "$ID_TRANSIENT"

# 3. DEGRADED MODE (primary recovers, optional exhausts retries)
divider "3/5  Scenario: DEGRADED MODE (fail_times=3, optional exhausts retries)"
echo -e "  Sending request..."
ID_DEGRADED=$(curl -s -X POST "$BASE_URL/requests" -H "Content-Type: application/json" -d '{"payload": {"scenario": "transient_fail_then_ok", "fail_times": 3}}' | extract_id)
echo -e "  Request ID: ${BOLD}$ID_DEGRADED${NC}"
echo -e "  Waiting for retries + processing (may take ~8s)..."
sleep 10
show_result "$ID_DEGRADED"

# 4. TIMEOUT
divider "4/5  Scenario: TIMEOUT (both handlers exceed deadline)"
echo -e "  Sending request..."
ID_TIMEOUT=$(curl -s -X POST "$BASE_URL/requests" -H "Content-Type: application/json" -d '{"payload": {"scenario": "timeout"}}' | extract_id)
echo -e "  Request ID: ${BOLD}$ID_TIMEOUT${NC}"
echo -e "  Waiting for processing..."
sleep 1
show_result "$ID_TIMEOUT"

# 5. HARD FAIL
divider "5/5  Scenario: HARD_FAIL (non-retryable error, no retry)"
echo -e "  Sending request..."
ID_HARD=$(curl -s -X POST "$BASE_URL/requests" -H "Content-Type: application/json" -d '{"payload": {"scenario": "hard_fail"}}' | extract_id)
echo -e "  Request ID: ${BOLD}$ID_HARD${NC}"
echo -e "  Waiting for processing..."
sleep 1
show_result "$ID_HARD"

# HEALTH
divider "HEALTH — Metrics after all scenarios"
echo -e "  ${BOLD}GET /health:${NC}"
echo ""
curl -s "$BASE_URL/health" | python3 -m json.tool | sed 's/^/  /'

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  Demo complete! 5 scenarios executed.${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
