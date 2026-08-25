---
name: ha-merge-queue
description: Finds open Home Assistant pull requests that are genuinely ready to merge, checking CI, the merge-gate statuses, code-owner approval, merge conflicts and unresolved review threads. Use when looking for PRs to merge, doing merge-queue triage, or asking for "quick wins" from the open PR backlog.
---

# Find Ready-to-Merge Pull Requests

Produce a shortlist of open PRs a maintainer can approve and merge immediately, plus a
short list of near-misses that each need one specific nudge. Default to 10 candidates
unless the user asks for a different number.

## Gather candidates

Search open PRs, excluding those that are structurally not mergeable:

```
repo:home-assistant/core is:open is:pr draft:false status:success -review:changes_requested
  -label:"awaiting-frontend" -label:"needs-more-info" -label:"stale" -label:"cla-needed"
```

Add `label:"small-pr"` for quick wins, or `label:"code-owner-approved"` / `review:approved`
for PRs already carrying an approval. Run several searches and pool the results — no single
query surfaces everything.

The search index lags reality by hours. Treat `status:` as a rough filter, never as proof;
verify every finalist with the per-PR checks below.

## Verify each finalist

Check all four. A PR fails the shortlist if any one fails.

1. **Merge-gate statuses** — fetch the combined commit status. This is the cheapest and
   most informative call, and it is what actually blocks the merge button. Five contexts
   matter: `code-owner-approval` (required for Gold and Platinum integrations),
   `required-labels` (red when the author checked no "Type of change" box),
   `docs-missing` (red when a user-facing change has no documentation PR), `cla-bot`, and
   `blocking-label-awaiting-frontend`.

2. **Check runs** — the commit statuses do not cover GitHub Actions. Fetch the check runs
   and look for any job with conclusion `failure`. Ignore `skipped`. A green combined
   status with a red test job is common.

3. **Merge conflicts** — read `mergeable_state`. GitHub computes it lazily: the first
   request usually returns `unknown` and kicks off the computation, so **request it a
   second time** and use that value.
   - `clean` — approved and mergeable; merge now
   - `blocked` — mergeable, no conflict, waiting on an approving review (the normal state)
   - `dirty` — merge conflict; the author must rebase. `homeassistant/generated/integrations.json`
     conflicts constantly, so PRs adding integrations go stale fast.

4. **Review threads** — fetch review threads and read `is_resolved`. Only unresolved
   threads from humans block. Resolved threads, and long chains from
   `copilot-pull-request-reviewer`, do not. Watch for an unresolved thread that is really
   an answered question versus one that is an open design debate — say which it is.

## Report

Rank by how little work each PR needs: `clean` first, then `blocked` with everything else
green. For each PR give the number as a full markdown link, the integration, one line on
what it does, and its blocking state.

Then list the near-misses separately, each with the one action that unblocks it. The
recurring ones:

- A failing test unrelated to the diff — name the test, say re-run the job.
- `required-labels` red — name the label to add (`bugfix`, `new-feature`, …).
- Awaiting code-owner approval — name the code owner from `manifest.json`.
- `dirty` — the author must merge `dev` and regenerate any generated files.

Call out mismatches worth a maintainer's attention: a PR whose body declares a breaking
change but carries no `breaking-change` label will silently miss the release notes.

## IMPORTANT

- Only report in the CONSOLE. DO NOT ACT ON GITHUB — no comments, no reviews, no merges,
  no pushes to contributor branches. Per `AI_POLICY.md`, a human decides and acts.
- Never call a PR ready on green CI alone. Read the diff of every PR you shortlist; CI
  cannot tell you whether the change is correct or wanted.
