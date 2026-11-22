#!/usr/bin/env bash
# Make the new version the only version once it has proven itself.
#
#   k8s/scripts/promote.sh <strategy>
#
#   canary / ab-testing / shadow   roll the baseline deployment to the new image, then retire
#                                  the canary / variant B / shadow
#   blue-green                     scale the old colour to 0 (gives up instant rollback)
#   rolling                        nothing to do: a finished rolling update is already promoted
# shellcheck source=SCRIPTDIR/lib.sh
source "$(dirname "$0")/lib.sh"

[ $# -ge 1 ] || die "usage: $0 <$STRATEGIES>"
resolve_strategy "$1"

promote_two_track() {  # promote_two_track BASELINE NEW INGRESS_TO_REMOVE
    local image; image="$(current_image "$2")"
    [ -n "$image" ] || die "deployment/$2 not found in $NS"
    log "Promoting $image to deployment/$1"
    kubectl -n "$NS" set image "deployment/$1" app="$image"
    kubectl -n "$NS" annotate "deployment/$1" kubernetes.io/change-cause="promote $image" --overwrite
    wait_rollout "$1"
    [ -z "$3" ] || kubectl -n "$NS" delete ingress "$3" --ignore-not-found
    kubectl -n "$NS" scale "deployment/$2" --replicas=0
}

case "$STRATEGY" in
    rolling)    echo "Nothing to promote for rolling updates." ;;
    blue-green)
        previous="$(kubectl -n "$NS" get service aceest -o jsonpath='{.metadata.annotations.aceest/previous-color}')"
        [ -n "$previous" ] || die "no previous colour recorded"
        kubectl -n "$NS" scale "deployment/aceest-$previous" --replicas=0 ;;
    canary)     promote_two_track aceest-stable aceest-canary aceest-canary ;;
    ab-testing) promote_two_track aceest-a aceest-b aceest-b ;;
    shadow)     promote_two_track aceest-primary aceest-shadow "" ;;
esac
kubectl -n "$NS" get deployments -o wide
