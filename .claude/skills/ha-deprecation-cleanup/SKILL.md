---
name: ha-deprecation-cleanup
description: Finds Home Assistant deprecations whose breaks_in_ha_version has been reached on dev and prepares one cleanup branch per deprecation, with the deprecated code removed, tests passing and a ready-to-paste PR description. Use when asked to scan for due or overdue deprecations, find breaks_in_ha_version cleanups, or create deprecation cleanup branches.
---

# Clean Up Due Deprecations

A deprecation is one deprecated thing, such as a YAML option, a service, an entity, or a
helper API parameter, with its own `breaks_in_ha_version`. Users are told about it with a
repair issue, a logged warning (`report_usage()`), or a deprecated constant or alias.

A deprecation is due when its `breaks_in_ha_version` X.Y is at or below the X.Y of the
current version on `dev` (`MAJOR_VERSION`/`MINOR_VERSION` in `homeassistant/const.py`). The
removal then ships in the release where it was promised.

Each deprecation gets its own decision and, when it is cleaned up, its own branch. Unless
the user narrows it down, scan everything, then prepare branches for the deprecations the
user picks. When running unattended (for example in a routine), prepare a branch for every
deprecation that qualifies.

## 1. Scan

Fetch the latest `dev` of `home-assistant/core` (for example `upstream/dev` when `origin`
is your fork) and check it out. Use that same ref, `<dev>` below, for every branch. Then
run from the repository root:

```bash
uv run --no-sync python3 ./.claude/skills/ha-deprecation-cleanup/scripts/find_due_deprecations.py [--version X.Y]
```

It finds `breaks_in_ha_version` keyword arguments and dict keys, plus the positional
version of `DeprecatedConstant`, `DeprecatedConstantEnum`, `DeprecatedAlias` and
`DeferredDeprecatedAlias`. Values held in an upper-case constant are resolved within the
file, or else in the same integration or core module when the name has only one value
there. When the value is a parameter of the enclosing function, such as a
`deprecate_entity(..., version="2026.9.0")` helper, it resolves each caller in the same
integration or module: the version the caller passes, or the parameter's default when it
passes none. Those items point at the call site. It prints JSON with:

- `current_version`: the X.Y compared against.
- `deprecations`: the due deprecations. Each has a `name` (integration domain, or module
  path such as `helpers/device_registry.py`), `kind` (`integration` or `core`), `version`
  (X.Y), the repair `issue_id` if it creates one, the `branch` name to use, and its
  `items` (file, line, version, source, issue_id). The script tells deprecations apart by
  integration or module, version and repair issue id. The varying parts of an issue id,
  such as an entry id in an f-string, are left out.
- `unresolved`: constants the script could not resolve, for example a name with
  different values in different files of the integration. Read them by hand and add any
  that are due.
- `passthrough`: values the script could not follow, such as an attribute, a variable
  unpacked from a tuple, a helper with no callers in the same integration or module, or a
  function name defined more than once there. Find where each value comes from and check
  it by hand. Most of them just forward a caller's argument, like
  `helpers/issue_registry.py` and `helpers/frame.py`, and need nothing. Others hold fixed
  versions the script can't read, like the tuples in `smartthings` entity descriptions or
  `_DEPRECATED_DEVICE_INFO_PARAMETERS` in `helpers/device_registry.py`. Add those that are
  due.

Branch names are `deprecation-cleanup/<slug>-<X.Y>-<issue_id>`, or
`deprecation-cleanup/<slug>-<X.Y>` when there is no repair issue. The slug is the name in
lowercase with `.py` dropped and other characters than letters, digits and `_` replaced by
`-`, so `helpers/device_registry.py` becomes `helpers-device_registry`. The script derives
the names from the deprecation alone, so the same deprecation gets the same name on every
run.

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
  to show the deprecation UI); or an open PR in `home-assistant/core` already removes it
  (search open PRs for the domain plus "deprecat" or "remove").
