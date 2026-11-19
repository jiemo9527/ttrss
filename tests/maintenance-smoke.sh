#!/bin/sh
set -eu
image=${TEST_IMAGE:?TEST_IMAGE is required}
if [ "${SMOKE_PULL:-0}" = 1 ]; then docker pull "$image"; fi
here=$(dirname "$0")
sh "$here/../scripts/check-nginx-version.sh" \
  "$(docker run --rm --entrypoint nginx "$image" -v 2>&1 | sed -n 's|.*nginx/\([0-9][0-9.]*\).*|\1|p')"
docker run --rm --entrypoint php "$image" -l /var/www/bridge.php
# Source patches: intervals, stale-lock minutes, feed ports (incl. a private port via ALLOW_PORTS)
docker run --rm -i --entrypoint php -e TTRSS_ALLOW_PORTS=80,443,8877 -e TTRSS_UPDATE_LOCK_MINUTES=1 "$image" -- /dev/stdin < "$here/patches-test.php"
docker run --rm --entrypoint nginx "$image" -t
# Enterprise theme ships as selectable files only (light/dark/auto + recoloured widgets).
docker run --rm --entrypoint sh "$image" -c '
  cd /var/www/themes.local &&
  for f in enterprise.css enterprise_night.css enterprise_auto.css enterprise/flat_light.css enterprise/flat_dark.css; do
    test -s "$f" || { echo "missing theme file $f"; exit 1; }
  done &&
  grep -q "enterprise/flat_light.css" enterprise.css &&
  grep -q "prefers-color-scheme: dark" enterprise_auto.css &&
  test -s /var/www/themes/light.css'
# Unauthenticated bridge must fail closed and never contact FlareSolverr.
result=$(docker run --rm --entrypoint php "$image" /var/www/bridge.php)
[ "$result" = Forbidden ]
echo 'maintenance smoke: PASS'
