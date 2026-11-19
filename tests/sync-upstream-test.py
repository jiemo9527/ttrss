#!/usr/bin/env python3
"""Regression tests for scripts/sync-upstream.py using throwaway local git repos."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'sync-upstream.py'


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), '-c', 'core.autocrlf=false', *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def write(repo, files):
    for name, content in files.items():
        p = pathlib.Path(repo, name)
        if content is None:
            p.unlink()
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content.encode())


def commit(repo, files, msg):
    write(repo, files)
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', msg)
    return git(repo, 'rev-parse', 'HEAD')


def new_repo(path):
    path.mkdir()
    subprocess.run(['git', 'init', '-q', '-b', 'main', str(path)], check=True)
    for k, v in [('user.name', 't'), ('user.email', 't@example.invalid'), ('core.autocrlf', 'false'),
                 ('uploadpack.allowAnySHA1InWant', 'true'), ('commit.gpgsign', 'false')]:
        git(path, 'config', k, v)
    return path


def run_sync(fork, up, app, *extra):
    p = subprocess.run([sys.executable, str(SCRIPT), '--repo', str(fork), '--container-url', str(up),
                        '--app-url', str(app), '--github-output', '', *extra], capture_output=True, text=True)
    out = dict(line.split('=', 1) for line in p.stdout.splitlines() if '=' in line and ' ' not in line.split('=', 1)[0])
    return p.returncode, out, p.stderr


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def setup(tmp, fork_x):
    up = new_repo(tmp / 'up')
    base = {'src/x.txt': 'line1\nline2\n', 'README.md': 'upstream readme v1\n',
            '.github/workflows/ci.yml': 'name: up v1\n', 'docker-compose.yml': 'image: upstream\n',
            'Dockerfile': 'FROM alpine\nARG TTRSS_REF=' + '0' * 40 + '\nRUN true\n'}
    a = commit(up, base, 'A')
    app = new_repo(tmp / 'app')
    p1 = commit(app, {'f': '1\n'}, 'P1')
    fork = tmp / 'fork'
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'clone', '-q', str(up), str(fork)], check=True)
    for k, v in [('user.name', 't'), ('user.email', 't@example.invalid'), ('core.autocrlf', 'false'),
                 ('commit.gpgsign', 'false')]:
        git(fork, 'config', k, v)
    lock = {'container': {'repository': 'x/up', 'branch': 'main', 'commit': a},
            'application': {'repository': 'x/app', 'branch': 'main', 'commit': p1}}
    commit(fork, {'README.md': 'my readme\n', 'docker-compose.yml': 'image: mine\n',
                  '.github/workflows/ci.yml': 'name: mine\n', 'src/x.txt': fork_x,
                  'Dockerfile': 'FROM alpine\nARG TTRSS_REF=' + p1 + '\nRUN true\n',
                  'upstream-lock.json': json.dumps(lock, indent=2) + '\n'}, 'fork changes')
    b = commit(up, {'src/x.txt': 'line1 upstream\nline2\n', 'src/new.txt': 'new\n',
                    'README.md': 'upstream readme v2\n', '.github/workflows/ci.yml': 'name: up v2\n',
                    'docker-compose.yml': 'image: upstream2\n'}, 'B')
    p2 = commit(app, {'f': '2\n'}, 'P2')
    return up, app, fork, b, p2


def test_clean_sync(tmp):
    up, app, fork, b, p2 = setup(tmp, 'line1\nline2\nfork line\n')
    rc, out, err = run_sync(fork, up, app)
    check(rc == 0 and out.get('needs_update') == 'true', 'check mode should report update: ' + err)
    check(git(fork, 'status', '--porcelain') == '', 'check mode must not modify the tree')
    rc, out, err = run_sync(fork, up, app, '--apply')
    check(rc == 0 and out.get('changed') == 'true', 'sync failed: ' + err)
    read = lambda n: (fork / n).read_text()
    check(read('src/x.txt') == 'line1 upstream\nline2\nfork line\n', 'upstream change not merged with fork change')
    check(read('src/new.txt') == 'new\n', 'new upstream file missing')
    check(read('README.md') == 'my readme\n', 'fork README overwritten')
    check(read('docker-compose.yml') == 'image: mine\n', 'fork compose overwritten')
    check(read('.github/workflows/ci.yml') == 'name: mine\n', 'active workflow overwritten')
    check(read('docs/README.upstream.md') == 'upstream readme v2\n', 'upstream README not archived')
    check(read('docs/upstream-workflows/ci.yml.upstream') == 'name: up v2\n', 'upstream workflow not archived')
    check('ARG TTRSS_REF=' + p2 in read('Dockerfile'), 'TTRSS_REF not bumped')
    lock = json.loads(read('upstream-lock.json'))
    check(lock['container']['commit'] == b and lock['application']['commit'] == p2, 'lock not updated')
    check(git(fork, 'status', '--porcelain') == '', 'sync left uncommitted changes')
    check(out.get('sha') == git(fork, 'rev-parse', 'HEAD'), 'reported sha mismatch')
    rc, out, err = run_sync(fork, up, app, '--apply')
    check(rc == 0 and out.get('changed') == 'false', 'second sync should be a no-op: ' + err)


def test_conflict(tmp):
    up, app, fork, b, p2 = setup(tmp, 'line1 fork\nline2\n')
    head = git(fork, 'rev-parse', 'HEAD')
    rc, out, err = run_sync(fork, up, app, '--apply')
    check(rc == 2 and out.get('conflict') == 'true', 'conflict not reported: rc=%s %s' % (rc, err))
    check(git(fork, 'rev-parse', 'HEAD') == head, 'conflict must not commit')
    check(git(fork, 'status', '--porcelain') == '', 'conflict must leave a clean tree')


APP_PATCH = '''diff --git a/f b/f
--- a/f
+++ b/f
@@ -1 +1 @@
-%s
+patched
'''


def test_app_patch_still_applies(tmp):
    up, app, fork, b, p2 = setup(tmp, 'line1\nline2\nfork line\n')
    # app P2 changes f to "2"; a patch written against "2" applies cleanly.
    commit(fork, {'patches/0001-x.patch': APP_PATCH % '2'}, 'add app patch')
    rc, out, err = run_sync(fork, up, app, '--apply')
    check(rc == 0 and out.get('changed') == 'true', 'sync with applicable patch failed: ' + err)


def test_app_patch_broken(tmp):
    up, app, fork, b, p2 = setup(tmp, 'line1\nline2\nfork line\n')
    # patch written against the old "1" no longer applies once tt-rss moves to P2.
    head = commit(fork, {'patches/0001-x.patch': APP_PATCH % '1'}, 'add app patch')
    rc, out, err = run_sync(fork, up, app, '--apply')
    check(rc == 2 and out.get('conflict') == 'true', 'broken patch not reported: rc=%s %s' % (rc, err))
    check('0001-x.patch' in err, 'broken patch name not reported: ' + err)
    check(git(fork, 'rev-parse', 'HEAD') == head, 'broken patch must not commit')
    check(git(fork, 'status', '--porcelain') == '', 'broken patch must leave a clean tree')


def main():
    for test in (test_clean_sync, test_conflict, test_app_patch_still_applies, test_app_patch_broken):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix='ttrss-sync-'))
        try:
            test(tmp)
        finally:
            shutil.rmtree(tmp, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
        print(test.__name__ + ': PASS')
    print('sync-upstream: PASS')


if __name__ == '__main__':
    main()
