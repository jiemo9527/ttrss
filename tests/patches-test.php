<?php
// Verifies patches/*.patch inside a built image (run by tests/maintenance-smoke.sh).
chdir('/var/www');
set_include_path('/var/www/include' . PATH_SEPARATOR . get_include_path());
require_once 'autoload.php';
require_once 'functions.php';
$fail = 0;
function ok($c, $m) { global $fail; echo ($c ? "ok   " : "FAIL ") . "$m\n"; if (!$c) $fail++; }
ok(UrlHelper::validate('http://1.1.1.1/rss', true) !== false, 'http feed on public host');
ok(UrlHelper::validate('http://1.1.1.1:8080/rss', true) !== false, 'public host, non-standard port 8080');
ok(UrlHelper::validate('https://1.1.1.1:8443/rss', true) !== false, 'public host, https non-standard port 8443');
ok(UrlHelper::validate('http://127.0.0.1/rss', true) === false, 'loopback still blocked');
ok(UrlHelper::validate('http://169.254.169.254/latest/meta-data', true) === false, 'link-local/metadata still blocked');
ok(UrlHelper::validate('http://10.0.0.5/rss', true) !== false, 'private host on port 80 allowed');
$allowed = in_array(8877, UrlHelper::private_ports(), true);
ok(UrlHelper::validate('http://10.0.0.5:8877/rss', true) === ($allowed ? 'http://10.0.0.5:8877/rss' : false), 'private host on 8877 follows ALLOW_PORTS (' . ($allowed ? 'listed' : 'not listed') . ')');
ok(UrlHelper::validate('http://10.0.0.5:9999/rss', true) === false || in_array(9999, UrlHelper::private_ports(), true), 'private host on unlisted port blocked');
$iv = Feeds::_get_update_intervals();
foreach ([1, 3, 5, 10] as $n) ok(isset($iv[$n]), "update interval option $n min");
ok(array_keys($iv) === [-1, 0, 1, 3, 5, 10, 15, 30, 60, 240, 720, 1440, 10080], 'interval order');
$lock = (int) Config::get(Config::UPDATE_LOCK_MINUTES);
ok($lock >= 1 && $lock <= 10, "update lock minutes = $lock");
ok(str_contains(file_get_contents('classes/RSSUtils.php'), "INTERVAL '\$lock_minutes minute'"), 'stale-lock query uses UPDATE_LOCK_MINUTES');
echo $fail ? "patches: FAIL ($fail)\n" : "patches: PASS\n";
exit($fail ? 1 : 0);
