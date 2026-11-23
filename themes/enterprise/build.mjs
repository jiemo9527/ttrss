#!/usr/bin/env node
// Builds the "enterprise" TT-RSS themes from the pinned TT-RSS LESS sources.
//
//   node themes/enterprise/build.mjs --ttrss <tt-rss root> --out <themes.local dir>
//
// Output (all under --out):
//   enterprise.css        light
//   enterprise_night.css  dark
//   enterprise_auto.css   follows the OS light/dark setting
//   enterprise/flat_light.css, enterprise/flat_dark.css
//                         TT-RSS's dijit widget theme (lib/flat-ttrss) with the
//                         accent colour family remapped to ours
//
// Fails (exit 1) when an upstream file it relies on changed shape, so a broken
// theme never ships silently.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, all) =>
	(v.startsWith('--') ? a.concat([[v.slice(2), all[i + 1]]]) : a), []));
const ROOT = path.resolve(args.ttrss || '/var/www');
const OUT = path.resolve(args.out || path.join(ROOT, 'themes.local'));
const require = createRequire(path.join(args['node-modules'] || process.cwd(), 'noop.js'));
const less = require('less');

function fail(msg) { console.error('theme build: ' + msg); process.exit(1); }
const read = (p) => fs.readFileSync(p, 'utf8');
const hash = (s) => crypto.createHash('sha256').update(s).digest('hex').slice(0, 10);

// ---------- colour helpers ----------
function hexToRgb(h) {
	h = h.replace('#', '');
	if (h.length === 3) h = h.split('').map((c) => c + c).join('');
	return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
}
function rgbToHsl([r, g, b]) {
	const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
	if (mx === mn) return [0, 0, l];
	const d = mx - mn, s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
	const h = mx === r ? ((g - b) / d + (g < b ? 6 : 0)) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
	return [h * 60, s, l];
}
function hslToHex([h, s, l]) {
	h = ((h % 360) + 360) % 360 / 360; s = Math.min(1, Math.max(0, s)); l = Math.min(1, Math.max(0, l));
	const f = (p, q, t) => { t = (t + 1) % 1; return t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p; };
	let rgb;
	if (s === 0) rgb = [l, l, l];
	else { const q = l < 0.5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q; rgb = [f(p, q, h + 1 / 3), f(p, q, h), f(p, q, h - 1 / 3)]; }
	return '#' + rgb.map((v) => Math.round(v * 255).toString(16).padStart(2, '0')).join('');
}
const HEX = /#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b/g;
const colours = (css) => new Set((css.match(HEX) || []).map((c) => hslToHex(rgbToHsl(hexToRgb(c)))));

// Map the accent family of `css` (colours not present in `other`, i.e. the
// theme-specific ones) from `base` to `target`, keeping each shade's relative
// lightness/saturation. Neutral greys get a faint cool tint.
function recolor(css, other, base, target, tint) {
	const own = colours(css), theirs = colours(other);
	const [bh, bs, bl] = rgbToHsl(hexToRgb(base)), [th, ts, tl] = rgbToHsl(hexToRgb(target));
	const map = new Map();
	for (const c of own) {
		const [h, s, l] = rgbToHsl(hexToRgb(c));
		if (!theirs.has(c) && s >= 0.25 && Math.abs(((h - bh + 540) % 360) - 180) <= 30) {
			map.set(c, hslToHex([th + (h - bh), s * (ts / bs), l + (tl - bl)]));
		} else if (s < 0.06 && l > 0.02 && l < 0.995) {
			map.set(c, hslToHex([tint.h, tint.s, l]));
		}
	}
	if (!map.has(hslToHex(rgbToHsl(hexToRgb(base))))) fail(`base accent ${base} not found in widget stylesheet`);
	const out = css.replace(HEX, (c) => map.get(hslToHex(rgbToHsl(hexToRgb(c)))) || c);
	return { css: out, mapped: [...map.entries()].filter(([a]) => !theirs.has(a)).length };
}

