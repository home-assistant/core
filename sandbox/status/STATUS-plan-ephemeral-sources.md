# STATUS — plan-ephemeral-sources (stateless sandboxes)

**One-line:** Shipped green — main now attaches a typed `IntegrationSource`
to `entry_setup` (builtin no-op, or a sha-pinned git source), and the sandbox
fetches custom (HACS) code into `<config>/custom_components/<domain>` before
`async_setup`. Custom code is the last stateful bit; sandboxes are now
wipe-and-restart safe. Both suites green, prek + drift clean.

## Commits (not pushed — parent pushes)

- `d4b7aef732f` — `sandbox_v2: stateless sandboxes — push integration source on entry_setup`
  (proto + resolver + wire + fetch + tests).
- `<this commit>` — docs + tracker + STATUS.

## Proto change

Added to `sandbox_v2/proto/sandbox_v2.proto`:

```proto
message IntegrationSource {
  string kind = 1;    // "builtin" | "git"
  string url = 2;     // git-only
  string ref = 3;     // exact commit sha
  string tag = 4;     // human-readable, logs only
  string domain = 5;
  string subdir = 6;  // path within the repo
}
```

and `IntegrationSource integration_source = 10;` on `EntrySetup` (next free
field number; 1–9 were taken). Regenerated both `_pb2.py` + `_pb2.pyi`
mirrors via the isolated-venv `generate.sh`; the two mirrors are byte-identical
to each other. **Registry unchanged**: `IntegrationSource` is a nested field on
an existing frame message (`EntrySetup`), not a new top-level wire type, so
`messages.py`'s `REGISTRY` needed no entry (confirmed).

## Resolver contract (core side — `homeassistant/components/sandbox_v2/sources.py`)

- `async_register_sandbox_source_resolver(hass, resolver) -> unregister` —
  `@callback`. Stores resolvers in
  `hass.data[HassKey("sandbox_v2_source_resolvers")]` (a list, consulted in
  registration order; returns an unregister callback). A resolver is
  `Callable[[str], IntegrationSourceDict | None]`.
- `async_resolve_integration_source(hass, domain) -> pb.IntegrationSource` —
  built-ins short-circuit to `{kind: "builtin"}` via `Integration.is_built_in`
  (no resolver consulted). For a custom integration, the registered resolvers
  are consulted in order; first non-`None` wins. **No resolver / all return
  `None` → raises `SandboxSourceError`** (a custom integration cannot run in a
  stateless sandbox without a source — surfaced, not silently fallen back).
- Default (no resolver registered) is therefore builtin-only, as specified.

## Tag→sha pinning — where it happens

Core performs **no network I/O**, so it cannot itself turn a tag into a sha.
The contract delegates the pin to the resolver: the resolver MUST return `ref`
as an exact commit sha (HACS already knows the sha of the installed version);
`tag` is logs-only. `_git_source_from_dict` **enforces** this — a git source
without `ref` raises `SandboxSourceError("…must pin the version to an exact
commit sha")`, so main never ships a sandbox a moving reference. This is the
one deviation from the brief's literal "main resolves tag→sha": main *requires*
the sha rather than resolving it, because resolving would mean a network call
in core. Documented in the resolver docstring + `sources.py` module docstring.

## Fetch + cache (sandbox side — `sandbox_v2/hass_client/hass_client/sources.py`)

- `async_ensure_integration_source(config_dir, source, *, fetch=None)`:
  - `kind in ("", "builtin")` → no-op.
  - `kind == "git"` → if `<config_dir>/custom_components/<domain>/manifest.json`
    is absent, download the tarball for the exact `ref` and extract the repo's
    `subdir` into the dest.
- **Fetch mechanism:** GitHub codeload tarball
  (`https://codeload.github.com/<owner>/<repo>/tar.gz/<ref>`), no `git` binary
  dependency (matches HACS). The download primitive `(url, ref) -> bytes` is
  **injected** — default does a one-shot `aiohttp` GET (imported lazily);
  tests pass a local stub.
- **Cache:** module-level `_TARBALL_CACHE: dict[(url, ref) -> bytes]` guarded
  by an `asyncio.Lock`, **process-lifetime only** (nothing survives a process
  restart → honours "stateless"). Multiple entries from the same repo download
  once.
