#!/usr/bin/env python3
"""Release one reviewed UCarsea draft per Beijing day; report evidence, not exit-code health."""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import html
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

TZ = ZoneInfo('Asia/Shanghai')
DEFAULT_REPO = Path('/Volumes/Workspace/projects/ucarsea-blog')


def scalar(text: str, key: str) -> str | None:
    front = text.split('---', 2)[1] if text.startswith('---\n') else ''
    found = re.search(r'^' + re.escape(key) + r':\s*(.*?)\s*$', front, re.M)
    return found.group(1).strip('\"\'') if found else None


def inventory(repo: Path) -> list[dict]:
    result = []
    for path in sorted((repo / 'src/content/blog').glob('*.md')):
        text = path.read_text()
        result.append({'slug': path.stem, 'path': str(path), 'title': scalar(text, 'title'),
                       'pubDate': scalar(text, 'pubDate'), 'draft': scalar(text, 'draft') == 'true',
                       'reviewStatus': scalar(text, 'reviewStatus'), 'reviewedOn': scalar(text, 'reviewedOn'),
                       'releaseApproved': scalar(text, 'releaseApproved') == 'true'})
    return result


def legacy_success_today(repo: Path, today: str) -> bool:
    log = repo / 'scripts/release-log.txt'
    return log.exists() and any(line.startswith('[' + today + ' ') and ' RELEASED ' in line
                                and 'pushed OK' in line for line in log.read_text().splitlines())


def load_state(repo: Path) -> dict:
    path = repo / 'scripts/release-state.json'
    return json.loads(path.read_text()) if path.exists() else {'version': 1, 'history': [], 'current': None}


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.release-', delete=False) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        temp = Path(stream.name)
    temp.chmod(0o600)
    os.replace(temp, path)


def health(repo: Path, today: str, state: dict | None = None) -> dict:
    items = inventory(repo)
    drafts = [row for row in items if row['draft']]
    due = [row for row in drafts if row['pubDate'] and row['pubDate'] <= today]
    current = (state if state is not None else load_state(repo)).get('current') or {}
    last = max((row['pubDate'] for row in items if not row['draft'] and row['pubDate']), default=None)
    findings = []
    if len(drafts) <= 3:
        findings.append({'severity': 'P0' if not drafts else 'P1', 'code': 'DRAFT_BUFFER_LOW', 'actual': len(drafts), 'minimum': 3, 'refill_target': 7})
    if last is None or (dt.date.fromisoformat(today) - dt.date.fromisoformat(last)).days > 1:
        findings.append({'severity': 'P0', 'code': 'PUBLICATION_GAP', 'last_source_pubDate': last})
    if current.get('phase') in {'push_unknown', 'push_failed', 'commit_failed', 'commit_intent', 'flip_intent'}:
        findings.append({'severity': 'P0', 'code': 'PENDING_RELEASE', 'phase': current['phase'], 'slug': current.get('slug')})
    if current.get('phase') in {'pushed', 'pushed_public_pending'}:
        findings.append({'severity': 'P0', 'code': 'PUBLIC_READBACK_PENDING', 'phase': current['phase'], 'slug': current.get('slug')})
    ready = [row for row in drafts if row['reviewStatus'] == 'ready' and row['reviewedOn']]
    if len(ready) < len(drafts):
        findings.append({'severity': 'P1', 'code': 'UNREVIEWED_DRAFTS', 'count': len(drafts)-len(ready)})
    approved = [row for row in ready if row['releaseApproved']]
    if len(approved) < len(ready):
        findings.append({'severity': 'P1', 'code': 'PUBLICATION_APPROVAL_PENDING', 'count': len(ready)-len(approved)})
    return {'date': today, 'timezone': 'Asia/Shanghai', 'draft_count': len(drafts), 'ready_draft_count': len(ready), 'approved_draft_count': len(approved), 'due_draft_count': len(due),
            'next_drafts': [{k: row[k] for k in ('slug', 'pubDate', 'reviewStatus', 'reviewedOn')} for row in drafts],
            'last_source_pubDate': last, 'last_release': current, 'findings': findings,
            'healthy': not findings, 'local_file_or_git_push_is_not_publication': True}


