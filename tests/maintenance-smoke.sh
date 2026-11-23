#!/bin/sh
set -eu
image=${TEST_IMAGE:?TEST_IMAGE is required}
if [ "${SMOKE_PULL:-0}" = 1 ]; then docker pull "$image"; fi
here=$(dirname "$0")
sh "$here/../scripts/check-nginx-version.sh" \
  "$(docker run --rm --entrypoint nginx "$image" -v 2>&1 | sed -n 's|.*nginx/\([0-9][0-9.]*\).*|\1|p')"
# 核对 PHP 分支、补丁版本与扩展，防止切换包名后 CLI/FPM 或 OPcache 漏装。
docker run --rm --entrypoint php "$image" -r '
  if (PHP_VERSION !== "8.3.37" || !extension_loaded("Zend OPcache") || !extension_loaded("pdo_pgsql") || !extension_loaded("imagick")) exit(1);
  echo "PHP runtime: ", PHP_VERSION, " PASS\n";'
docker run --rm --entrypoint sh "$image" -c 'php-fpm83 -v | grep -F "PHP 8.3.37" && php-fpm83 -t'
docker run --rm --entrypoint php "$image" -l /var/www/bridge.php
# Source patches: intervals, stale-lock minutes, feed ports (incl. a private port via ALLOW_PORTS)
docker run --rm -i --entrypoint php -e TTRSS_ALLOW_PORTS=80,443,8877 -e TTRSS_UPDATE_LOCK_MINUTES=1 "$image" -- /dev/stdin < "$here/patches-test.php"
docker run --rm --entrypoint nginx "$image" -t
# 镜像默认的中断更新重试时间为 3 分钟（上游固定 10）。
docker run --rm --entrypoint sh "$image" -c 'test "$UPDATE_LOCK_MINUTES" = 3'
# 固定提交的插件与第三方主题已解压到位。
docker run --rm --entrypoint sh "$image" -c '
  for f in /var/www/plugins/fever/init.php /var/www/plugins.local/api_newsplus/init.php \
    /var/www/plugins.local/wallabag_v2/init.php /var/www/plugins.local/api_feedreader/init.php \
    /var/www/plugins.local/auth_oidc/init.php /var/www/plugins.local/freshapi/init.php \
    /var/www/themes.local/feedly.css /var/www/themes.local/rsshub.css /var/www/themes.local/feedlish.css; do
    test -s "$f" || { echo "missing $f"; exit 1; }
  done
  test -d /var/www/themes.local/feedly/fonts'
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
