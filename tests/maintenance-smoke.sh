#!/bin/sh
set -eu
image=${TEST_IMAGE:?TEST_IMAGE is required}
if [ "${SMOKE_PULL:-0}" = 1 ]; then docker pull "$image"; fi
here=$(dirname "$0")
sh "$here/../scripts/check-nginx-version.sh" \
  "$(docker run --rm --entrypoint nginx "$image" -v 2>&1 | sed -n 's|.*nginx/\([0-9][0-9.]*\).*|\1|p')"
docker run --rm --entrypoint php "$image" -l /var/www/bridge.php
docker run --rm --entrypoint php "$image" /apply-maintenance.php
docker run --rm --entrypoint nginx "$image" -t
# Unauthenticated bridge must fail closed and never contact FlareSolverr.
result=$(docker run --rm --entrypoint php "$image" /var/www/bridge.php)
[ "$result" = Forbidden ]
echo 'maintenance smoke: PASS'