- Wired into `EntryRunner._handle_entry_setup` **before**
  `config_entries.async_setup`, using `self.hass.config.config_dir`.
  `EntryRunner.__init__` gained an optional `fetch=` for test injection.

## Verification of the fetched tree

The codeload tarball for a sha is content-addressed by GitHub (the sha *is* the
identity), so the transport already binds bytes→ref. On top of that the
extractor: rejects path-traversal members (anything resolving outside dest),
skips non-file members (symlinks/devices), requires ≥1 file under
`<top>/<subdir>/`, and **requires `manifest.json`** in the dest afterwards
(raises otherwise). It does **not** recompute the git tree hash to assert it
equals `ref` — that would mean reimplementing git's tree-hashing, which is more
than the "at minimum non-empty + manifest.json" bar the brief set. Noted as the
weaker-than-ideal spot.

## Test results (exact)

- HA core: `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **201 passed, 2 warnings**. New this plan: `test_sources.py` (7 resolver
  tests) + 2 `_entry_setup_payload` tests in `test_router.py`. (The rest of
  the delta from T2's 189 is the T3 unix-transport suite that landed between.)
- Client: `uv run pytest sandbox_v2/hass_client/ -q` → **70 passed, 1 warning**.
  New this plan: `test_sources.py` (8 fetch tests).
- `uv run prek run --files <13 touched files>` → ruff/ruff-format/codespell/
  prettier/mypy/pylint all pass.
- Drift guard: `bash sandbox_v2/proto/check_drift.sh` → "gencode matches
  sandbox_v2.proto."
- `grep -rn "integration_source" sandbox_v2/proto/sandbox_v2.proto` → present
  (`IntegrationSource integration_source = 10;`).

**No test hits the network.** Every fetch in `test_sources.py` (both sides)
uses an in-memory local tarball fixture / stub `fetch` primitive; the default
`aiohttp` path is never exercised by a test. Resolver tests use mocked
integrations (`mock_integration`), no real loading.

## Doc updates

- `protocol.py` (HA side) — documented the `integration_source` field on the
  `entry_setup` entry. Client `protocol.py` defers to the HA catalogue, unchanged.
- `OVERVIEW.md` — new "Integration source — fetch before setup (stateless)"
  section; entry-lifecycle note that `EntryRunner` fetches before setup.
- `CLAUDE.md` — new "Stateless sandboxes — integration source" section: the
  resolver-hook contract, the sha-pin rule, and the statelessness payoff, plus
  the pip/egress runtime gap as a follow-up.
- `architecture.html` — light-touch: entry-lifecycle line + a stateless
  fetch-before-setup subsection.
- `whats-changed.md` — "Custom (HACS) integrations are fetched at startup"
  `[ ]`→`[x]` + SHA `d4b7aef732f`.

## Anything weird / follow-ups

1. **Tree-vs-ref verification is weaker than a full git-tree-hash check** (see
   above): we trust GitHub's content-addressed codeload URL + assert a
   non-empty tree with `manifest.json`. Sufficient for the threat model the
   plan describes (the sha is pinned on the wire; the sandbox is the isolation
   boundary for untrusted custom code) but not a cryptographic tree match.
2. **`async_process_requirements` (pip for custom deps) is NOT confirmed to run
   in the bare-HA sandbox.** The sandbox client disables nothing — the normal
   `config_entries.async_setup` → `async_process_deps_reqs` →
   `async_process_requirements` path is intact, so it *would* attempt a pip
   install — but whether `pip` + network egress (GitHub + PyPI) are actually
   available in the sandbox process is unverified here and untestable without a
   real environment. A custom integration that ships Python deps would fetch
   its code fine but fail to import its deps until this is resolved. **This is
   the plan's §"Runtime requirements" gap — left as a follow-up that pairs with
   `plan-docker.md` (the ephemeral container that provides pip + egress).** Per
   the brief, the testable wire + fetch are shipped; this runtime gap is flagged,
   not faked.
3. The fetch holds `_CACHE_LOCK` across the network download, serializing
   concurrent fetches from different repos. Deliberate (prevents duplicate
   concurrent downloads of the same `(url, ref)`); startup fetches are few and
   one-shot, so the serialization cost is negligible.
