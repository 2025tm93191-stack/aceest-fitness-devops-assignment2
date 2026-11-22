#!/usr/bin/env bash
# Send N requests to /<path>/version and count which version / track answered.
# Used to show the canary split, A/B routing and blue-green switch.
#
#   k8s/scripts/traffic.sh <base-url> <path-prefix> [requests] [extra curl args...]
#
#   k8s/scripts/traffic.sh http://192.168.49.2 canary 50
#   k8s/scripts/traffic.sh http://192.168.49.2 ab 20 -H 'X-User-Group: B'
set -euo pipefail

[ $# -ge 2 ] || { echo "usage: $0 <base-url> <path-prefix> [requests] [curl args...]" >&2; exit 1; }
BASE="${1%/}"; PREFIX="$2"; COUNT="${3:-50}"
shift $(( $# >= 3 ? 3 : 2 ))

for _ in $(seq 1 "$COUNT"); do
    curl -fsS --max-time 5 "$@" "$BASE/$PREFIX/version" \
        | sed -E 's/.*"track":"([^"]*)".*"version":"([^"]*)".*/version=\2 track=\1/; s/.*"version":"([^"]*)".*"track":"([^"]*)".*/version=\1 track=\2/' \
        || echo "request failed"
done | sort | uniq -c
