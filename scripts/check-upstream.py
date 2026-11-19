#!/usr/bin/env python3
"""Report upstream changes without merging or changing the running service."""
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
lock = json.loads((ROOT / 'upstream-lock.json').read_text())
changed = False
for key, item in lock.items():
    req = urllib.request.Request('https://api.github.com/repos/' + item['repository'] + '/commits/' + item['branch'], headers={'User-Agent': 'ttrss-maintenance'})
    with urllib.request.urlopen(req, timeout=30) as response:
        current = json.load(response)['sha']
    different = current != item['commit']
    changed |= different
    print(key + ': ' + ('UPDATE AVAILABLE' if different else 'up to date') + ' ' + current)
print('Review and test changes before updating upstream-lock.json and Dockerfile; no automatic merge/deploy.')
