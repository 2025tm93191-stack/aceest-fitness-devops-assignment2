#!/usr/bin/env bash
# Shared helpers for the deploy / smoke-test / rollback / promote scripts.
# Bash 3.2 compatible (macOS default), needs only kubectl and sed.
set -euo pipefail

K8S_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROLLOUT_TIMEOUT="${ROLLOUT_TIMEOUT:-180s}"
STRATEGIES="rolling | blue-green | canary | ab-testing | shadow"

log() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# Normalise the strategy name and set NS (namespace) and DIR (manifest folder).
resolve_strategy() {
    case "${1:-}" in
        rolling)            STRATEGY=rolling;    NS=aceest-rolling ;;
        blue-green|bluegreen) STRATEGY=blue-green; NS=aceest-blue-green ;;
        canary)             STRATEGY=canary;     NS=aceest-canary ;;
        ab|ab-testing)      STRATEGY=ab-testing; NS=aceest-ab ;;
        shadow)             STRATEGY=shadow;     NS=aceest-shadow ;;
        *) die "unknown strategy '${1:-}' (expected: $STRATEGIES)" ;;
    esac
    # shellcheck disable=SC2034  # DIR is used by deploy.sh
    DIR="$K8S_DIR/$STRATEGY"
}

# render FILE KEY=VALUE ... : print FILE with every __KEY__ replaced by VALUE.
render() {
    local file="$1"; shift
    local args=(-e 's|\r$||') kv   # always one expression, so sed never mistakes the file for a script
    for kv in "$@"; do
        args+=(-e "s|__${kv%%=*}__|${kv#*=}|g")
    done
    sed "${args[@]}" "$file"
}

# apply FILE KEY=VALUE ... : render and kubectl apply.
apply() {
    render "$@" | kubectl apply -f -
}

current_image() {  # current_image DEPLOYMENT -> image, or empty if the deployment does not exist
    kubectl -n "$NS" get deployment "$1" -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true
}

wait_rollout() {
    kubectl -n "$NS" rollout status "deployment/$1" --timeout="$ROLLOUT_TIMEOUT"
}

random_hex() {
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
}

# Namespace, config map, volume and the app secret (created once, never overwritten).
ensure_base() {
    log "Base resources in namespace $NS"
    local f
    for f in namespace configmap pvc; do
        apply "$K8S_DIR/base/$f.yaml" NAMESPACE="$NS"
    done
    if ! kubectl -n "$NS" get secret aceest-secrets >/dev/null 2>&1; then
        local admin_password="${ACEEST_ADMIN_PASSWORD:-$(random_hex)}"
        kubectl -n "$NS" create secret generic aceest-secrets \
            --from-literal=ACEEST_SECRET_KEY="$(random_hex)" \
            --from-literal=ACEEST_ADMIN_PASSWORD="$admin_password" >/dev/null
        echo "secret/aceest-secrets created. Admin password:"
        echo "  kubectl -n $NS get secret aceest-secrets -o jsonpath='{.data.ACEEST_ADMIN_PASSWORD}' | base64 -d"
    fi
}

# http_check DEPLOYMENT URL [EXPECTED_VERSION]
# Calls URL/health and URL/version from inside a pod of DEPLOYMENT (no ingress or port-forward
# needed) and fails if the app is unhealthy or reports a different version.
http_check() {
    local deployment="$1" url="$2" expected="${3:-}"
    kubectl -n "$NS" exec -i "deployment/$deployment" -c app -- python - "$url" "$expected" <<'PY'
import json, sys, time, urllib.request

url, expected = sys.argv[1].rstrip("/"), sys.argv[2]
# A Service created a moment ago may not have endpoints yet: retry connection errors for ~30s.
for attempt in range(10):
    try:
        health = json.load(urllib.request.urlopen(url + "/health", timeout=5))
        info = json.load(urllib.request.urlopen(url + "/version", timeout=5))
        break
    except OSError as exc:
        if attempt == 9:
            sys.exit(f"  {url}: unreachable ({exc})")
        time.sleep(3)
print(f"  {url}: status={health['status']} version={info['version']} track={info['track']} pod={info['hostname']}")
if health.get("status") != "ok":
    sys.exit("health check failed")
if expected and info["version"] != expected:
    sys.exit(f"expected version {expected}, got {info['version']}")
PY
}
