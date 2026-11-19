#!/bin/sh
set -eu
image=${TEST_IMAGE:?TEST_IMAGE is required}
docker pull "$image"
docker run --rm --entrypoint nginx "$image" -v 2>&1 | grep -F 'nginx/1.30.7'
docker run --rm --entrypoint php "$image" -l /var/www/bridge.php
docker run --rm --entrypoint php "$image" /apply-maintenance.php
docker run --rm --entrypoint nginx "$image" -t
# Unauthenticated bridge must fail closed and never contact FlareSolverr.
result=$(docker run --rm --entrypoint php "$image" /var/www/bridge.php)
[ "$result" = Forbidden ]
echo 'maintenance smoke: PASS'
