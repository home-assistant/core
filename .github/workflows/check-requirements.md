---
on:
  workflow_run:
    workflows: ["Check requirements (deterministic)"]
    types: [completed]
permissions:
  contents: read
  actions: read
  pull-requests: read
network:
  allowed:
    - python
tools:
  web-fetch: {}
  github:
    toolsets: [repos, pull_requests]
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
  group: ${{ github.workflow }}-${{ github.event.workflow_run.id }}
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

You are a code-review assistant for Home Assistant. The deterministic
stage already evaluated every check it can and produced an artifact at
`/tmp/gh-aw/deterministic/results.json`. Your only job is to resolve any
`needs_agent` checks and post the rendered comment.

## Step 1 — Read the artifact

Read the JSON directly for the full schema. Key fields:

- `pr_number`, `needs_agent` (bool), `packages[]`, `rendered_comment`.
- Each `package`: `name`, `old_version` (`null` if new), `new_version`,
  `repo_url`, `publisher_kind`, `checks` (keyed by check-kind, each
  with `status` of `pass`/`warn`/`fail`/`needs_agent` and `details`).
- `rendered_comment` contains, for each `needs_agent` check, two
  placeholders to replace:
  - `{{CHECK_CELL:<pkg>:<kind>}}` → exactly one of `✅`, `☑️`, `⚠️`, `❌`.  The
    **`security`** check kind uses `☑️` instead of `✅` for the success
    case — see its section below for why.
  - `{{CHECK_DETAIL:<pkg>:<kind>}}` → `<icon> <one-line explanation>`
    (the bullet's `- **<label>**:` prefix is already rendered; replace
    only the placeholder).

Do not modify other content in `rendered_comment`, do not re-evaluate
deterministic checks, do not add or remove packages. If `needs_agent`
is `false`, emit `rendered_comment` unchanged.

## Step 2 — Resolve each `needs_agent` check

For each `(package, check_kind)` with `status == "needs_agent"`, find
the matching `### Check kind: <check_kind>` section below and follow
it. If no section matches, emit a single `add_comment` with:

```
<!-- requirements-check -->
## Check requirements

❌ Internal error: deterministic artifact contains an unknown check kind
(`<check_kind>` on `<pkg>`).
```

Then stop. Do not improvise a verdict.

## Step 3 — Post the comment

Replace every placeholder with the resolved value and emit
`rendered_comment` via `add_comment`. Preserve the leading
`<!-- requirements-check -->` marker. The PR target is already wired;
do not pass `item_number`.

## Check instructions

### Check kind: `repo_public`

`web-fetch` GET `package.repo_url`.
- 200 + public repo page → ✅ `<repo_url> is publicly accessible.`
- 4xx/5xx or login redirect → ❌ `Source repository at <repo_url> is
  not publicly accessible. Home Assistant requires dependencies to
  have publicly available source code.`
- Otherwise → ⚠️ with a one-line description.

If ❌, also mark this package's `release_pipeline` and `async_blocking`
cells/details as `—` and explain `Skipped because the source
repository is not publicly accessible.`.

### Check kind: `pr_link`

Fetch the PR body via the `pull_requests` MCP using `pr_number`. Extract URLs.

- **New package** (`old_version == null`): body must contain a URL
  pointing at `repo_url`'s `owner/repo` on the same host (any
  sub-path OK). PyPI is not sufficient.
  - ✅ if present; otherwise ❌ `PR description must link to the
    source repository at <repo_url>. A PyPI page link is not
    sufficient.`
- **Version bump**: body must contain a URL on the same host as
  `repo_url` that mentions **both** `old_version` and `new_version`
  (compare URL, changelog, release page).
  - ✅ if present and versions match; otherwise ❌ `PR description
    should link to a changelog or compare URL on <repo_url> that
    mentions both <old_version> and <new_version>.`

### Check kind: `release_pipeline`

Inspect the upstream's publish-to-PyPI CI. Host-specific lookup, same
rubric:

