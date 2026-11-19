<?php
// Apply narrowly-scoped local options without changing feed/user preferences.
$root = rtrim(getenv('TTRSS_ROOT') ?: '/var/www', '/');
$fast = filter_var(getenv('TTRSS_FAST_REFRESH') ?: 'true', FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE);
$lock = getenv('TTRSS_UPDATE_LOCK_MINUTES');
if ($lock === false || $lock === '') $lock = '1';
if ($fast === null || !ctype_digit($lock) || (int)$lock < 1 || (int)$lock > 10) {
    fwrite(STDERR, "Invalid maintenance options (lock must be 1..10 minutes)\n"); exit(1);
}
if (!$fast) { echo "Fast refresh disabled; upstream defaults retained\n"; exit(0); }
$rssFile = $root . '/classes/RSSUtils.php';
$feedFile = $root . '/classes/Feeds.php';
$rss = @file_get_contents($rssFile);
$feeds = @file_get_contents($feedFile);
if ($rss === false || $feeds === false) { fwrite(STDERR, "Unsupported upstream layout\n"); exit(1); }
$pattern = "/last_update_started < NOW\\(\\) - INTERVAL '[0-9]+ minute'/";
$rssNew = preg_replace($pattern, "last_update_started < NOW() - INTERVAL '" . (int)$lock . " minute'", $rss, -1, $count);
if ($count < 1) { fwrite(STDERR, "Upstream lock expression changed; refusing silent patch\n"); exit(1); }
if (!preg_match("/^[ \\t]*-1\\s*=>\\s*__\\('Disable updates'\\),/m", $feeds, $match)) {
    fwrite(STDERR, "Upstream interval options changed; refusing silent patch\n"); exit(1);
}
$extra = '';
foreach ([1,3,5,10] as $n) {
    if (!preg_match('/^\s*' . $n . '\s*=>/m', $feeds)) {
        $extra .= "\n\t\t\t$n => __('" . $n . ($n === 1 ? " minute" : " minutes") . "'),";
    }
}
$feedsNew = str_replace($match[0], $match[0] . $extra, $feeds);
if ($rssNew !== $rss && file_put_contents($rssFile, $rssNew, LOCK_EX) === false) exit(1);
if ($feedsNew !== $feeds && file_put_contents($feedFile, $feedsNew, LOCK_EX) === false) exit(1);
echo "Fast refresh options ready; lock={$lock} minute(s)\n";
