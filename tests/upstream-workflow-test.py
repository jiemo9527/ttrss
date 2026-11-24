#!/usr/bin/env python3
"""用本地 Git 仓库执行 workflow 的真实候选检查，GitHub API 使用边界替身。"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), '-c', 'core.autocrlf=false', *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def check_block():
    lines = (ROOT / '.github/workflows/upstream.yml').read_text(encoding='utf-8').splitlines()
    start = lines.index('      - id: check')
    start = lines.index('        run: |', start) + 1
    block = []
    for line in lines[start:]:
        if line and not line.startswith('          '):
            break
        block.append(line[10:])
    return '\n'.join(block) + '\n'


class CandidateCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ttrss-workflow-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        git(self.repo, 'init', '-q', '-b', 'main')
        git(self.repo, 'config', 'user.name', 'test')
        git(self.repo, 'config', 'user.email', 'test@example.invalid')
        git(self.repo, 'config', 'commit.gpgsign', 'false')
        (self.repo / 'scripts').mkdir()
        (self.repo / 'scripts/sync-upstream.py').write_text(
            "import pathlib,sys\npathlib.Path(sys.argv[2]).write_text('key=aaaaaaa-bbbbbbb\\n')\n",
            encoding='utf-8')
        self.lock = {'container': {'commit': 'aaaaaaa' + 'a' * 33},
                     'application': {'commit': 'bbbbbbb' + 'b' * 33}}
        self.commit_lock()
        self.base = git(self.repo, 'rev-parse', 'HEAD')
        git(self.repo, 'clone', '-q', '--bare', str(self.repo), str(self.root / 'origin.git'))
        git(self.repo, 'remote', 'add', 'origin', str(self.root / 'origin.git'))
        git(self.repo, 'fetch', '-q', 'origin')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        # 仅替代外部 GitHub API；分支获取、lock 读取、祖先判断都使用真实 Git。
        (self.bin / 'gh').write_bytes(b'#!/bin/sh\nprintf "%s\\n" "$MOCK_PR"\nexit "${MOCK_GH_RC:-0}"\n')
        (self.bin / 'python3').write_bytes(
            ('#!/bin/sh\nexec ' + shlex.quote(Path(sys.executable).as_posix()) + ' "$@"\n').encode())
        for file in self.bin.iterdir():
            file.chmod(0o755)
        self.script = self.root / 'check.sh'
        self.script.write_bytes(check_block().encode())

    def commit_lock(self):
        (self.repo / 'upstream-lock.json').write_text(json.dumps(self.lock), encoding='utf-8')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-qm', 'fixture')

    def candidate(self):
        (self.repo / 'candidate').write_text('candidate', encoding='utf-8')
        self.commit_lock()
        git(self.repo, 'push', '-q', 'origin', 'HEAD:refs/heads/bot/upstream-sync')
        git(self.repo, 'reset', '--hard', self.base)

    def run_check(self, pr='', rc=0):
        output = self.root / 'output'
        env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                   RUNNER_TEMP=self.root.as_posix(), GITHUB_OUTPUT=output.as_posix(),
                   BRANCH='bot/upstream-sync', MOCK_PR=pr, MOCK_GH_RC=str(rc))
        p = subprocess.run(['bash', '-e', self.script.as_posix()], cwd=self.repo,
                           env=env, capture_output=True, text=True)
        values = dict(line.split('=', 1) for line in output.read_text().splitlines()) if output.exists() else {}
        return p, values

    def test_branch_without_pr_must_not_skip_recovery(self):
        self.candidate()
        p, values = self.run_check()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(values.get('pending'), 'false', '候选分支存在不等于 PR 存在，必须恢复创建 PR')

    def test_matching_branch_with_pr_is_pending(self):
        self.candidate()
        p, values = self.run_check('42')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(values.get('pending'), 'true')

    def test_absent_candidate_is_not_pending(self):
        p, values = self.run_check()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(values.get('pending'), 'false')

    def test_stale_key_is_not_pending(self):
        self.lock['container']['commit'] = 'c' * 40
        self.candidate()
        p, values = self.run_check('42')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(values.get('pending'), 'false')

    def test_outdated_base_is_not_pending(self):
        self.candidate()
        (self.repo / 'main-change').write_text('main', encoding='utf-8')
        self.commit_lock()
        git(self.repo, 'push', '-q', 'origin', 'main')
        git(self.repo, 'fetch', '-q', 'origin')
        p, values = self.run_check('42')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(values.get('pending'), 'false')

    def test_github_api_failure_is_not_silent_success(self):
        self.candidate()
        p, values = self.run_check(rc=1)
        self.assertNotEqual(p.returncode, 0, 'API 失败必须中止并交给 report，不能显示已恢复')
        self.assertNotEqual(values.get('pending'), 'true')


if __name__ == '__main__':
    unittest.main()