1. Locate the publish workflow / job (name or filename contains
   `release`, `publish`, `pypi`, or `deploy`).
   - GitHub: list `.github/workflows/` via the `repos` MCP, pick the
     promising file by name, fetch its contents.
   - GitLab: fetch `.gitlab-ci.yml` from the default ref via
     `https://gitlab.com/api/v4/projects/{id}/repository/files/.gitlab-ci.yml/raw?ref=HEAD`.
   - Other hosts: `web-fetch` an obvious CI config
     (`.circleci/config.yml`, `bitbucket-pipelines.yml`, etc.).
2. Apply this rubric:
   - **Trigger**: tag push / `release: published` / protected branch —
     not solely manual dispatch without an environment guard.
   - **Credentials**: OIDC (`id-token: write` +
     `pypa/gh-action-pypi-publish` or equivalent) preferred; static
     `PYPI_TOKEN` from a CI secret acceptable for a bump.
   - **No bypass**: no ungated `twine upload` / `pip upload`.
3. Verdict:
   - ✅ — OIDC + sane triggers + no bypass.
   - ⚠️ — static token on a bump, details unclear, or
     non-GitHub/GitLab host with limited CI visibility.
   - ❌ — static token on a new package, or manual-only triggers
     without environment protection.

### Check kind: `async_blocking`

Verify the dependency does not call blocking APIs inside `async def`
bodies. Home Assistant runs on a single asyncio loop, so blocking
calls from the async surface stall the whole loop. A purely sync
library is fine — integrations wrap its calls in an executor.

**Mode** (decided by `old_version`):
- `null` → new package: review the entire current source tree.
- string → version bump: review only the diff between the two tags.
  Blocking calls already present in `old_version` are not regressions.

**Step 1 — async surface?**

Fetch `pyproject.toml` / `setup.py` / `setup.cfg` / `README*` at the
tag matching `new_version` (try `v{version}`, `{version}`,
`release-{version}` — at most three attempts). Use the `repos` MCP for
github.com, `web-fetch` otherwise.

If sync-only (no `async def` in public modules; no
asyncio/aiohttp/httpx/anyio in deps; no `Framework :: AsyncIO`
classifier) → ✅ `Sync-only library; Home Assistant integrations must
wrap calls in an executor.` (Same verdict for both modes.)

**Step 2 — review the surface**

- New package: grep public modules for `async def`, inspect each
  async body and transitive helpers.
- Bump: fetch the compare diff
  (`/repos/{owner}/{repo}/compare/{old}...{new}` on GitHub, equivalent
  on GitLab/other hosts). Only flag patterns on **added** lines that
  are inside or reachable from `async def`. If no tag format resolves,
  fall back to a full review and note that the diff was unavailable.

**Blocking patterns to flag inside `async def`:**

- Sync HTTP: `requests.`, `urllib.request`, `urllib3.` direct,
  `http.client.`, sync `httpx.Client(` / `httpx.get(`, `pycurl`.
- `time.sleep(` (use `await asyncio.sleep(`).
- Sync sockets/SSL: bare `socket.socket` I/O, `ssl.wrap_socket`,
  blocking `select.select`.
- File I/O on the request path: `open(` /
  `pathlib.Path.read_*` / `.write_*` for non-trivial sizes (small
  one-shot reads during import are OK).
- Sync DB drivers: `sqlite3`, `psycopg2`, `pymysql`, sync `pymongo` /
  `redis.Redis`.
- `subprocess.run` / `subprocess.call` / `os.system`.

Calls dispatched to an executor (`run_in_executor`,
`asyncio.to_thread`, `anyio.to_thread.run_sync`) do **not** count as
blocking.

**Verdict:**

- ✅ — no offending pattern. Bumps: phrase as `No new blocking calls
  introduced in {old_version} → {new_version}.`.
- ⚠️ — blocking only in sync helpers the async API never calls, or
  clearly off the hot path (e.g. one-shot pre-loop setup). Cite at
  least one `<file>:<line>` and say why it's not hot.
