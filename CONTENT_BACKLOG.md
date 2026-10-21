# UCarsea Blog: current release queue

Updated 2026-10-21. Previous backlog is preserved in Git history and the dated repair backup. It was last maintained in May and did not describe the October queue.

## Restart queue

These are reviewed preparation/schedule states, not proof of publication. Consult `scripts/release-state.json`, `scripts/release-health.json` and the public URL for the actual result.

| Intended date (Beijing) | Slug | Review / initial state |
|---|---|---|
| 2026-10-21 | five-automatic-used-cars-shortlist-dealer-brief-2026 | ready / draft |
| 2026-10-22 | used-car-quote-validity-versus-stock-reservation-2026 | ready / draft |
| 2026-10-23 | used-car-document-request-redacted-review-2026 | ready / draft |
| 2026-10-24 | substitute-used-car-buyer-approval-checklist-2026 | ready / draft |

## Operating standard

- Existing daily release remains 10:00 Asia/Shanghai; at most one article per Beijing day. This is our editorial capacity, not a Google rule or ranking guarantee.
- Daily 08:10 SOP checks previous publication, current ready-draft count and errors. Refill a reviewed rolling queue toward seven when it reaches three or fewer; do not fill it with duplicate, unverified or obsolete articles.
- Weekly operational/SEO/GEO review checks actual public receipts and seven-day gaps, not scheduler configuration alone.
- Drafts require `reviewStatus: ready`, `reviewedOn: YYYY-MM-DD` and an applicable confirmed publication authorization recorded as `releaseApproved: true`. A ready review alone cannot publish unapproved content; this restart batch remains gated until Eric confirms it. Review stock, policy or pricing assertions against current evidence; remove unsupported claims rather than invent figures.
- Content should solve a distinct buyer question. There is no Google-required minimum word count. Useful examples, explicit uncertainty, a dated review and an appropriate inquiry route matter more than article length.
- No automatic claims of current inventory, fixed freight/duty rates, DDP, guaranteed admission, independent inspection, customer orders or earnings without applicable evidence and approval.
- New content uses current sourcing priorities: Cambodia, Kazakhstan and Nigeria; existing relevant markets remain. Moto material stays separate and requires its own product/use/brand evidence.
- Preserve previous articles and dates; do not bulk backfill missed days. Missed scheduled draft dates are changed to the actual release day when released, with the original intended date retained in the local journal.
- Local build, Git push, hosting deployment, public HTTP200, search indexing and AI citations are separate states. A scheduler exit code or crawler visit proves neither publication nor acquisition.

## Safe release commands

Read-only current queue/health:

```sh
/Volumes/Workspace/projects/ucarsea-leads/.venv/bin/python scripts/release_blog.py --check
```

Existing authorized daily publication:

```sh
bash scripts/release-next-draft.sh
```

Do not delete journals to force a retry. For `push_failed`, `push_unknown` or a pending commit, reconcile the same commit first. A pending deployment is rechecked without creating another article or repeating uploads. Notifications are handled in the existing Codex daily report and weekly review; the publisher writes local evidence, not duplicate Feishu pushes.
