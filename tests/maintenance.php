<?php
// Dependency-free regression tests; run with php tests/maintenance.php.
$patch = dirname(__DIR__) . '/src/apply-maintenance.php';
$root = sys_get_temp_dir() . '/ttrss-test-' . bin2hex(random_bytes(5));
mkdir($root . '/classes', 0700, true);
file_put_contents($root . '/classes/RSSUtils.php', "<?php\n\$q = \"last_update_started < NOW() - INTERVAL '10 minute'\";\n");
file_put_contents($root . '/classes/Feeds.php', "<?php\n\$intervals = [\n -1 => __('Disable updates'),\n 15 => __('15 minutes'),\n];\n");
putenv('TTRSS_ROOT=' . $root);
putenv('TTRSS_FAST_REFRESH=true');
putenv('TTRSS_UPDATE_LOCK_MINUTES=1');
function check($condition, $message) { if (!$condition) throw new RuntimeException($message); }
try {
    check(is_file($patch), 'Missing maintenance patch implementation');
    passthru(PHP_BINARY . ' ' . escapeshellarg($patch), $rc);
    check($rc === 0, 'Patch failed');
    $rss = file_get_contents($root . '/classes/RSSUtils.php');
    $feeds = file_get_contents($root . '/classes/Feeds.php');
    check(str_contains($rss, "INTERVAL '1 minute'"), 'Lock interval not reduced');
    foreach ([1,3,5,10] as $n) check(preg_match_all('/^\s*' . $n . '\s*=>/m', $feeds) === 1, "Missing or duplicate interval $n");
    passthru(PHP_BINARY . ' ' . escapeshellarg($patch), $rc);
    check($rc === 0 && file_get_contents($root . '/classes/Feeds.php') === $feeds, 'Not idempotent');
    putenv('TTRSS_UPDATE_LOCK_MINUTES=0');
    exec(PHP_BINARY . ' ' . escapeshellarg($patch) . ' 2>&1', $output, $rc);
    check($rc !== 0, 'Invalid lock accepted');
    check(file_get_contents($root . '/classes/RSSUtils.php') === $rss, 'Invalid config mutated source');
    echo "maintenance: PASS\n";
} finally {
    foreach (glob($root . '/classes/*') as $file) unlink($file);
    rmdir($root . '/classes'); rmdir($root);
}