def run_cmd(repo: Path, args: list[str], timeout: int = 120) -> str:
    result = subprocess.run(args, cwd=repo, capture_output=True, text=True, timeout=timeout,
                            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_OPTIONAL_LOCKS': '0'})
    if result.returncode:
        raise RuntimeError(args[0] + ' returned ' + str(result.returncode))
    return result.stdout.strip()


def verify_live(slug: str, title: str) -> dict:
    url = 'https://blog.ucarsea.com/' + slug + '/'
    result = {'url': url, 'verified_at': dt.datetime.now(TZ).isoformat(),
              'method': 'public GET via requests, no proxy environment or credentials'}
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(url, timeout=(5, 20))
        soup = BeautifulSoup(response.text, 'html.parser')
        canonical = soup.select_one('link[rel="canonical"]')
        expected_h1 = any(h.get_text(' ', strip=True) == title for h in soup.select('h1'))
        canonical_url = canonical.get('href') if canonical else None
        result.update(http=response.status_code, expected_title_present=expected_h1,
                      canonical=canonical_url)
        result['public_verified'] = response.status_code == 200 and expected_h1 and canonical_url == url
    except Exception as exc:
        result.update(error_type=type(exc).__name__, public_verified=False)
    return result


class Publisher:
    def __init__(self, repo: Path, today: str | None = None):
        self.repo = repo
        self.today = today or dt.datetime.now(TZ).date().isoformat()
        self.state = load_state(repo)

    def event(self, phase: str, **fields) -> dict:
        current = self.state.get('current') or {}
        current.update(phase=phase, updated_at=dt.datetime.now(TZ).isoformat(), **fields)
        self.state['current'] = current
        self.state['history'].append(dict(current))
        atomic_json(self.repo / 'scripts/release-state.json', self.state)
        return current

    def finish(self, status: str, **fields) -> dict:
        report = {'at': dt.datetime.now(TZ).isoformat(), 'status': status, **fields,
                  'health': health(self.repo, self.today, self.state), 'notifications_sent': 0}
        atomic_json(self.repo / 'scripts/release-health.json', report)
        return report

    def verify_current(self) -> dict:
        current = self.state['current']
        observed = verify_live(current['slug'], current['title'])
        if observed.get('public_verified'):
            self.event('public_verified', public_evidence=observed)
            with (self.repo / 'scripts/release-log.txt').open('a') as stream:
                stream.write(f"[{dt.datetime.now(TZ):%Y-%m-%d %H:%M:%S}] RELEASED {current['slug']} (pubDate={current['release_date']}) — pushed OK; public HTTP200 verified\n")
            return self.finish('public_verified', public_evidence=observed)
        self.event('pushed_public_pending', public_evidence=observed)
        return self.finish('pushed_public_pending', public_evidence=observed)

    def publish(self) -> dict:
        current = self.state.get('current') or {}
        phase = current.get('phase')
        if phase in {'pushed', 'pushed_public_pending'}:
            result = self.verify_current()
            if result['status'] != 'public_verified' or current.get('release_date') == self.today:
                return result
        elif phase in {'committed', 'push_unknown', 'push_failed'}:
            # Reconcile the same commit, never flip a second article or blindly retry a push.
            remote = run_cmd(self.repo, ['git', 'ls-remote', 'origin', 'refs/heads/main'], 40).split()
            if remote and remote[0] == current.get('commit'):
                self.event('pushed', reconciled_remote_commit=remote[0])
                return self.verify_current()
            return self.finish('blocked_pending_push_reconciliation', requires_action=True)
        elif phase in {'flip_intent', 'commit_intent', 'commit_failed'}:
            return self.finish('blocked_pending_local_reconciliation', requires_action=True)
        if (self.state.get('current') or {}).get('release_date') == self.today and (self.state['current']['phase'] == 'public_verified'):
            return self.finish('already_published_today')
        if legacy_success_today(self.repo, self.today):
            return self.finish('already_published_today_legacy_receipt')

        due = sorted([row for row in inventory(self.repo) if row['draft'] and row['pubDate'] and row['pubDate'] <= self.today],
                     key=lambda row: (row['pubDate'], row['slug']))
        if not due:
            return self.finish('no_due_draft_not_published', requires_action=True)
        candidate = due[0]
        if not candidate['releaseApproved']:
            return self.finish('blocked_publication_approval_missing', slug=candidate['slug'], requires_action=True)
        if candidate['reviewStatus'] != 'ready' or not candidate['reviewedOn']:
            return self.finish('blocked_draft_review_missing', slug=candidate['slug'], requires_action=True)
        review_age = (dt.date.fromisoformat(self.today) - dt.date.fromisoformat(candidate['reviewedOn'])).days
        if not 0 <= review_age <= 30:
            return self.finish('blocked_review_stale', slug=candidate['slug'], requires_action=True)
        dirty = run_cmd(self.repo, ['git', 'status', '--porcelain=v1', '--untracked-files=no'])
        if dirty:
            return self.finish('blocked_existing_tracked_changes', requires_action=True)
        if run_cmd(self.repo, ['git', 'branch', '--show-current']) != 'main':
            return self.finish('blocked_unexpected_branch', requires_action=True)
        if run_cmd(self.repo, ['git', 'log', '--format=%H', 'origin/main..HEAD']):
            return self.finish('blocked_existing_unpushed_commits', requires_action=True)

        path = Path(candidate['path'])
        original = path.read_text()
        changed = re.sub(r'^draft:\s*true\s*$', 'draft: false', original, count=1, flags=re.M)
        changed = re.sub(r'^pubDate:.*$', 'pubDate: ' + self.today, changed, count=1, flags=re.M)
        assert changed != original and scalar(changed, 'draft') == 'false'
        self.state['current'] = None
        self.event('flip_intent', slug=candidate['slug'], title=candidate['title'], release_date=self.today,
                   intended_pubDate=candidate['pubDate'], review_date=candidate['reviewedOn'])
        path.write_text(changed)
        try:
            run_cmd(self.repo, ['npm', 'run', 'build'], 180)
        except Exception as exc:
            path.write_text(original)  # Restore only this process's uncommitted edit.
            self.event('build_failed_restored', error_type=type(exc).__name__)
            return self.finish('build_failed_no_publish', requires_action=True)
        relative = str(path.relative_to(self.repo))
        self.event('commit_intent')
        try:
            run_cmd(self.repo, ['git', 'add', '--', relative])
            run_cmd(self.repo, ['git', 'commit', '-m', f"post: release {candidate['slug']} ({self.today})"], 60)
        except Exception as exc:
            self.event('commit_failed', error_type=type(exc).__name__)
            return self.finish('commit_failed_no_push', requires_action=True)
        commit = run_cmd(self.repo, ['git', 'rev-parse', 'HEAD'])
        self.event('committed', commit=commit)
        self.event('push_unknown', commit=commit)
        try:
            run_cmd(self.repo, ['git', 'push', 'origin', 'HEAD:main'], 90)
        except Exception as exc:
            self.event('push_failed', error_type=type(exc).__name__)
            return self.finish('push_failed_no_new_article_retry', requires_action=True)
        self.event('pushed', commit=commit)
        return self.verify_current()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, default=DEFAULT_REPO)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not (repo / 'src/content/blog').is_dir():
        print(json.dumps({'status': 'repository_unavailable', 'published': False}))
        return 75
    if args.check:
        result = health(repo, dt.datetime.now(TZ).date().isoformat())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['healthy'] else 2
    with (repo / 'scripts/release.lock').open('a') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'status': 'release_already_running', 'published': False}))
            return 75
        result = Publisher(repo).publish()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result.get('requires_action') else 0


if __name__ == '__main__':
    raise SystemExit(main())