- ❌ — blocking call reachable from a public `async def` on the
  request/polling path (bump: introduced or moved onto the hot path
  by this version). Cite the offending `<file>:<line>` as a clickable
  link on the repo host.

### Check kind: `security`

Perform a **baseline** scan of the upstream package source for obvious
supply-chain red flags. This is a cheap first pass, **not** a security
review, malware audit, or substitute for human judgement. A clean result
means "nothing obvious stood out in a quick scan", not "this package is
safe". The success icon for this check is `☑️` — **never** `✅` — to
make clear that a passing scan is not an endorsement.

If `repo_public` resolves to ❌ for the same package, mark `security`'s
cell and detail as `—` (em dash) and explain
`Skipped because the source repository is not publicly accessible.` —
the source cannot be fetched without a public repo.

**Step 1 — Fetch a representative slice of the source**

Use `package.repo_url` to locate the source.

- For **GitHub** repos:
  1. Resolve the default branch via `GET /repos/{owner}/{repo}`.
  2. List the tree with
     `GET /repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1`.
  3. Identify the package's actual Python module directory
     (`{package_name}/` or `src/{package_name}/`, normalising `-` ↔ `_`).
- For **GitLab** repos use the equivalent REST API calls; for any other
  host fall back to `web-fetch` of raw file URLs.

Fetch the **raw contents** of:

- `setup.py` if present — install-time code runs on every consumer
  machine.
- `pyproject.toml` — inspect `[build-system]` and any custom build
  backend.
- The package's `__init__.py`.
- Up to **8** additional Python files inside the package directory,
  prioritising files referenced from `entry_points`, plus any file whose
  name suggests bootstrap, loader, or self-update behavior
  (`update*.py`, `loader*.py`, `bootstrap*.py`, `_native.py`,
  `_post_install*.py`, etc.).

If the source tree is too large to inspect within the available API
budget, inspect at least `setup.py`, `pyproject.toml`, and the package's
`__init__.py`, then return ⚠️ with a note that only a partial scan was
performed.

**Step 2 — Patterns to flag**

Reason from principles, not a fixed checklist. For each fetched file,
ask: *would a well-behaved Python library that does what this package's
PyPI description claims to do need to do this?* If the answer is "no" or
"unclear", record a finding. The categories below describe the **shape**
of concerning behavior; the specific APIs, filenames, and storage keys
mentioned are illustrative examples — treat any equivalent construct
(including ones that did not exist when this workflow was written) the
same way.

For every finding include the file path, line number, a snippet
(≤ 120 chars), a permalink of the form
`https://github.com/{owner}/{repo}/blob/{sha}/{path}#L{line}` (or the
GitLab equivalent), and one sentence explaining why the behavior is out
of scope for the package's stated purpose.

1. **Reaches outside the package's declared scope into Home Assistant
   internals.** A third-party library should interact with Home
   Assistant only through the public, documented Python API it imports from the library
   — never by touching the filesystem of `config_dir` or by reading
   internal authentication / session state. Flag any code that opens,
   reads, writes, or resolves paths to artifacts it does not own
   (top-level YAML it did not create, anything under `.storage/`, files
   owned by other integrations / domains), or that reads tokens, refresh
   tokens, auth providers, or other internal session state. Examples
   like `secrets.yaml`, `.storage/auth*`, `hass.auth`, or
   `hass.config.path("secrets.yaml")` are illustrative — the principle
   is *out-of-scope access*, not a static list of names.
2. **Network input flows into an execution sink (download-and-execute).**
   Bytes obtained from a remote source must never reach an interpreter.
   Flag any data-flow path where the response body of a network call
   (any HTTP / WebSocket / raw-socket client, sync or async) ends up at
   *any* execution sink: `exec`, `eval`, `compile`, `marshal.loads`,
   `pickle.loads`, `types.FunctionType`,
   `importlib.util.spec_from_loader`, `subprocess.*`, `os.system`, shell
   pipelines such as `curl … | sh`, or a file that is subsequently
   imported or executed. The same applies to package-manager invocations
   (`pip install`, `pip download`, …) whose arguments are resolved from
   network responses at runtime.