// ---------- widget (dijit) stylesheets ----------
const flatDir = path.join(ROOT, 'lib/flat-ttrss');
const flatLight = read(path.join(flatDir, 'flat_combined.css'));
const flatDark = read(path.join(flatDir, 'flat_combined_dark.css'));
const T = JSON.parse(read(path.join(HERE, 'tokens.json')));
// flat css uses relative url()s (fonts/, images/) - rebase them to lib/flat-ttrss.
const rebase = (css) => css.replace(/url\((['"]?)(?!data:|https?:|\/)([^'")]+)\1\)/g,
	(m, q, u) => `url(${q}../../lib/flat-ttrss/${u}${q})`);

const light = recolor(flatLight, flatDark, T.upstream.light_accent, T.light.accent, T.light.neutral_tint);
const dark = recolor(flatDark, flatLight, T.upstream.dark_accent, T.dark.accent, T.dark.neutral_tint);
if (light.mapped < 5 || dark.mapped < 5) fail(`too few accent shades remapped (light ${light.mapped}, dark ${dark.mapped})`);

fs.mkdirSync(path.join(OUT, 'enterprise'), { recursive: true });
const flatFiles = { light: rebase(light.css), dark: rebase(dark.css) };
for (const [k, css] of Object.entries(flatFiles)) fs.writeFileSync(path.join(OUT, 'enterprise', `flat_${k}.css`), css);

// ---------- compile LESS against the upstream sources ----------
async function compile(entry, upstreamFlat, ourFlat) {
	const file = path.join(HERE, entry);
	const { css } = await less.render(read(file), {
		filename: file,
		javascriptEnabled: true,
		globalVars: { 'ttrss-themes': JSON.stringify(path.join(ROOT, 'themes').replace(/\\/g, '/')) },
	});
	// Swap upstream's widget stylesheet import for our recoloured copy.
	const re = new RegExp(`@import url\\(["']\\.\\./lib/flat-ttrss/${upstreamFlat}["']\\);\\n?`, 'g');
	const found = (css.match(re) || []).length;
	if (found < 1) fail(`${entry}: expected @import of ${upstreamFlat} not found (upstream layout changed?)`);
	// Upstream urls are relative to themes/; ours live in themes.local/ (same depth),
	// so "../vendor", "../lib", "../images" keep resolving to the TT-RSS root.
	for (const u of css.match(/url\((['"]?)([^'")]+)\1\)/g) || []) {
		const p = u.replace(/^url\((['"]?)/, '').replace(/['"]?\)$/, '');
		if (/^(data:|https?:|#)/.test(p) || p.startsWith('../') || p.startsWith('enterprise/')) continue;
		fail(`${entry}: unexpected relative url ${p} (would break outside themes/)`);
	}
	return `@import url("enterprise/${ourFlat}?${hash(flatFiles[ourFlat.includes('dark') ? 'dark' : 'light'])}");\n` + css.replace(re, '');
}

const outLight = await compile('enterprise.less', 'flat_combined.css', 'flat_light.css');
const outDark = await compile('enterprise_night.less', 'flat_combined_dark.css', 'flat_dark.css');
for (const [name, css, forbidden] of [['enterprise.css', outLight, T.upstream.light_accent], ['enterprise_night.css', outDark, T.upstream.dark_accent]]) {
	if (css.length < 40000) fail(`${name} suspiciously small (${css.length} bytes)`);
	if (css.toLowerCase().includes(forbidden.toLowerCase())) fail(`${name} still contains upstream accent ${forbidden}`);
	fs.writeFileSync(path.join(OUT, name), css);
}
fs.writeFileSync(path.join(OUT, 'enterprise_auto.css'),
	`@import url("enterprise.css?${hash(outLight)}") not all and (prefers-color-scheme: dark);\n` +
	`@import url("enterprise_night.css?${hash(outDark)}") (prefers-color-scheme: dark);\n`);
for (const [k, css] of Object.entries(flatFiles))
	if (css.toLowerCase().includes((k === 'light' ? T.upstream.light_accent : T.upstream.dark_accent).toLowerCase()))
		fail(`flat_${k}.css still contains the upstream accent`);

console.log(`theme build: OK (${light.mapped} light + ${dark.mapped} dark accent shades remapped) -> ${OUT}`);
