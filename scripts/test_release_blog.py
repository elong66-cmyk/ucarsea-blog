import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

STAGE = Path(__file__).parent / 'stage'
if not STAGE.exists():
    STAGE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('release_blog', STAGE / 'release_blog.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / 'src/content/blog').mkdir(parents=True)
        (self.repo / 'scripts').mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, slug='sample', date='2026-10-21', ready=True):
        path = self.repo / 'src/content/blog' / (slug + '.md')
        path.write_text(f'---\ntitle: "Sample {slug}"\npubDate: {date}\ndraft: true\nreleaseApproved: true\nreviewStatus: {"ready" if ready else "pending"}\nreviewedOn: 2026-10-21\n---\nA sourcing checklist.\n')
        return path

    def test_empty_inventory_warns_without_grep_pipeline(self):
        result = mod.health(self.repo, '2026-10-21')
        self.assertEqual(result['draft_count'], 0)
        self.assertFalse(result['healthy'])

    def test_legacy_zero_grep_pipeline_reproduces_silent_abort(self):
        path = self.repo / 'plain.md'
        path.write_text('draft: false\n')
        run = subprocess.run(['/bin/bash', '-c', 'set -euo pipefail; n=$(grep -l "^draft: true" "$1" | wc -l); echo alert-reached', 'test', str(path)], capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertNotIn('alert-reached', run.stdout)

    def test_noop_today_is_not_success(self):
        (self.repo / 'scripts/release-log.txt').write_text('[2026-10-21 10:00:00] no due draft — no-op\n')
        self.assertFalse(mod.legacy_success_today(self.repo, '2026-10-21'))

    def test_actual_legacy_success_deduplicates(self):
        (self.repo / 'scripts/release-log.txt').write_text('[2026-10-21 10:00:00] RELEASED sample — pushed OK\n')
        self.assertTrue(mod.legacy_success_today(self.repo, '2026-10-21'))
        self.post()
        self.assertEqual(mod.Publisher(self.repo, '2026-10-21').publish()['status'], 'already_published_today_legacy_receipt')

    def test_no_due_draft_is_not_published(self):
        result = mod.Publisher(self.repo, '2026-10-21').publish()
        self.assertTrue(result['requires_action'])
        self.assertEqual(result['status'], 'no_due_draft_not_published')

    def test_future_only_draft_does_not_release_early(self):
        path = self.post(date='2026-10-22')
        self.assertEqual(mod.Publisher(self.repo, '2026-10-21').publish()['status'], 'no_due_draft_not_published')
        self.assertIn('draft: true', path.read_text())

    def test_review_gate(self):
        self.post(ready=False)
        self.assertEqual(mod.Publisher(self.repo, '2026-10-21').publish()['status'], 'blocked_draft_review_missing')

    def test_unapproved_content_cannot_be_auto_published(self):
        path = self.post()
        path.write_text(path.read_text().replace('releaseApproved: true', 'releaseApproved: false'))
        self.assertEqual(mod.Publisher(self.repo, '2026-10-21').publish()['status'], 'blocked_publication_approval_missing')

    def test_stale_review_gate(self):
        self.post()
        self.assertEqual(mod.Publisher(self.repo, '2026-12-01').publish()['status'], 'blocked_review_stale')

    def test_dirty_tracked_files_untouched(self):
        path = self.post()
        before = path.read_text()
        with patch.object(mod, 'run_cmd', return_value=' M unrelated.md'):
            result = mod.Publisher(self.repo, '2026-10-21').publish()
        self.assertEqual(result['status'], 'blocked_existing_tracked_changes')
        self.assertEqual(path.read_text(), before)

    def test_pending_local_commit_does_not_flip_new_draft(self):
        self.post()
        mod.atomic_json(self.repo / 'scripts/release-state.json', {'version': 1, 'history': [], 'current': {'phase': 'commit_intent'}})
        self.assertEqual(mod.Publisher(self.repo, '2026-10-21').publish()['status'], 'blocked_pending_local_reconciliation')

    def test_public_pending_rechecks_same_url_not_new_article(self):
        self.post('new')
        mod.atomic_json(self.repo / 'scripts/release-state.json', {'version': 1, 'history': [], 'current': {'phase': 'pushed_public_pending', 'slug': 'old', 'title': 'Old', 'release_date': '2026-10-21'}})
        with patch.object(mod, 'verify_live', return_value={'public_verified': False, 'http': 404}) as verifier:
            result = mod.Publisher(self.repo, '2026-10-21').publish()
        verifier.assert_called_once_with('old', 'Old')
        self.assertEqual(result['status'], 'pushed_public_pending')
        self.assertIn('draft: true', (self.repo / 'src/content/blog/new.md').read_text())

    def test_committed_crash_window_never_flips_second_article(self):
        path = self.post('second')
        mod.atomic_json(self.repo / 'scripts/release-state.json', {'version': 1, 'history': [], 'current': {'phase': 'committed', 'slug': 'first', 'title': 'First', 'commit': 'aaa', 'release_date': '2026-10-21'}})
        with patch.object(mod, 'run_cmd', return_value='bbb\trefs/heads/main'):
            result = mod.Publisher(self.repo, '2026-10-21').publish()
        self.assertEqual(result['status'], 'blocked_pending_push_reconciliation')
        self.assertIn('draft: true', path.read_text())

    def test_unreviewed_stock_is_not_healthy_ready_buffer(self):
        for n in range(3): self.post(str(n), ready=False)
        result = mod.health(self.repo, '2026-10-21')
        self.assertEqual(result['ready_draft_count'], 0)
        self.assertIn('UNREVIEWED_DRAFTS', [row['code'] for row in result['findings']])

    def test_three_remaining_drafts_trigger_refill(self):
        for n in range(3): self.post(str(n))
        result = mod.health(self.repo, '2026-10-21')
        self.assertIn('DRAFT_BUFFER_LOW', [row['code'] for row in result['findings']])

    def test_unverified_deployment_is_not_healthy(self):
        result = mod.health(self.repo, '2026-10-21', {'current': {
            'phase': 'pushed_public_pending', 'slug': 'sample'}})
        self.assertIn('PUBLIC_READBACK_PENDING', [row['code'] for row in result['findings']])

    def test_http200_homepage_title_is_not_article_acceptance(self):
        with patch.object(mod.requests, 'Session') as Session:
            response = Session.return_value.__enter__.return_value.get.return_value
            response.status_code = 200
            response.text = '<h1>Other article</h1><div>Sample</div><link rel="canonical" href="https://blog.ucarsea.com/">'
            self.assertFalse(mod.verify_live('sample', 'Sample')['public_verified'])

    def test_public_acceptance_requires_h1_and_exact_canonical(self):
        with patch.object(mod.requests, 'Session') as Session:
            response = Session.return_value.__enter__.return_value.get.return_value
            response.status_code = 200
            response.text = '<h1>Sample</h1><link rel="canonical" href="https://blog.ucarsea.com/sample/">'
            self.assertTrue(mod.verify_live('sample', 'Sample')['public_verified'])
            response.status_code = 403
            self.assertFalse(mod.verify_live('sample', 'Sample')['public_verified'])

    def test_build_failure_restores_only_own_edit(self):
        path = self.post(date='2026-10-20')
        before = path.read_text()
        def fake(repo, args, timeout=120):
            if args[:2] == ['npm', 'run']:
                raise RuntimeError('fixture build failed')
            return 'main' if args[1] == 'branch' else ''
        with patch.object(mod, 'run_cmd', side_effect=fake):
            result = mod.Publisher(self.repo, '2026-10-21').publish()
        self.assertEqual(result['status'], 'build_failed_no_publish')
        self.assertEqual(path.read_text(), before)

    def test_full_success_does_not_backdate_and_deduplicates_second_run(self):
        path = self.post(date='2026-10-20')
        commands = []
        def fake(repo, args, timeout=120):
            commands.append(args)
            if args[1] == 'branch': return 'main'
            if args[1] == 'rev-parse': return 'abc123'
            return ''
        with patch.object(mod, 'run_cmd', side_effect=fake), patch.object(mod, 'verify_live', return_value={'public_verified': True, 'http': 200}):
            first = mod.Publisher(self.repo, '2026-10-21').publish()
            second = mod.Publisher(self.repo, '2026-10-21').publish()
        self.assertEqual(first['status'], 'public_verified')
        self.assertEqual(second['status'], 'already_published_today')
        self.assertIn('pubDate: 2026-10-21', path.read_text())
        self.assertEqual(sum(command[1] == 'push' for command in commands), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
