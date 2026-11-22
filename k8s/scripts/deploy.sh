#!/usr/bin/env bash
# Deploy a new image of ACEest with one of the five strategies.
#
#   k8s/scripts/deploy.sh <strategy> <new-image> [baseline-image]
#
#   strategy        rolling | blue-green | canary | ab-testing | shadow
#   new-image       e.g. docker.io/<user>/aceest-fitness:2.0.0
#   baseline-image  only used the first time canary / ab-testing / shadow is deployed: the
#                   "current" version that keeps most of the traffic (default: new-image)
#
# Environment: CANARY_WEIGHT (default 20), ROLLOUT_TIMEOUT (default 180s),
#              ACEEST_ADMIN_PASSWORD (admin password for a new namespace; random if unset).
#
# Each strategy lives in its own namespace (aceest-<strategy>) and is served by the NGINX
# ingress under /<strategy>/, so all five can run side by side on one cluster.
# shellcheck source=SCRIPTDIR/lib.sh
source "$(dirname "$0")/lib.sh"

[ $# -ge 2 ] || die "usage: $0 <$STRATEGIES> <new-image> [baseline-image]"
resolve_strategy "$1"
NEW_IMAGE="$2"
BASELINE_IMAGE="${3:-$NEW_IMAGE}"
CANARY_WEIGHT="${CANARY_WEIGHT:-20}"

ensure_base

deploy_rolling() {
    local current; current="$(current_image aceest)"
    # Apply with the running image so the manifest is in sync, then change the image:
    # the RollingUpdate strategy (maxSurge 1, maxUnavailable 0) replaces pods one by one.
    apply "$DIR/deployment.yaml" IMAGE="${current:-$NEW_IMAGE}"
    apply "$DIR/service.yaml"
    apply "$DIR/ingress.yaml"
    if [ -n "$current" ] && [ "$current" != "$NEW_IMAGE" ]; then
        log "Rolling update $current -> $NEW_IMAGE"
        kubectl -n "$NS" set image deployment/aceest app="$NEW_IMAGE"
    fi
    kubectl -n "$NS" annotate deployment/aceest kubernetes.io/change-cause="deploy $NEW_IMAGE" --overwrite
    wait_rollout aceest
}

deploy_blue_green() {
    local live idle blue_image green_image blue_replicas=2 green_replicas=2
    live="$(kubectl -n "$NS" get service aceest -o jsonpath='{.spec.selector.track}' 2>/dev/null || true)"
    blue_image="$(current_image aceest-blue)"
    green_image="$(current_image aceest-green)"
    if [ -z "$live" ]; then
        idle=blue                  # first deployment: blue becomes live, green stays empty
        green_replicas=0
        green_image="${green_image:-$NEW_IMAGE}"
    elif [ "$live" = blue ]; then
        idle=green
    else
        idle=blue
    fi
    if [ "$idle" = blue ]; then blue_image="$NEW_IMAGE"; else green_image="$NEW_IMAGE"; fi
    log "Blue-green: live=${live:-none}, deploying $NEW_IMAGE to $idle"

    apply "$DIR/deployment-blue.yaml" IMAGE_BLUE="$blue_image" REPLICAS_BLUE="$blue_replicas"
    apply "$DIR/deployment-green.yaml" IMAGE_GREEN="$green_image" REPLICAS_GREEN="$green_replicas"
    apply "$DIR/service-blue-preview.yaml"
    apply "$DIR/service-green-preview.yaml"
    wait_rollout "aceest-$idle"

    log "Smoke test on the idle colour ($idle) before switching traffic"
    http_check "aceest-$idle" "http://aceest-$idle" "${EXPECTED_VERSION:-}"

    if [ -z "$live" ]; then
        apply "$DIR/service.yaml" LIVE_COLOR="$idle"
    else
        log "Switching live traffic $live -> $idle"
        kubectl -n "$NS" patch service aceest --type merge \
            -p "{\"spec\":{\"selector\":{\"app\":\"aceest\",\"track\":\"$idle\"}}}"
        kubectl -n "$NS" annotate service aceest aceest/previous-color="$live" --overwrite
    fi
    apply "$DIR/ingress.yaml"
}

# Shared by canary, A/B and shadow: a baseline deployment that keeps serving users and a
# second deployment with the new image that gets a slice / a segment / a copy of the traffic.
deploy_two_track() {
    local base_name="$1" base_file="$2" base_key="$3" new_name="$4" new_file="$5" new_key="$6"
    local base_image; base_image="$(current_image "$base_name")"
    base_image="${base_image:-$BASELINE_IMAGE}"
    log "$STRATEGY: baseline $base_image, new $NEW_IMAGE"
    apply "$DIR/$base_file" "$base_key=$base_image"
    apply "$DIR/$new_file" "$new_key=$NEW_IMAGE"   # also restores replicas after a rollback
    wait_rollout "$base_name"
    wait_rollout "$new_name"
}

case "$STRATEGY" in
    rolling)
        deploy_rolling ;;
    blue-green)
        deploy_blue_green ;;
    canary)
        deploy_two_track aceest-stable deployment-stable.yaml IMAGE_STABLE aceest-canary deployment-canary.yaml IMAGE_CANARY
        apply "$DIR/service-stable.yaml"
        apply "$DIR/service-canary.yaml"
        apply "$DIR/ingress-stable.yaml"     # the main ingress must exist before the canary one
        apply "$DIR/ingress-canary.yaml" CANARY_WEIGHT="$CANARY_WEIGHT"
        log "Canary live: ${CANARY_WEIGHT}% of /canary traffic goes to $NEW_IMAGE" ;;
    ab-testing)
        deploy_two_track aceest-a deployment-a.yaml IMAGE_A aceest-b deployment-b.yaml IMAGE_B
        apply "$DIR/service-a.yaml"
        apply "$DIR/service-b.yaml"
        apply "$DIR/ingress-a.yaml"
        apply "$DIR/ingress-b.yaml"
        log "A/B live: requests with 'X-User-Group: B' (or cookie ab_group=always) get variant B" ;;
    shadow)
        deploy_two_track aceest-primary deployment-primary.yaml IMAGE_PRIMARY aceest-shadow deployment-shadow.yaml IMAGE_SHADOW
        apply "$DIR/service-primary.yaml"
        apply "$DIR/service-shadow.yaml"
        apply "$DIR/mirror-proxy.yaml"
        wait_rollout mirror-proxy
        apply "$DIR/ingress.yaml"
        log "Shadow live: users are served by the primary; every request is mirrored to $NEW_IMAGE" ;;
esac

log "Deployed $NEW_IMAGE with strategy $STRATEGY in namespace $NS"
kubectl -n "$NS" get deployments,services,ingress -o wide
