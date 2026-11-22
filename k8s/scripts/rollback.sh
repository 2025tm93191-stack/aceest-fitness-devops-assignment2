#!/usr/bin/env bash
# Return a strategy to its last stable state.
#
#   k8s/scripts/rollback.sh <strategy>
#
#   rolling      kubectl rollout undo (previous ReplicaSet revision)
#   blue-green   switch the live Service back to the previous colour (instant, pods still running)
#   canary       remove the canary ingress and scale the canary to 0: 100% back on stable
#   ab-testing   remove the variant-B ingress and scale B to 0: everyone gets variant A
#   shadow       scale the shadow to 0 (users were never served by it)
# shellcheck source=SCRIPTDIR/lib.sh
source "$(dirname "$0")/lib.sh"

[ $# -ge 1 ] || die "usage: $0 <$STRATEGIES>"
resolve_strategy "$1"

log "Rolling back $STRATEGY in $NS"
case "$STRATEGY" in
    rolling)
        kubectl -n "$NS" rollout undo deployment/aceest
        wait_rollout aceest ;;
    blue-green)
        live="$(kubectl -n "$NS" get service aceest -o jsonpath='{.spec.selector.track}')"
        previous="$(kubectl -n "$NS" get service aceest -o jsonpath='{.metadata.annotations.aceest/previous-color}')"
        [ -n "$previous" ] || die "no previous colour recorded on service/aceest: nothing to roll back to"
        kubectl -n "$NS" scale "deployment/aceest-$previous" --replicas=2
        wait_rollout "aceest-$previous"
        kubectl -n "$NS" patch service aceest --type merge \
            -p "{\"spec\":{\"selector\":{\"app\":\"aceest\",\"track\":\"$previous\"}}}"
        kubectl -n "$NS" annotate service aceest aceest/previous-color="$live" --overwrite
        echo "Live traffic switched back $live -> $previous" ;;
    canary)
        kubectl -n "$NS" delete ingress aceest-canary --ignore-not-found
        kubectl -n "$NS" scale deployment/aceest-canary --replicas=0 ;;
    ab-testing)
        kubectl -n "$NS" delete ingress aceest-b --ignore-not-found
        kubectl -n "$NS" scale deployment/aceest-b --replicas=0 ;;
    shadow)
        kubectl -n "$NS" scale deployment/aceest-shadow --replicas=0 ;;
esac
kubectl -n "$NS" get deployments -o wide
