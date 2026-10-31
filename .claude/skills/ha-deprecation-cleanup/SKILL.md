---
name: ha-deprecation-cleanup
description: Finds Home Assistant deprecations whose breaks_in_ha_version has been reached on dev and prepares one cleanup branch per deprecation, with the deprecated code removed, tests passing and a ready-to-paste PR description. Use when asked to scan for due or overdue deprecations, find breaks_in_ha_version cleanups, or create deprecation cleanup branches.
---

# Clean Up Due Deprecations

Each deprecation is marked with its own `breaks_in_ha_version`. It is due when that X.Y is
at or below the X.Y of the current version on `dev` (`MAJOR_VERSION`/`MINOR_VERSION` in
`homeassistant/const.py`).

Decide on each deprecation separately, and clean up each one in its own branch. Unless the
user narrows it down, scan everything, then prepare branches for the deprecations the user
picks. When running unattended (for example in a routine), prepare a branch for every
deprecation that qualifies.

## 1. Scan

Fetch the latest `dev` of `home-assistant/core` (for example `upstream/dev` when `origin`
is your fork) and create a detached worktree of it, so the current working tree is left
alone. Use that same ref for every branch. Then run from the root of that worktree:

```bash
uv run --no-sync python3 ./.claude/skills/ha-deprecation-cleanup/scripts/find_due_deprecations.py [--version X.Y]
```

The script's output needs a few notes:

- Each entry in `deprecations` is one deprecation to check, with the name of the branch to
  create for it in `branch`.
- `unresolved` lists constants the script could not resolve. Check them by hand and add
  any that are due.
- `passthrough` lists values the script could not follow. Most just forward a caller's
  argument, like `helpers/issue_registry.py` and `helpers/frame.py`, and need nothing.
  Others hold fixed versions the script can't read, like the tuples in `smartthings`
  entity descriptions or `_DEPRECATED_DEVICE_INFO_PARAMETERS` in
  `helpers/device_registry.py`. Add those that are due.

## 2. Check each deprecation

Read the code and work out what is deprecated and what removing it means. The script's
split is a starting point:

- Items without an issue id (a logged warning, a constant) can belong to a deprecation
  that also has a repair issue. Clean them up together.
- Two issue ids can be one deprecation, for example the success and failure issues of
  one YAML import. Clean them up together on the branch of the first one the script
  lists.

Then pick one outcome per deprecation:

- **Skip**, with a short reason, if: it is the `kitchen_sink` demo (its repair issues exist
  to show the deprecation UI); or an open PR in `home-assistant/core` already removes it.
- **Needs decision**, with a one-line reason, when the removal is not mechanical: there is
  no clear replacement; the issue is a permanent warning that only reuses the field; it
  would need a config entry migration that can't be defined safely; or it is a core API
  that custom integrations still use widely (the `custom-integration-sources` skill can
  measure that). Don't create a branch.
- **Branch exists**: if a branch for this deprecation already exists on the push remote
  or locally, don't touch it. Branches made for the same deprecation can have another
  suffix, so look for every branch that starts with the script's branch name up to and
  including the version, and check its diff. Report whether a PR is open from it, whether
  it is only local, and whether its base is more than one release behind `dev`.
- **Prepare a branch** otherwise.

For every deprecation, look for an open task issue in `home-assistant/core` that covers
the removal. Report it if exactly one clearly matches, and list the candidates if several
might. Searching is read-only: never comment on or edit an issue.

## 3. Prepare a branch

For each deprecation to clean up, create the branch from the script's output in its own
new worktree, so one deprecation's changes never end up on another's branch.

1. Remove the deprecated code path completely. Leave other deprecations in the same
   integration alone. Follow the `ha-integration-knowledge` skill.
2. Run the tests for the integration or core module and the linters on the changed
   files. If they still fail after a reasonable attempt, don't commit or push. Report the
   deprecation as needs decision, with what failed and the worktree path, and leave the
   worktree for a human to look at, or remove it and its branch in an unattended run.
3. Commit as "Remove deprecated <thing> from <domain>". In the body, name the
   `breaks_in_ha_version` and the PR that added the deprecation. Keep the PR template out
   of the commit message.
4. Write a ready-to-paste PR description following `.github/PULL_REQUEST_TEMPLATE.md`,
   leaving unchecked boxes in place and putting the task issue (if one was found) on the
   "fixes #" line. When users have to change something, check "Breaking change" and fill
   in the breaking change section: what breaks, how to fix it and why. Removing a YAML
   import whose deprecation period has ended is not a breaking change, because the
   deprecation already announced it: check "Code quality improvements" and remove the
   breaking change section, as the template allows. Don't commit the description. It goes
   in the report.
5. Push only if the user (or the routine prompt) asked for it, to the remote they named,
   for example the user's fork, or `origin` for maintainers who keep branches upstream.
   Use a plain `git push <remote> <branch>`, and give the compare link to `dev` of
   `home-assistant/core` in the report.
6. Remove the worktree. The branch stays.

## 4. Stale branches

List the `deprecation-cleanup/*` branches on the push remote. A branch is stale when no PR
is open from it and either its deprecation is gone from `dev` or its PR was closed. Report
them for a human to delete.

## Report

Start with the version used and counts per outcome. Then, per deprecation: name, kind,
version, repair issue id if any, what is deprecated, outcome with its reason, branch and
compare link if any, task issue if any, and the PR description for each branch prepared
in this run. Finish with unresolved items and stale branches.

## IMPORTANT

- Never open pull requests, comment, review, or edit issues. Per `AI_POLICY.md`, a human
  reviews each branch and opens the PR.
- Only create new `deprecation-cleanup/` branches. Never force-push, never push to a branch
  that already exists on the remote, and never push to `dev`, `rc`, `master` or anything
  outside `deprecation-cleanup/`. Never delete a remote branch, or a local branch that
  this run didn't create.
- If a push is rejected (for example by a branch ruleset), stop pushing for the rest of
  the run and report why.
