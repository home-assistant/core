---
name: ha-deprecation-cleanup
description: Finds Home Assistant deprecations whose breaks_in_ha_version has been reached on dev and prepares one cleanup branch per integration or core module and version, with the deprecated code removed, tests passing and a ready-to-paste PR description. Use when asked to scan for due or overdue deprecations, find breaks_in_ha_version cleanups, or create deprecation cleanup branches.
---

# Clean Up Due Deprecations

A deprecation is due when its `breaks_in_ha_version` X.Y is at or below the X.Y of the
current version on `dev` (`MAJOR_VERSION`/`MINOR_VERSION` in `homeassistant/const.py`). The
removal then ships in the release where it was promised.

Unless the user narrows it down, scan everything, then prepare branches for the groups
the user picks. When running unattended (for example in a routine), prepare a branch for
every group that qualifies.

## 1. Scan

Start from an up-to-date `dev`, then run from the repository root:

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
- `groups`: the due groups, one per integration or core module and `breaks_in_ha_version`
  X.Y, because each version is usually a separate deprecation that needs its own
  decision. Each has a `name` (integration domain, or module path such as
  `helpers/device_registry.py`), `kind` (`integration` or `core`), `version`, the `branch`
  name to use, and its `items` (file, line, version, source).
- `unresolved`: constants the script could not resolve, for example a name with
  different values in different files of the group. Read them by hand and add any that
  are due to the matching group.
- `passthrough`: values the script could not follow, such as an attribute, a variable
  unpacked from a tuple, or a helper with no callers in the same group. Helpers in
  `homeassistant/helpers/` just forward the value and can be ignored. For one inside an
  integration, find where the value comes from and check it by hand (for example
  `smartthings` keeps its versions in tuples in its entity descriptions).

Branch names are `deprecation-cleanup/<group-slug>-<X.Y>`. The script derives them, so the
same group gets the same name on every run.

## 2. Decide per group

Read the code and work out what is deprecated (a YAML option, a service, an entity or
attribute, a helper API, a repair issue, …) and what removing it means. Then pick one:

- **Skip**, with a short reason, if: it is the `kitchen_sink` demo (its repair issues exist
  to show the deprecation UI); or an open PR in `home-assistant/core` already removes it
  (search open PRs for the domain plus "deprecat" or "remove").
- **Needs decision**, with a one-line reason, when the removal is not mechanical: there is
  no clear replacement; the issue is a permanent warning that only reuses the field; it
  would need a config entry migration that can't be defined safely; or it is a core API
  that custom integrations still use widely (the `custom-integration-sources` skill can
  measure that). Don't create a branch.
- **Branch exists**: if the group's branch already exists on the push remote
  (`git ls-remote --heads <remote> <branch>`) or locally (`git branch --list <branch>`),
  don't touch it. Report whether a PR is open from it, whether it is only local and not
  pushed, and when its base is more than one release behind `dev`, say it needs a merge of
  `dev` or a fresh branch.
- **Prepare a branch** otherwise.

For every group, whatever the outcome, look for an open task issue in
`home-assistant/core` that covers the removal (for an integration, search its
`integration: <domain>` label plus words like remove, deprecated or the deprecated thing's
name). Report the issue if exactly one clearly matches, report all candidates if several
might, and ignore closed or unrelated issues. Searching is read-only: never comment on or
edit an issue. On a rate limit, wait for the reset and retry once.

## 3. Prepare a branch

Prepare each branch in its own worktree, so a group's changes never end up on another
group's branch. For each group:

1. `git worktree add -b <branch> ../deprecation-cleanup/<group-slug>-<X.Y> origin/dev`.
   This refuses to touch a branch that already exists. Work inside that directory and run
   `script/setup` there.
2. Remove the deprecated code path completely: the issue creation or warning,
   compatibility shims, old schema keys, constants, now-unused strings in `strings.json`
   (then run `python3 -m script.translations develop --integration <domain>`), and the
   tests and snapshots that only covered the deprecated behaviour. Update the remaining
   tests. Follow `CLAUDE.md` and the `ha-integration-knowledge` skill.
3. Validate: `uv run --no-sync pytest tests/components/<domain>` (or the matching core
   tests) and `uv run --no-sync prek run --files <changed files>`. If they still fail after
   a reasonable attempt, don't commit or push. Report the group as needs decision, with
   what failed and the worktree path, and leave the worktree for a human to look at. In
   an unattended run, remove it instead (`git worktree remove --force <path>` and
   `git branch -D <branch>`; the branch only has the uncommitted attempt).
4. Commit as "Remove deprecated <thing> from <domain>". In the body, name the
   `breaks_in_ha_version` and the PR that added the deprecation (find it with `git log -S`
   or `git blame`). Keep the PR template out of the commit message.
5. Write a ready-to-paste PR description following `.github/PULL_REQUEST_TEMPLATE.md`
   without removing anything: fill in the breaking change section, check "Breaking change"
   as the type, leave unchecked boxes in place, and put the task issue (if one was found)
   on the "fixes #" line. Don't commit it. It goes in the report.
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

Start with the version used and counts per outcome. Then, per group: name, kind, oldest due
version, outcome with its reason, branch and compare link if any, task issue if any, and
the PR description for each branch prepared in this run. Finish with unresolved items and
stale branches.

## IMPORTANT

- Never open pull requests, comment, review, or edit issues. Per `AI_POLICY.md`, a human
  reviews each branch and opens the PR.
- Only create new `deprecation-cleanup/` branches. Never force-push, never push to a branch
  that already exists on the remote, and never push to `dev`, `rc`, `master` or anything
  outside `deprecation-cleanup/`. Never delete a remote branch, or a local branch that
  this run didn't create.
- If a push is rejected (for example by a branch ruleset), stop pushing for the rest of
  the run and report why.
