#!/usr/bin/env bash
# Print what is running for every strategy (evidence for the report).
#
#   k8s/scripts/status.sh            all strategies
#   k8s/scripts/status.sh canary     one strategy
# shellcheck source=SCRIPTDIR/lib.sh
source "$(dirname "$0")/lib.sh"

for s in ${1:-rolling blue-green canary ab-testing shadow}; do
    resolve_strategy "$s"
    log "$STRATEGY ($NS)"
    if ! kubectl get namespace "$NS" >/dev/null 2>&1; then
        echo "  not deployed"
        continue
    fi
    kubectl -n "$NS" get deployments -o custom-columns='DEPLOYMENT:.metadata.name,READY:.status.readyReplicas,WANTED:.spec.replicas,IMAGE:.spec.template.spec.containers[0].image'
    kubectl -n "$NS" get ingress -o custom-columns='INGRESS:.metadata.name,PATH:.spec.rules[0].http.paths[0].path,BACKEND:.spec.rules[0].http.paths[0].backend.service.name,CANARY-WEIGHT:.metadata.annotations.nginx\.ingress\.kubernetes\.io/canary-weight,CANARY-HEADER:.metadata.annotations.nginx\.ingress\.kubernetes\.io/canary-by-header'
    if [ "$STRATEGY" = blue-green ]; then
        echo "live colour: $(kubectl -n "$NS" get service aceest -o jsonpath='{.spec.selector.track}' 2>/dev/null)"
    fi
done