- **Needs decision**, with a one-line reason, when the removal is not mechanical: there is
  no clear replacement; the issue is a permanent warning that only reuses the field; it
  would need a config entry migration that can't be defined safely; or it is a core API
  that custom integrations still use widely (the `custom-integration-sources` skill can
  measure that). Don't create a branch.
- **Branch exists**: if a branch for this deprecation already exists on the push remote
  or locally, don't touch it. Look for every branch of the integration and version
  (`git ls-remote --heads <remote> 'deprecation-cleanup/<slug>-<X.Y>*'` and
  `git branch --list 'deprecation-cleanup/<slug>-<X.Y>*'`), since a branch made for the
  same deprecation can have another suffix, and check its diff to see what it removes.
  Report whether a PR is open from it, whether it is only local and not pushed, and when
  its base is more than one release behind `dev`, say it needs a merge of `dev` or a fresh
  branch.
- **Prepare a branch** otherwise.

For every deprecation, whatever the outcome, look for an open task issue in
`home-assistant/core` that covers the removal (for an integration, search its
`integration: <domain>` label plus words like remove, deprecated, the repair issue id or
the deprecated thing's name). Report the issue if exactly one clearly matches, report all
candidates if several might, and ignore closed or unrelated issues. Searching is
read-only: never comment on or edit an issue. On a rate limit, wait for the reset and
retry once.

## 3. Prepare a branch

Prepare each branch in its own worktree, so one deprecation's changes never end up on
another's branch. For each deprecation:

1. `git worktree add -b <branch> ../<branch> <dev>`, with the `dev` ref you scanned. This
   refuses to touch a branch that already exists. Work inside that directory and run
   `script/setup` there.
2. Remove the deprecated code path completely: the repair issue or warning,
   compatibility shims, old schema keys, constants, now-unused strings in `strings.json`
   (then run `python3 -m script.translations develop --integration <domain>`), and the
   tests and snapshots that only covered the deprecated behaviour. Update the remaining
   tests. Leave other deprecations in the same integration alone. Follow `CLAUDE.md` and
   the `ha-integration-knowledge` skill.
3. Validate: `uv run --no-sync pytest tests/components/<domain>` (or the matching core
   tests) and `uv run --no-sync prek run --files <changed files>`. If they still fail after
   a reasonable attempt, don't commit or push. Report the deprecation as needs decision,
   with what failed and the worktree path, and leave the worktree for a human to look at.
   In an unattended run, remove it instead (`git worktree remove --force <path>` and
   `git branch -D <branch>`; the branch only has the uncommitted attempt).
4. Commit as "Remove deprecated <thing> from <domain>". In the body, name the
   `breaks_in_ha_version` and the PR that added the deprecation (find it with `git log -S`
   or `git blame`). Keep the PR template out of the commit message.
5. Write a ready-to-paste PR description following `.github/PULL_REQUEST_TEMPLATE.md`,
   leaving unchecked boxes in place and putting the task issue (if one was found) on the
   "fixes #" line. When users have to change something, check "Breaking change" and fill
   in the breaking change section: what breaks, how to fix it and why. Removing a YAML
   import whose deprecation period has ended is not a breaking change, because the
   deprecation already announced it: check "Code quality improvements" and remove the
   breaking change section, as the template allows. Don't commit the description. It goes
   in the report.
6. Push only if the user (or the routine prompt) asked for it, to the remote they named,
   for example the user's fork, or `origin` for maintainers who keep branches upstream.
   Use a plain `git push <remote> <branch>`. The compare link is
   `https://github.com/home-assistant/core/compare/dev...<branch>?expand=1` for an upstream
   branch, or `https://github.com/home-assistant/core/compare/dev...<owner>:<repo>:<branch>?expand=1`
   for a fork.
7. Remove the worktree with `git worktree remove <path>`. The branch stays.

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
