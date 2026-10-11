---
name: custom-integration-sources
description: Keep a local, searchable copy of the latest code of every HACS default custom integration, and use it to measure how a core change (deprecation, removal, rename, signature change) affects custom integrations. Use when the user asks which or how many custom integrations use something, wants to check custom integration impact, or asks to sync/update the custom integration sources.
---

# Custom integration sources

A local snapshot of every repository in the [HACS default integration list](https://github.com/hacs/default/blob/master/integration), at the HEAD of each default branch. There is no git history: each repo is one filtered tarball containing only `*.py` and `manifest.json` files (~1.3 GB for ~3,250 repos).

Layout: `.custom_integration_sources/<owner>/<repo>/...`, with `.custom_integration_sources/.state.json` mapping `owner/repo` to the synced commit SHA.

## Sync

Always sync before answering an impact question, so results reflect current code:

```bash
python3 .claude/skills/custom-integration-sources/scripts/sync.py
```

- Requires an authenticated `gh` (`gh auth status`), used only to resolve commit SHAs via GraphQL.
- Incremental: only repos whose HEAD changed are downloaded. A no-change run takes about a minute; the first run downloads everything (~10 minutes).
- Repos dropped from the HACS list are deleted. Repos that are deleted, private or empty are listed as `unavailable`.
- The directory is added to `.git/info/exclude` automatically; it must never be committed.
- Options: `owner/repo ...` to sync only some repos, `--force` to re-download everything, `--dest DIR` to use another location (for example a directory shared between worktrees), `--workers N` for download concurrency.

## Search

Run searches from the sources directory, so paths start with `<owner>/<repo>/`:

```bash
cd .custom_integration_sources
rg -l --glob '*.py' '<pattern>'
```

Fall back to `grep -rlE --include='*.py' '<pattern>' .` if `rg` is unavailable.

- Results include `tests/`, `scripts/` and vendored code. Restrict to shipped code with `--glob '*/custom_components/**'` when the question is about runtime impact.
- Text search over-matches (comments, strings, unrelated attributes with the same name). For anything that will be reported or used as a number, confirm each match with Python's `ast` module: for example, check that a name is used as an attribute of an entity subclass, or that a call actually passes the argument in question.
- One repo can contain several integrations; read the `domain` from `custom_components/<domain>/manifest.json` when reporting.

## Report

- Group results by `owner/repo`, with the integration domain and the matching files and lines.
- Link each match as `https://github.com/<owner>/<repo>/blob/<sha>/<path>#L<line>`, using the SHA from `.state.json` so links stay valid.
- Give totals: matching repos out of synced repos.
- The snapshot is the default branch HEAD, not the latest release HACS installs; say so if the distinction matters.
- Do not open issues, PRs or comments on custom integration repositories without the user reviewing each one first (see `AI_POLICY.md`).
