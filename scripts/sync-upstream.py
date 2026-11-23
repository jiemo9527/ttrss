#!/usr/bin/env python3
"""Import upstream Awesome-TTRSS changes and bump the pinned TT-RSS commit.

Upstream container changes are imported as a single patch commit, not as a git
merge: workflow files are archived under docs/upstream-workflows instead of
being activated, and the bot never pushes commits that touch .github/workflows
(GITHUB_TOKEN may not modify workflows).

Exit codes: 0 ok (updated or already current), 1 error, 2 manual merge needed.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

CONTAINER_URL = 'https://github.com/HenryQW/Awesome-TTRSS.git'
APP_URL = 'https://github.com/tt-rss/tt-rss.git'
# Paths owned by this fork: upstream changes to them are not applied directly.
OWNED = ['.github/workflows', '.github/dependabot.yml', 'README.md', 'docker-compose.yml']
ARCHIVE_DIR = 'docs/upstream-workflows'
README_ARCHIVE = 'docs/README.upstream.md'
REF_RE = re.compile(r'^ARG TTRSS_REF=[0-9a-f]{40}$', re.M)
SAFE_TO_RESET = []


def git(repo, *args, check=True, binary=False, stdin=None):
    p = subprocess.run(['git', '-C', str(repo), *args], input=stdin, capture_output=True,
                       text=not binary)
    if check and p.returncode:
        raise RuntimeError('git ' + ' '.join(args) + ' failed:\n' + (p.stderr if not binary else p.stderr.decode(errors='replace')))
    return p


def remote_head(repo, url, branch):
    out = git(repo, 'ls-remote', url, 'refs/heads/' + branch).stdout.split()
    if not out:
        raise RuntimeError('cannot resolve %s %s' % (url, branch))
    return out[0]


def fetch(repo, url, sha):
    git(repo, 'fetch', '--no-tags', '--quiet', url, sha)


def patches_apply(repo, app_url, sha):
    """Return the names of patches/*.patch that do not apply cleanly to tt-rss `sha`."""
    patches = sorted((pathlib.Path(repo) / 'patches').glob('*.patch'))
    if not patches:
        return []
    with tempfile.TemporaryDirectory(prefix='ttrss-app-') as tmp:
        subprocess.run(['git', 'init', '-q', tmp], check=True)
        git(tmp, 'fetch', '--no-tags', '--quiet', '--depth=1', app_url, sha)
        git(tmp, '-c', 'core.autocrlf=false', 'checkout', '--quiet', '--detach', 'FETCH_HEAD')
        failed = []
        for p in patches:
            if git(tmp, 'apply', '--check', '--whitespace=nowarn', str(p), check=False).returncode:
                failed.append(p.name)
            else:
                git(tmp, 'apply', '--whitespace=nowarn', str(p))
        return failed


def emit(path, values):
    if path:
        with open(path, 'a', encoding='utf-8') as f:
            for k, v in values.items():
                f.write('%s=%s\n' % (k, v))
    for k, v in values.items():
        print('%s=%s' % (k, v))


def archive_upstream(repo, new):
    """Store upstream README/workflows for reference; never activate them."""
    root = pathlib.Path(repo)
    (root / README_ARCHIVE).parent.mkdir(parents=True, exist_ok=True)
    (root / README_ARCHIVE).write_bytes(git(repo, 'show', new + ':README.md', binary=True).stdout)
    names = git(repo, 'ls-tree', '--name-only', new, '.github/workflows/').stdout.split()
    keep = set()
    adir = root / ARCHIVE_DIR
    adir.mkdir(parents=True, exist_ok=True)
    for name in names:
        target = adir / (pathlib.PurePosixPath(name).name + '.upstream')
        target.write_bytes(git(repo, 'show', new + ':' + name, binary=True).stdout)
        keep.add(target.name)
    for old in adir.glob('*.upstream'):
        if old.name not in keep:
            old.unlink()
    git(repo, 'add', '-A', '--', README_ARCHIVE, ARCHIVE_DIR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='create a sync commit (default: check only)')
    ap.add_argument('--repo', default=str(pathlib.Path(__file__).resolve().parents[1]))
    ap.add_argument('--container-url', default=CONTAINER_URL)
    ap.add_argument('--app-url', default=APP_URL)
    ap.add_argument('--github-output', default=os.environ.get('GITHUB_OUTPUT'))
    a = ap.parse_args()
    repo = a.repo
    root = pathlib.Path(repo)
    lock_path = root / 'upstream-lock.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    c, app = lock['container'], lock['application']

    new_c = remote_head(repo, a.container_url, c['branch'])
    new_app = remote_head(repo, a.app_url, app['branch'])
    container_changed = new_c != c['commit']
    app_changed = new_app != app['commit']
    key = new_c[:7] + '-' + new_app[:7]
    print('container: %s -> %s%s' % (c['commit'][:7], new_c[:7], ' (update)' if container_changed else ''))
    print('application: %s -> %s%s' % (app['commit'][:7], new_app[:7], ' (update)' if app_changed else ''))
    needs = container_changed or app_changed
    if not a.apply:
        emit(a.github_output, {'needs_update': str(needs).lower(), 'key': key})
        return 0
    if not needs:
        emit(a.github_output, {'changed': 'false', 'key': key})
        return 0
    if git(repo, 'status', '--porcelain', '--untracked-files=no').stdout.strip():
        raise RuntimeError('working tree has uncommitted changes')
    SAFE_TO_RESET.append(repo)

    if container_changed:
        fetch(repo, a.container_url, new_c)
        fetch(repo, a.container_url, c['commit'])
        if git(repo, 'merge-base', '--is-ancestor', c['commit'], new_c, check=False).returncode:
            print('upstream history was rewritten; manual review required', file=sys.stderr)
            emit(a.github_output, {'changed': 'false', 'conflict': 'true', 'key': key})
            return 2
        excludes = [':(exclude)' + p for p in OWNED]
        patch = git(repo, 'diff', '--binary', '--full-index', c['commit'], new_c, '--', '.', *excludes,
                    binary=True).stdout
        if patch:
            res = git(repo, 'apply', '--3way', '--index', '--whitespace=nowarn', check=False,
                      binary=True, stdin=patch)
            if res.returncode:
                conflicts = git(repo, 'diff', '--name-only', '--diff-filter=U').stdout.split()
                git(repo, 'reset', '--hard', '--quiet', 'HEAD')
                print('upstream patch conflicts: ' + (', '.join(conflicts) or res.stderr.decode(errors='replace').strip()),
                      file=sys.stderr)
                emit(a.github_output, {'changed': 'false', 'conflict': 'true', 'key': key})
                return 2
        archive_upstream(repo, new_c)
        c['commit'] = new_c

    if app_changed:
        dockerfile = root / 'Dockerfile'
        text = dockerfile.read_bytes().decode('utf-8')
        if len(REF_RE.findall(text.replace('\r\n', '\n'))) != 1:
            git(repo, 'reset', '--hard', '--quiet', 'HEAD')
            print('Dockerfile TTRSS_REF pin not found exactly once', file=sys.stderr)
            emit(a.github_output, {'changed': 'false', 'conflict': 'true', 'key': key})
            return 2
        text = re.sub(r'^ARG TTRSS_REF=[0-9a-f]{40}(\r?)$', lambda m: 'ARG TTRSS_REF=' + new_app + m.group(1),
                      text, flags=re.M)
        dockerfile.write_bytes(text.encode('utf-8'))
        app['commit'] = new_app
        git(repo, 'add', 'Dockerfile')

    failed = patches_apply(repo, a.app_url, app['commit'])
    if failed:
        git(repo, 'reset', '--hard', '--quiet', 'HEAD')
        print('local patches no longer apply to tt-rss %s: %s' % (app['commit'][:7], ', '.join(failed)),
              file=sys.stderr)
        emit(a.github_output, {'changed': 'false', 'conflict': 'true', 'key': key})
        return 2

    lock_path.write_text(json.dumps(lock, indent=2) + '\n', encoding='utf-8', newline='\n')
    git(repo, 'add', 'upstream-lock.json')
    msg = 'chore(sync): Awesome-TTRSS %s, tt-rss %s' % (new_c[:7], new_app[:7])
    body = 'Upstream container: %s\nUpstream application: %s\n' % (new_c, new_app)
    git(repo, 'commit', '--quiet', '-m', msg, '-m', body)
    sha = git(repo, 'rev-parse', 'HEAD').stdout.strip()
    emit(a.github_output, {'changed': 'true', 'sha': sha, 'key': key})
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except Exception:
        # Never leave a half-applied sync behind (only once the tree was verified clean).
        if SAFE_TO_RESET:
            subprocess.run(['git', '-C', SAFE_TO_RESET[0], 'reset', '--hard', '--quiet', 'HEAD'])
        raise
