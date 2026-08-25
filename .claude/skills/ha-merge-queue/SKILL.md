---
name: ha-merge-queue
description: Finds open Home Assistant pull requests that are genuinely ready to merge, checking CI, the merge-gate statuses, code-owner approval, merge conflicts, requested changes and unresolved review threads. Use when looking for PRs to merge, doing merge-queue triage, or asking for "quick wins" from the open PR backlog.
---

# Find Ready-to-Merge Pull Requests

Produce a shortlist of open PRs a maintainer can approve and merge immediately, plus a
short list of near-misses that each need one specific nudge. Default to 10 candidates
unless the user asks for a different number.

## Gather candidates

Search open PRs, excluding those that are structurally not mergeable:

```
repo:home-assistant/core is:open is:pr draft:false status:success -review:changes_requested
  -label:"awaiting-frontend" -label:"stale" -label:"cla-needed"
```

Add `label:"small-pr"` for quick wins, or `label:"code-owner-approved"` / `review:approved`
for PRs already carrying an approval. Run several searches and pool the results — no single
query surfaces everything.

The search index lags reality by hours. Treat `status:` as a rough filter, never as proof;
verify every finalist with the per-PR checks below.

## Verify each finalist

Check all five. A PR fails the shortlist if any one fails.

1. **Merge-gate statuses** — fetch the combined commit status. This is the cheapest and
   most informative call, and it is what actually blocks the merge button. Five contexts
   matter: `code-owner-approval` (required for Platinum integrations),
   `required-labels` (red when the author checked no "Type of change" box),
   `docs-missing` (red when a user-facing change has no documentation PR), `cla-bot`, and
   `blocking-label-awaiting-frontend`.

2. **Check runs** — the commit statuses do not cover GitHub Actions. Fetch the check runs
   and require every one to have reached an acceptable terminal result: `status` must be
   `completed`, and `conclusion` must be `success`, `skipped` or `neutral`. Everything else
   disqualifies — `failure`, `cancelled`, `timed_out`, `action_required` and `stale`, and
   any run still `queued` or `in_progress`. A green combined status sitting on top of a red
   or still-running test job is common, so the status list alone is never enough.

3. **Merge conflicts** — read `mergeable_state`. GitHub computes it asynchronously: a
   request that finds no cached answer returns `unknown` and starts the computation, and
   the request after that can still return `unknown`. Poll with bounded retries — a few
   attempts, pausing between them — and treat an `unknown` that never resolves as not
   ready, rather than assuming it is fine.
   - `clean` — approved and mergeable; merge now
   - `blocked` — mergeable, no conflict, waiting on an approving review (the normal state)
   - `dirty` — merge conflict. The author needs to merge `dev` into the branch. Do not tell
     them to rebase: `AGENTS.md` forbids rewriting history on a PR branch once the PR is
     open, because reviewers need to see what changed since their last review.
     `homeassistant/generated/integrations.json` conflicts constantly, so PRs adding
     integrations go stale fast.

4. **Review submissions** — fetch the reviews, not just the threads. A `CHANGES_REQUESTED`
   review is returned here and nowhere else, and a reviewer can request changes with only a
   top-level body and no inline comments — such a PR has zero open review threads and looks
   clean to the check above. Take the latest submission per reviewer: a standing
   `CHANGES_REQUESTED` that no later `APPROVED` from the same person supersedes disqualifies
   the PR, regardless of whether its inline threads have since been resolved — resolving a
   thread does not withdraw the review. Do not lean on the `-review:changes_requested`
   search qualifier instead — the
   index is stale, and `mergeable_state: blocked` does not distinguish "needs an approval"
   from "changes were requested".

5. **Review threads** — fetch review threads and read `is_resolved`. Judge a thread by
   whether it is resolved or substantively addressed, never by who wrote it: an unresolved
   finding from `copilot-pull-request-reviewer` is a bug report and can be a real defect,
   so read it on its merits before discounting it. Every thread still open counts against
   the PR until you have read it and concluded it needs no change — the question was
   answered, the suggestion was considered and declined, the point was fixed elsewhere in
   the diff. Say for each open thread what it is and why it does or does not block. Never
   discount one for the category it appears to fall into; an unaddressed defect is a
   blocker whether or not anyone is arguing about it.

## Report

Rank by how little work each PR needs: `clean` first, then `blocked` with everything else
green. For each PR give the number as a full markdown link, the integration, one line on
what it does, and its blocking state.

Then list the near-misses separately, each with the one action that unblocks it. The
recurring ones:

- A failing test unrelated to the diff — name the test, say re-run the job.
- `required-labels` red — name the label to add (`bugfix`, `new-feature`, …).
- Awaiting code-owner approval — name the code owner from `manifest.json`.
- A standing `CHANGES_REQUESTED` review — name the reviewer, and say what they asked for.
- `dirty` — the author must merge `dev` and regenerate any generated files.

Call out mismatches worth a maintainer's attention: a PR whose body declares a breaking
change but carries no `breaking-change` label will silently miss the release notes.

## IMPORTANT

- Only report in the CONSOLE. DO NOT ACT ON GITHUB — no comments, no reviews, no merges,
  no pushes to contributor branches. Per `AI_POLICY.md`, a human decides and acts.
- Never call a PR ready on green CI alone. Read the diff of every PR you shortlist; CI
  cannot tell you whether the change is correct or wanted.
