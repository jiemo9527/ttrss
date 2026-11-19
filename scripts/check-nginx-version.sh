#!/bin/sh
# Verify nginx meets the nginx2root security baseline (1.30.7+ stable, 1.31.9+ mainline/newer).
# Usage: check-nginx-version [version]   (default: version of the installed nginx)
set -eu
v=${1:-$(nginx -v 2>&1 | sed -n 's|.*nginx/\([0-9][0-9.]*\).*|\1|p')}
ge() {
  awk -v a="$1" -v b="$2" 'BEGIN {
    split(a, x, "."); split(b, y, ".")
    for (i = 1; i <= 3; i++) { if (x[i] + 0 > y[i] + 0) exit 0; if (x[i] + 0 < y[i] + 0) exit 1 }
    exit 0 }'
}
case "$v" in
  '') echo 'nginx version not found' >&2; exit 1 ;;
  1.30.*) min=1.30.7 ;;
  *) min=1.31.9 ;;
esac
if ge "$v" "$min"; then
  echo "nginx $v meets security baseline (>= $min)"
else
  echo "nginx $v is below security baseline (need 1.30.7+ or 1.31.9+)" >&2
  exit 1
fi
