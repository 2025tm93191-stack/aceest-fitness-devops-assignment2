#!/usr/bin/env bash
# Verify a deployment from inside the cluster: /health must be ok and, if given, /version must
# match the expected version on the track that received the new image.
#
#   k8s/scripts/smoke-test.sh <strategy> [expected-version]
#
# Optional: INGRESS_URL=http://<minikube-ip> also checks the public path /<strategy>/health.
# shellcheck source=SCRIPTDIR/lib.sh
source "$(dirname "$0")/lib.sh"

[ $# -ge 1 ] || die "usage: $0 <$STRATEGIES> [expected-version]"
resolve_strategy "$1"
EXPECTED="${2:-}"

log "Smoke test: $STRATEGY in $NS (expected version: ${EXPECTED:-any})"
case "$STRATEGY" in
    rolling)
        http_check aceest http://aceest "$EXPECTED" ;;
    blue-green)
        live="$(kubectl -n "$NS" get service aceest -o jsonpath='{.spec.selector.track}')"
        http_check "aceest-$live" http://aceest "$EXPECTED" ;;
    canary)
        http_check aceest-stable http://aceest-stable
        http_check aceest-canary http://aceest-canary "$EXPECTED" ;;
    ab-testing)
        http_check aceest-a http://aceest-a
        http_check aceest-b http://aceest-b "$EXPECTED" ;;
    shadow)
        http_check aceest-primary http://mirror-proxy        # users go through the mirror proxy
        http_check aceest-primary http://aceest-shadow "$EXPECTED" ;;
esac

if [ -n "${INGRESS_URL:-}" ]; then
    prefix="$STRATEGY"; [ "$STRATEGY" = ab-testing ] && prefix=ab
    log "Public check: ${INGRESS_URL%/}/$prefix/health"
    curl -fsS --max-time 10 "${INGRESS_URL%/}/$prefix/health"; echo
fi
log "Smoke test passed"
