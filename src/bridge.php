<?php
// Shared-secret authenticated bridge. Keep /etc/ttrss-bridge.key outside the image.
$expected = trim((string) @file_get_contents('/etc/ttrss-bridge.key'));
$key = (string) ($_SERVER['HTTP_X_BRIDGE_KEY'] ?? $_GET['key'] ?? '');
header('Cache-Control: no-store');
if ($expected === '' || !hash_equals($expected, $key)) {
    http_response_code(403); exit('Forbidden');
}
$url = (string) ($_GET['url'] ?? '');
if (!filter_var($url, FILTER_VALIDATE_URL) || !in_array(strtolower((string) parse_url($url, PHP_URL_SCHEME)), ['http', 'https'], true)
    || parse_url($url, PHP_URL_USER) !== null || parse_url($url, PHP_URL_PASS) !== null) {
    http_response_code(400); exit('Invalid URL');
}
// Only grant bridge access to trusted users: FlareSolverr follows redirects and
// can access its own network. Isolate its network; authentication is not SSRF isolation.
$ch = curl_init('http://flaresolverr:8191/v1');
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => json_encode(['cmd'=>'request.get','url'=>$url,'maxTimeout'=>60000]),
    CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_CONNECTTIMEOUT => 10,
    CURLOPT_TIMEOUT => 70,
]);
$res = curl_exec($ch);
$status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);
$json = $res === false ? null : json_decode($res, true);
if ($status !== 200 || !is_string($json['solution']['response'] ?? null)) {
    http_response_code(502); exit('Bridge upstream failed');
}
$html = $json['solution']['response'];
// Preserve raw RSS/Atom; Chrome's rendered <pre> needs entity decoding.
$xml = preg_match('/^\s*(?:<\?xml|<rss\b|<feed\b|<rdf:RDF\b)/i', $html)
    ? trim($html) : trim(html_entity_decode(strip_tags($html), ENT_QUOTES | ENT_XML1, 'UTF-8'));
header('Content-Type: application/xml; charset=utf-8');
header('X-Content-Type-Options: nosniff');
echo $xml;