3. **Build-time or install-time code is non-deterministic or non-local.**
   `setup.py`, `setup.cfg` `cmdclass`, custom PEP 517 backends, and any
   other build hook must be self-contained: they may only compile and
   copy files that ship in the source distribution. Flag any build-stage
   code that opens a network socket, shells out to external binaries,
   writes outside the build / install tree, or pulls in a build backend
   whose source is not on PyPI (e.g. referenced via Git URL or local
   path).
4. **Reads user secrets and combines them with an egress path.** The
   concerning shape is *secret-source → outbound-channel*, not any
   single API. Flag code that reads credential / authentication material
   from the host (environment variables that look like tokens or API
   keys, files under the user's home that store credentials, OS keychain
   APIs, browser-profile directories, Home Assistant token stores)
   **and** in the same code path sends that data to a destination the
   package does not need to talk to. Reading secrets alone is not
   enough; sending data out alone is not enough; the *combination* is
   the signal.
5. **Hides what it does from a reader.** Source that a maintainer cannot
   reasonably review is itself a smell. Flag any pattern where opaque
   data flows into an execution sink: large encoded / compressed / hex
   strings (decoded via `base64`, `codecs`, `zlib`, `lzma`,
   `bytes.fromhex`, or any future equivalent) passed to `exec` / `eval`
   / `compile` / `__import__`; identifiers assembled at runtime from
   non-literal pieces and then imported; or any other construct whose
   evident purpose is to make the real behavior unreadable.
6. **Hard-coded network destination that does not match the package's
   stated purpose.** Flag outbound URLs or hosts that do not appear in
   the package's PyPI `project_urls` and have no obvious connection to
   its function — especially short-link / paste services, ephemeral
   tunnels, raw IP addresses, or non-default ports against unknown hosts
   — and any network call originating from module top-level /
   `__init__.py` (which executes on import for every consumer).

If a behavior is clearly out of scope for the package's stated purpose
but does not fit any of the categories above, flag it under whichever
category fits best and explain in the finding. The list of categories is
meant to guide reasoning, not bound it.

**Verdict**

Aggregate the findings for the package and produce one of:

- `☑️ Baseline scan found nothing obvious in <list of inspected files>.
  This is not a security review — only the cheap checks were run.`
  Use `☑️` (**not** `✅`) so a passing scan is not read as an
  endorsement.
- `⚠️ <one-line summary>` when patterns were found that have plausible
  legitimate uses.
  Include the file path, line number, snippet, and permalink for each
  match in the bullet's detail so a human reviewer can decide.
- `❌ <one-line summary>` for patterns with no legitimate explanation
  for a Python dependency, for example: install-time network execution,
  decode-and-exec of opaque blobs, reads of `secrets.yaml` or
  `.storage/auth*`, or env-var / token exfiltration to an external host.
  Include the same file path / line / snippet / permalink detail.

Be precise. False positives are expected — when in doubt, prefer `⚠️`
with context over `❌`. This check is informational and never blocks the
workflow on its own; a human reviewer decides whether to merge.

## Notes

- Be constructive; reference the inspected file by URL when useful.
- Comment dedup is handled by gh-aw's `add_comment` safe-output via
  the `<!-- requirements-check -->` marker.
- If `/tmp/gh-aw/deterministic/results.json` is missing (upstream
  cancelled/failed), emit nothing — the post-step verification is
  gated and won't complain.
- The `security` check is a **baseline** scan, not a full security
  review. It is informational only — it surfaces findings for a human
  reviewer but never blocks the workflow on its own. The success icon
  is intentionally `☑️` (and *never* `✅`) so a passing scan does not
  read as an endorsement: it only means nothing obvious stood out.