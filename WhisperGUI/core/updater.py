"""Update a clean Git installation from the public release repository.

Checks only fetch objects. Applying is a separate, explicitly confirmed fast-forward
to the inspected SHA. No reset, stash, credential storage, or automatic code execution.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

REPOSITORY = 'konata91008/KonataWhisperGUI-Public'
BRANCH = 'main'


class UpdateError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class UpdateInfo:
    head: str
    target: str
    status: str
    version: str
    date: str
    summary: str
    blocker: str = ''
    runtime_changes: bool = False

    @property
    def can_update(self):
        return self.status == 'available' and not self.blocker


class GitUpdater:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.git = shutil.which('git')

    def _run(self, *args, check=True, timeout=30):
        if not self.git:
            raise UpdateError('git_missing')
        env = os.environ.copy()
        # Use the user's existing credential helper/SSH key, without terminal prompts.
        env['GIT_TERMINAL_PROMPT'] = '0'
        env.setdefault('GIT_SSH_COMMAND', 'ssh -o BatchMode=yes -o ConnectTimeout=15')
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        try:
            result = subprocess.run([self.git, '-C', str(self.root), *args],
                                    capture_output=True, text=True, encoding='utf-8',
                                    errors='replace', timeout=timeout, env=env, **options)
        except subprocess.TimeoutExpired:
            raise UpdateError('timeout') from None
        except OSError:
            raise UpdateError('git_failed') from None
        if check and result.returncode:
            # Do not display raw Git output: a remote URL may contain credentials.
            raise UpdateError('git_failed')
        return result

    def _validate_installation(self):
        result = self._run('rev-parse', '--show-toplevel', check=False)
        if result.returncode or Path(result.stdout.strip()).resolve() != self.root:
            raise UpdateError('not_git')
        remote = self._run('config', '--get', 'remote.origin.url', check=False).stdout.strip()
        if remote.startswith('git@github.com:'):
            repository = remote.split(':', 1)[1]
        else:
            url = urlsplit(remote)
            if url.scheme not in ('https', 'ssh') or url.hostname != 'github.com':
                raise UpdateError('wrong_remote')
            repository = url.path.lstrip('/')
        if repository.removesuffix('.git').lower() != REPOSITORY.lower():
            raise UpdateError('wrong_remote')

    def _head(self):
        return self._run('rev-parse', 'HEAD').stdout.strip()

    def _ancestor(self, first, second):
        result = self._run('merge-base', '--is-ancestor', first, second, check=False)
        if result.returncode not in (0, 1):
            raise UpdateError('git_failed')
        return result.returncode == 0

    def _blocker(self):
        if self._run('branch', '--show-current').stdout.strip() != BRANCH:
            return 'wrong_branch'
        if self._run('status', '--porcelain', '--untracked-files=normal').stdout.strip():
            return 'local_changes'
        for marker in ('MERGE_HEAD', 'REBASE_HEAD', 'CHERRY_PICK_HEAD', 'BISECT_LOG'):
            path = self._run('rev-parse', '--git-path', marker).stdout.strip()
            if (self.root / path).exists():
                return 'local_changes'
        return ''

    def check(self):
        self._validate_installation()
        head = self._head()
        blocker = self._blocker()
        result = self._run('fetch', '--no-tags', 'origin', f'refs/heads/{BRANCH}',
                           check=False, timeout=90)
        if result.returncode:
            raise UpdateError('fetch_failed')
        target = self._run('rev-parse', 'FETCH_HEAD^{commit}').stdout.strip()
        if head == target:
            status = 'current'
        elif self._ancestor(head, target):
            status = 'available'
        elif self._ancestor(target, head):
            status = 'ahead'
        else:
            status = 'diverged'
        version = target[:7]
        date = self._run('show', '-s', '--format=%cs', target).stdout.strip()
        metadata = self._run('show', f'{target}:WhisperGUI/version.json', check=False)
        if not metadata.returncode:
            try:
                data = json.loads(metadata.stdout)
                if re.fullmatch(r'\d+(?:\.\d+){1,3}(?:[-+][\w.-]+)?', str(data.get('version', ''))):
                    version = 'v' + data['version']
                if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(data.get('updated_at', ''))):
                    date = data['updated_at']
            except (ValueError, TypeError):
                pass
        summary = self._run('log', '-8', '--format=%h %s', f'{head}..{target}').stdout.strip()
        changed = self._run('diff', '--name-only', head, target).stdout.splitlines()
        runtime_changes = any(p == 'requirements.txt' or p.startswith('whisper.cpp/') for p in changed)
        return UpdateInfo(head, target, status, version, date, summary[:3000], blocker, runtime_changes)

    def apply(self, info):
        if not info.can_update or not re.fullmatch(r'[0-9a-f]{40,64}', info.target):
            raise UpdateError('cannot_apply')
        self._validate_installation()
        if self._head() != info.head:
            raise UpdateError('state_changed')
        blocker = self._blocker()
        if blocker:
            raise UpdateError(blocker)
        if not self._ancestor(info.head, info.target):
            raise UpdateError('state_changed')
        # A named/pinned SHA prevents a later remote commit being installed unseen.
        with tempfile.TemporaryDirectory(prefix='tjksub-hooks-') as hooks_dir:
            result = self._run('-c', f'core.hooksPath={hooks_dir}', 'merge', '--ff-only', '--no-edit',
                               info.target, check=False, timeout=90)
        if result.returncode or self._head() != info.target:
            raise UpdateError('apply_failed')
        return info
