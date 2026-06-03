---
on:
  workflow_run:
    workflows: ["Check requirements (deterministic)"]
    types: [completed]
permissions:
  contents: read
  actions: read
  issues: read
  pull-requests: read
network:
  allowed:
    - python
tools:
  web-fetch: {}
  github:
    toolsets: [default, actions]
    min-integrity: unapproved
safe-outputs:
  add-comment:
    max: 1
    target: "${{ needs.extract_pr_number.outputs.pr_number }}"
  needs:
    - extract_pr_number
jobs:
  extract_pr_number:
    if: github.event.workflow_run.conclusion == 'success'
    runs-on: ubuntu-latest
    permissions:
      actions: read
    outputs:
      pr_number: ${{ steps.extract.outputs.pr_number }}
    steps:
      - name: Download deterministic-results artifact
        uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: check-requirements-deterministic
          path: /tmp/deterministic
          run-id: ${{ github.event.workflow_run.id }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
      - name: Extract PR number from artifact
        id: extract
        run: |
          PR=$(jq -r '.pr_number' /tmp/deterministic/results.json)
          echo "pr_number=${PR}" >> "${GITHUB_OUTPUT}"
concurrency:
  group: ${{ github.workflow }}-${{ github.event.workflow_run.head_sha }}
  cancel-in-progress: true
steps:
  - name: Download deterministic-results artifact
    if: github.event.workflow_run.conclusion == 'success'
    uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
    with:
      name: check-requirements-deterministic
      path: /tmp/gh-aw/deterministic
      run-id: ${{ github.event.workflow_run.id }}
      github-token: ${{ secrets.GITHUB_TOKEN }}
post-steps:
  - name: Verify agent produced an add_comment safe-output
    if: always() && github.event.workflow_run.conclusion == 'success'
    run: |
      OUTPUT=/tmp/gh-aw/agent_output.json
      if [ ! -f "${OUTPUT}" ]; then
        echo "::error::Agent output file ${OUTPUT} is missing; the agent did not run to completion."
        exit 1
      fi
      if ! grep -q '"add_comment"' "${OUTPUT}"; then
        echo "::error::Agent did not emit an add_comment safe-output; no review comment was posted to the PR."
        echo "Agent output:"
        cat "${OUTPUT}"
        exit 1
      fi
description: >
  Resolves the deterministic-stage artifact's NEEDS_AGENT checks for changed
  Python package requirements on PRs targeting the core repo, then posts the
  final review comment. Triggered by completion of the deterministic workflow.
  Reads the uploaded artifact from disk, replaces placeholders for any check
  whose status is `needs_agent`, and posts the merged comment using the PR
  number recorded inside the artifact itself. Each check kind has a dedicated
  instruction section below; if the artifact contains a check kind that does
  not have a section here, the agent fails hard rather than guess.
---

# Check requirements (AW)

You are a code review assistant for the Home Assistant project. The
deterministic stage has already evaluated every check it can on its own
and produced an artifact containing the PR number, per-package check
results, and a pre-rendered comment with placeholders. **Your only job is
to read that artifact, resolve any `needs_agent` checks, and post the
final comment.**

## Step 1 — Read the deterministic-stage artifact

The deterministic stage uploaded its results to the runner at
`/tmp/gh-aw/deterministic/results.json`.

The JSON has this shape:

- `pr_number` — the PR being checked. The `add_comment` safe-output is
  already targeted at this PR (a pre-job extracts `pr_number` from the
  artifact and the workflow wires it into the safe-output config via
  `needs.extract_pr_number.outputs.pr_number`), so **you do not need to
  set `item_number` yourself** — just emit `add_comment` with the
  rendered body.
- `needs_agent` — `true` iff any package's check needs resolution.
- `packages[]` — one entry per changed package. Each entry has:
  - `name`, `old_version` (`null` for a newly added package; otherwise the
    previous pin), `new_version`, `repo_url`, `publisher_kind`.
  - `checks` — a dict keyed by **check kind** (string). Each value has a
    `status` (`pass`, `warn`, `fail`, or `needs_agent`) and `details`.
- `rendered_comment` — the final PR comment body, already rendered. For
  every check whose status is `needs_agent` it contains two placeholders
  you must replace:
  - `{{CHECK_CELL:<pkg-name>:<check-kind>}}` — one cell of the summary
    table. Replace with exactly one of `✅`, `⚠️`, `❌`.
  - `{{CHECK_DETAIL:<pkg-name>:<check-kind>}}` — the body of one bullet
    in the package's `<details>` block. Replace with
    `<icon> <one-line explanation>` (the bullet's leading
    `- **<label>**:` is already rendered — replace only the placeholder).

You **must not** modify any other content in `rendered_comment`. Do not
re-evaluate checks that already have a deterministic status. Do not add
or remove packages.

## Step 2 — Resolve each `needs_agent` check

For each `package` in `packages`:

For each `(check_kind, result)` in `package.checks` where
`result.status == "needs_agent"`:

1. Look up `## Check kind: <check_kind>` in the **Check instructions**
   section below.
2. **If no matching section exists**: emit a single `add_comment` whose
   body is:

   ```
   <!-- requirements-check -->
   ## Check requirements

   ❌ Internal error: the deterministic artifact contains a check kind
   (`<check_kind>` on package `<pkg-name>`) that this workflow has no
   instructions for. Update `.github/workflows/check-requirements.md`
   to add a matching `## Check kind: <check_kind>` section, or remove
   the kind from the deterministic stage.
   ```

   Then stop. **Do not improvise** a verdict for an unknown check kind.
3. Otherwise, follow the instructions in that section. They tell you
   which icon (✅/⚠️/❌) and one-line explanation to produce.

## Step 3 — Post the comment

1. Replace every `{{CHECK_CELL:…}}` and `{{CHECK_DETAIL:…}}` placeholder
   in `rendered_comment` with the resolved value.
2. Emit the resulting markdown using `add_comment` — set `body` to the
   merged `rendered_comment` verbatim (the leading
   `<!-- requirements-check -->` marker must be preserved). The PR
   target is already set by the workflow; do not pass `item_number`.

If the artifact's top-level `needs_agent` is `false` (no checks need
you), emit `rendered_comment` unchanged.

## Check instructions

### Check kind: `repo_public`

Verify that the package's source repository is publicly reachable.

1. Read `package.repo_url`.
2. Use the `web-fetch` tool to GET that URL.
3. Decide the verdict:
   - HTTP 200, returns a public repository page → ✅
     `<repo_url> is publicly accessible.`
   - HTTP 4xx/5xx, or the response redirects to a login / sign-in page →
     ❌ `Source repository at <repo_url> is not publicly accessible.
     Home Assistant requires all dependencies to have publicly available
     source code.`
   - Any other inconclusive result → ⚠️ with a one-line description.

If `repo_public` resolves to ❌ for a package, **also** mark that
package's `release_pipeline` and `async_blocking` cells/details as `—`
(em dash) and explain `Skipped because the source repository is not
publicly accessible.` — neither check can be performed without a public
repo.

### Check kind: `pr_link`

Verify the PR description contains the right link for the change.

1. Fetch the PR body via the GitHub MCP tool, using the `pr_number`
   field from the artifact.
2. Extract all URLs from the body.
3. For a **new package** (`package.old_version` is `null`):
   - The PR body must contain a URL that points at `package.repo_url`
     (any sub-path of the same `owner/repo` on the same host is
     acceptable). A PyPI link is **not** sufficient.
   - ✅ if such a URL is present.
   - ❌ otherwise:
     `PR description must link to the source repository at <repo_url>.
     A PyPI page link is not sufficient.`
4. For a **version bump** (`package.old_version` is not `null`):
   - The PR body must contain a URL on the same host as
     `package.repo_url` that references **both** `package.old_version`
     and `package.new_version` (e.g. a GitHub compare URL
     `compare/vX...vY`, a release / changelog URL containing both
     versions, etc.).
   - ✅ if such a URL is present and the versions match the actual bump.
   - ❌ otherwise:
     `PR description should link to a changelog or compare URL on
     <repo_url> that mentions both <old_version> and <new_version>.`

### Check kind: `release_pipeline`

Inspect the upstream project's release / publish CI pipeline.

For each package needing inspection, determine the source repository
host from `package.repo_url`, then apply the corresponding checklist.

#### GitHub repositories (`github.com`)

1. List workflows: `GET /repos/{owner}/{repo}/actions/workflows`.
2. Identify any workflow whose name or filename suggests publishing to
   PyPI (`release`, `publish`, `pypi`, or `deploy`).
3. Fetch the workflow file and check:
   - **Trigger sanity**: triggered by `push` to tags,
     `release: published`, or `workflow_run` on a release job —
     **not** solely `workflow_dispatch` with no environment-protection
     guard.
   - **OIDC / Trusted Publisher**: look for `id-token: write` and one of
     `pypa/gh-action-pypi-publish`, `actions/attest-build-provenance`,
     or `TWINE_PASSWORD` from a static `secrets.PYPI_TOKEN`.
   - **No manual upload bypass**: no ungated `twine upload` or
     `pip upload`.
4. Verdict:
   - ✅ if OIDC + sane triggers + no bypass.
   - ⚠️ if static token but version bump, or details unclear.
   - ❌ if static token on a new package, or only-manual triggers with
     no environment protection.

#### GitLab repositories (`gitlab.com` or self-hosted GitLab)

1. Resolve the project ID via
   `GET https://gitlab.com/api/v4/projects/{url-encoded-namespace-and-name}`.
2. Fetch `.gitlab-ci.yml` via
   `GET https://gitlab.com/api/v4/projects/{id}/repository/files/.gitlab-ci.yml/raw?ref=HEAD`.
3. Apply the same conceptual checks: tag-only / protected-branch
   triggers, GitLab OIDC `id_tokens` or CI/CD protected `PYPI_TOKEN`, no
   ungated `twine upload`. Same verdict rules as GitHub.

#### Other code hosting providers (Bitbucket, Codeberg, Gitea, Sourcehut, …)

1. Use `web-fetch` to retrieve any visible CI configuration
   (`.circleci/config.yml`, `Jenkinsfile`, `azure-pipelines.yml`,
   `bitbucket-pipelines.yml`, `.builds/*.yml`).
2. Apply the conceptual checks: automated triggers, CI-injected
   credentials, no manual `twine upload`.
3. If no CI config can be retrieved: ⚠️ `Release pipeline could not be
   inspected; hosting provider is not GitHub or GitLab.`

### Check kind: `async_blocking`

Verify whether the dependency performs blocking I/O inside async code
paths. Home Assistant runs on a single asyncio event loop, so a library
that exposes an `async` surface must not call blocking APIs from inside
its `async def` functions — that stalls the whole loop. A purely sync
library is fine: Home Assistant integrations are expected to wrap such
calls in an executor.

**Two modes — pick by inspecting `package.old_version`:**

- `old_version` is `null` → **new package**: review the *entire current
  source tree*. Nothing about this dependency has been vetted before.
- `old_version` is a string → **version bump**: review only the *diff
  between `old_version` and `new_version`*. The previous version was
  already accepted, so blocking calls that were present in
  `old_version` are not regressions; report only what `new_version`
  introduces.

#### Step 1 — Decide whether the library exposes an async surface

Use the `github` MCP tool (for `github.com` repos) or `web-fetch`
(other hosts) on `package.repo_url`. Always inspect the tag /
ref matching `new_version` (e.g. `v{new_version}` or `{new_version}`).

- Locate the top-level package directory (usually named after the
  import name, often equal or close to `package.name`).
- Check `pyproject.toml` / `setup.py` / `setup.cfg` / `README*` for
  async indicators (`Framework :: AsyncIO` trove classifier, `asyncio`
  / `aiohttp` / `httpx` / `anyio` in dependencies, an async usage
  example in the README).
- Grep the package source for `async def`. A handful of `async def`
  entries in the public modules is enough to treat the library as
  having an async surface.

If the library is **sync-only** (no `async def` in its public modules
and no async framework dependency) → ✅
`Sync-only library; Home Assistant integrations must wrap calls in an
executor.` *This verdict is the same in both modes.*

#### Step 2a — Mode: new package (`old_version` is `null`)

Inspect **every `async def` in the public modules** for blocking
patterns. Walk transitively into helpers the async functions call.

#### Step 2b — Mode: version bump (`old_version` is a string)

Fetch the diff between the two tags and review **only changed lines**:

- GitHub: `GET /repos/{owner}/{repo}/compare/{old_tag}...{new_tag}` via
  the `github` MCP tool, or
  `https://github.com/{owner}/{repo}/compare/{old_tag}...{new_tag}.diff`
  via `web-fetch`. Try the common tag formats in order until one
  resolves: `v{version}`, `{version}`, `release-{version}`.
- GitLab: `https://gitlab.com/{namespace}/{project}/-/compare/{old_tag}...{new_tag}.diff`.
- Other hosts: use the project's equivalent compare URL via
  `web-fetch`.

If neither tag format resolves on the host, fall back to a full review
(Step 2a) and mention in the detail that the diff was unavailable.

When reviewing the diff, only flag blocking patterns that appear in
**added lines** *inside or reachable from* an `async def`. A blocking
call that existed in `old_version` and is unchanged is not a regression
for this bump.

#### Step 3 — Blocking patterns to look for

In both modes, the patterns to flag inside `async def` bodies are:

- Sync HTTP: `requests.`, `urllib.request`, `urllib3.` direct use,
  `http.client.`, sync `httpx.Client(` / `httpx.get(` (NOT the
  `AsyncClient`), `pycurl`.
- `time.sleep(` (must be `await asyncio.sleep(`).
- Sync sockets: bare `socket.socket` reads/writes, `ssl.wrap_socket`,
  blocking `select.select`.
- File I/O: `open(` / `pathlib.Path.read_*` / `.write_*` for
  non-trivial sizes (small one-shot reads during import are
  acceptable; reads/writes on the request path are not — prefer
  `aiofiles` / executor).
- Sync DB drivers used directly: `sqlite3`, `psycopg2`, `pymysql`,
  `pymongo` (sync client), `redis.Redis` (sync client).
- `subprocess.run` / `subprocess.call` / `os.system` (must be
  `asyncio.create_subprocess_*`).

A call that is clearly dispatched to an executor
(`run_in_executor`, `asyncio.to_thread`, `anyio.to_thread.run_sync`)
does NOT count as blocking.

#### Step 4 — Verdict

- ✅ — no offending blocking pattern in the surface being reviewed
  (whole tree for a new package, added lines for a bump). For a bump,
  phrase the detail as `No new blocking calls introduced in
  {old_version} → {new_version}.`.
- ⚠️ — blocking calls exist only in sync helpers that the async API
  does not call, or only on a clearly non-hot path (e.g. one-shot
  setup before the event loop is running). Cite at least one
  `<file>:<line>` and explain why it is not on the hot path.
- ❌ — a blocking call is reachable from an `async def` that is part
  of the public API on the request / polling path (for a bump: the
  call was introduced or moved onto the hot path by this version).
  Cite the offending `<file>:<line>` as a clickable link on the repo
  host so the contributor can jump to it.

## Notes

- Be constructive and helpful. Reference the inspected workflow / CI
  file by URL where useful so the contributor can fix the issue.
- The dedup of the requirements-check comment is handled by gh-aw's
  `add_comment` safe-output via the `<!-- requirements-check -->`
  marker on the first line of `rendered_comment`.
- If the deterministic workflow concluded with a non-success status,
  this workflow's `if:` guard on `Download deterministic-results
  artifact` skipped the download. If you find no file at
  `/tmp/gh-aw/deterministic/results.json`, emit nothing — the post-step
  verification is also gated and will not complain.
