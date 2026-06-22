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
  gate:
    # Skip the (token-spending) agent when no tracked requirement file changed
    if: github.event.workflow_run.conclusion == 'success'
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      pull-requests: read
    outputs:
      skip: ${{ steps.gate.outputs.skip }}
    steps:
      - name: Download deterministic-results artifact
        uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: check-requirements-deterministic
          path: /tmp/gate
          run-id: ${{ github.event.workflow_run.id }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
      - name: Decide whether requirements changed since the last comment
        id: gate
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          PR=$(jq -r '.pr_number' /tmp/gate/results.json)
          HEAD=$(jq -r '.head_sha // empty' /tmp/gate/results.json)
          if [ -z "${HEAD}" ]; then
            echo "Artifact has no head_sha; running the agent."
            exit 0
          fi
          # Recover the commit recorded in the most recent requirements-check
          # comment from the "Checked at commit" link
          PRIOR=$(gh api --paginate "repos/${GITHUB_REPOSITORY}/issues/${PR}/comments" \
            --jq '.[] | select(.body | contains("<!-- requirements-check -->")) | .body' \
            | grep -oiE '/commit/[0-9a-f]{40}' \
            | grep -oiE '[0-9a-f]{40}' | tail -1 || true)
          if [ -z "${PRIOR}" ]; then
            echo "No previous comment with a recorded commit; running the agent."
            exit 0
          fi
          if [ "${PRIOR}" = "${HEAD}" ]; then
            echo "Head ${HEAD} unchanged since the last comment; skipping the agent."
            echo "skip=true" >> "${GITHUB_OUTPUT}"
            exit 0
          fi
          # List files changed between the recorded commit and the current head.
          # Tracked patterns mirror script/check_requirements/diff.py TRACKED_PATTERNS.
          CHANGED=$(gh api "repos/${GITHUB_REPOSITORY}/compare/${PRIOR}...${HEAD}" \
            --jq '.files[].filename' 2>/dev/null) || {
            echo "Could not compare ${PRIOR}...${HEAD}; running the agent."
            exit 0
          }
          TRACKED=$(printf '%s\n' "${CHANGED}" \
            | grep -Ex 'requirements.*\.txt|homeassistant/package_constraints\.txt' || true)
          if [ -z "${TRACKED}" ]; then
            echo "No tracked requirement files changed since ${PRIOR}; skipping the agent."
            echo "skip=true" >> "${GITHUB_OUTPUT}"
          else
            echo "Tracked requirement files changed since ${PRIOR}; running the agent:"
            printf '%s\n' "${TRACKED}"
          fi
  extract_pr_number:
    needs: gate
    if: needs.gate.outputs.skip != 'true' && github.event.workflow_run.conclusion == 'success'
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
  - `{{SUMMARY}}` → the single top-of-comment summary line, present only
    when at least one check needed resolving. Fill it **after** resolving
    every check, based on the final cell verdicts (see Step 3).

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

If a `{{SUMMARY}}` placeholder is present, replace it last, once every
`{{CHECK_CELL:…}}` is resolved:
- `All requirements checks passed. ✅` — when every check cell across all
  packages is `✅` or `☑️` (treat `—`/skipped as not a problem).
- `⚠️ Some checks require attention — see the details below.` — when any
  cell is `⚠️` or `❌`.

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

**Baseline** scan of the upstream source for obvious supply-chain red
flags — a cheap first pass, **not** a security review or malware audit.
A clean result means "nothing obvious stood out", not "this package is
safe". The success icon is `☑️` — **never** `✅` — so a passing scan is
not read as an endorsement.

If `repo_public` resolves to ❌ for the same package, mark `security`'s
cell and detail as `—` and explain `Skipped because the source
repository is not publicly accessible.` — the source cannot be fetched.

**Step 1 — Fetch a representative slice**

Locate the source from `package.repo_url`.

- GitHub: resolve the default branch (`GET /repos/{owner}/{repo}`), list
  the tree (`GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1`),
  find the module dir (`{name}/` or `src/{name}/`, normalising `-` ↔ `_`).
- GitLab: equivalent REST calls. Other hosts: `web-fetch` raw file URLs.

Fetch the **raw contents** of `setup.py` (install-time code runs on every
consumer), `pyproject.toml` (`[build-system]` / custom backend), the
package's `__init__.py`, and co — prioritising `entry_points` targets, plus any name suggesting
bootstrap / loader / self-update (`update*.py`, `loader*.py`,
`bootstrap*.py`, `_native.py`, `_post_install*.py`, …).

If the tree is too large for the API budget, inspect at least `setup.py`,
`pyproject.toml`, and `__init__.py`, then return ⚠️ noting the partial scan.

**Step 2 — Patterns to flag**

Reason from principles, not a fixed checklist: for each file ask *would a
well-behaved library doing what this package's PyPI description claims
need to do this?* If "no" or "unclear", record a finding. The categories
describe the **shape** of concerning behavior; the named APIs, filenames,
and keys are illustrative — treat any equivalent construct (including ones
that did not exist when this was written) the same way.

For every finding include the file path, line number, a snippet
(≤ 120 chars), a permalink
(`https://github.com/{owner}/{repo}/blob/{sha}/{path}#L{line}` or the
GitLab equivalent), and one sentence on why it is out of scope.

1. **Reaches into Home Assistant internals.** A library should touch HA
   only through its documented Python API — never the `config_dir`
   filesystem or internal auth / session state. Flag code that opens,
   reads, writes, or resolves paths to artifacts it does not own
   (top-level YAML it did not create, anything under `.storage/`, other
   integrations' files) or reads tokens / refresh tokens / auth providers
   (e.g. `secrets.yaml`, `.storage/auth*`, `hass.auth`). The principle is
   *out-of-scope access*, not a static list of names.
2. **Network input flows into an execution sink (download-and-execute).**
   Flag any data-flow from a network response body (any HTTP / WebSocket /
   raw-socket client, sync or async) to an execution sink: `exec`, `eval`,
   `compile`, `marshal.loads`, `pickle.loads`, `types.FunctionType`,
   `importlib.util.spec_from_loader`, `subprocess.*`, `os.system`, shell
   pipelines (`curl … | sh`), or a file later imported / executed — plus
   package-manager calls (`pip install` / `download`) with args resolved
   from network responses at runtime.
3. **Build / install-time code is non-deterministic or non-local.**
   `setup.py`, `setup.cfg` `cmdclass`, custom PEP 517 backends, and other
   build hooks must only compile and copy files shipped in the sdist. Flag
   build-stage code that opens a socket, shells out, writes outside the
   build / install tree, or pulls a build backend not on PyPI (Git URL /
   local path).
4. **Reads secrets and combines them with an egress path.** The shape is
   *secret-source → outbound-channel*. Flag code that reads credential
   material (token-like env vars, credential files under the user's home,
   OS keychain APIs, browser-profile dirs, HA token stores) **and** in the
   same path sends it to a destination the package needn't talk to.
   Reading or sending alone is not enough — the *combination* is the signal.
5. **Hides what it does.** Flag opaque data flowing into an execution
   sink: large encoded / compressed / hex strings (`base64`, `codecs`,
   `zlib`, `lzma`, `bytes.fromhex`, or any equivalent) passed to `exec` /
   `eval` / `compile` / `__import__`; identifiers assembled at runtime
   then imported; or any construct whose evident purpose is to make the
   behavior unreadable.
6. **Hard-coded network destination off-purpose.** Flag outbound URLs or
   hosts absent from the package's PyPI `project_urls` with no obvious
   connection to its function — short-link / paste services, ephemeral
   tunnels, raw IPs, non-default ports against unknown hosts — and any
   network call at module top-level / `__init__.py` (runs on import for
   every consumer).

A clearly out-of-scope behavior that fits none of the above: flag under
the closest category and explain. The categories guide reasoning, not bound it.

**Verdict**

Aggregate the findings into one of:

- `☑️ Baseline scan found nothing obvious in <list of inspected files>.
  This is not a security review — only the cheap checks were run.`
  Use `☑️` (**not** `✅`) so a passing scan is not read as an endorsement.
- `⚠️ <one-line summary>` — patterns with plausible legitimate uses;
  include path / line / snippet / permalink per match for the reviewer.
- `❌ <one-line summary>` — patterns with no legitimate explanation
  (install-time network execution, decode-and-exec of opaque blobs, reads
  of `secrets.yaml` / `.storage/auth*`, token exfiltration to an external
  host); same detail.

Be precise. False positives are expected — when in doubt prefer `⚠️` with
context over `❌`. This check is informational and never blocks the
workflow on its own; a human reviewer decides whether to merge.

## Notes

- Be constructive; reference the inspected file by URL when useful.
- Comment dedup is handled by gh-aw's `add_comment` safe-output via
  the `<!-- requirements-check -->` marker.
- If `/tmp/gh-aw/deterministic/results.json` is missing (upstream
  cancelled/failed), emit nothing — the post-step verification is
  gated and won't complain.