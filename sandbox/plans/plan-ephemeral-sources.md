# Plan: stateless sandboxes — push integration source on entry_setup

> User vision: sandboxes are truly ephemeral. They start up, connect to main,
> receive their config entries **plus where to get the integration code**, fetch
> it, set up, and hold no persistent state. Built-in integrations are sourced
> from the HA install (today's behaviour); **custom (HACS) integrations get a
> git URL + version/tag** pushed in so the sandbox clones them at startup.

## Why this completes the stateless story

Three kinds of state a sandbox could hold, and where each already lives:
- **Config** — pushed via `sandbox_v2/entry_setup` (`router.py:_entry_setup_payload`).
- **Storage / restore-state** — routed to main via `RemoteStore` (Phase 8).
- **Integration code** — the missing piece. Built-ins ride the `homeassistant`
  package; **custom integration code is the only stateful bit left.** Fetching
  it at startup from a main-supplied source makes the sandbox wipe-and-restart
  safe — the payoff the user described.

## Current state

- `_entry_setup_payload` (`homeassistant/components/sandbox_v2/router.py:186`)
  sends `entry_id, domain, title, data, options, source, unique_id, version,
  minor_version`. **No integration-source field.**
- Sandbox `entry_runner._handle_entry_setup` builds a `ConfigEntry` and calls
  `config_entries.async_setup(entry_id)`; HA's loader resolves the integration
  from the `homeassistant` package or `<config>/custom_components/<domain>`. The
  sandbox runs a bare HA in a **tempdir config_dir** (`sandbox.py:~139`), so a
  custom integration's code is **not present** there today → custom integrations
  can't actually load in a fresh sandbox. This plan fixes that.

## Design

### 1. Main attaches a source descriptor to entry_setup
Extend `_entry_setup_payload` with a `source` block:
```python
# built-in (today's behaviour, made explicit)
"integration_source": {"kind": "builtin"}
# custom (HACS)
"integration_source": {
    "kind": "git",
    "url": "https://github.com/owner/repo",
    "ref": "<exact commit sha>",   # resolved from the tag — see security
    "tag": "v1.2.3",               # human-readable, for logs
    "domain": "my_integration",
    "subdir": "custom_components/my_integration",  # path within the repo
}
```
Main decides built-in vs git from `Integration.is_built_in` (already used by the
classifier).

### 2. **Decision (2026-06-03): generic resolver hook (option c)**
Core exposes
`async_register_sandbox_source_resolver(callable)`; HACS (or any other
distribution mechanism) registers a resolver domain→source. Core ships a
no-op default (built-in only). Keeps core HACS-agnostic.

Options considered and rejected:
- (a) HACS-provided index — couples core to a HACS data shape.
- (b) Manifest convention — clean decoupling but requires HACS to write the
  manifest field; less flexible than (c).

### 3. Sandbox fetches before setup
In `entry_runner._handle_entry_setup`, before `async_setup`:
- `kind == "builtin"` → no-op (package provides it).
- `kind == "git"` → if `<config>/custom_components/<domain>` absent, fetch:
  - shallow-fetch the **exact sha** and export `subdir` into
    `<config>/custom_components/<domain>` (git or the GitHub codeload tarball —
    HACS uses release zipballs; tarball avoids a `git` binary dep).
  - **process-lifetime cache** keyed by `(url, ref)` so multiple entries of the
    same custom domain fetch once.
- Then `async_setup` runs; HA's loader discovers the custom_component and
  `async_process_requirements` pip-installs its manifest requirements (needs pip
  + network in the sandbox — see Runtime).

### 4. Security (supply-chain)
- **Pin to an exact commit sha, not a moving tag.** Main resolves tag→sha and
  sends the sha (`ref`); the sandbox verifies the fetched tree matches. Prevents
  a tag being re-pointed between resolution and fetch.
- Trust chain: the URL/version come from a resolver fed by what the user already
  installed via HACS — trust is inherited, not new. The sandbox running
  untrusted custom code is exactly the isolation boundary the sandbox exists for.
- Sandbox needs **network egress** (clone + pip). For the locked-down `custom`
  group this is expected; document that egress is required and consider an
  allow-list (github + PyPI) if egress filtering is ever added.

### 5. Runtime requirements
- Confirm the bare-HA sandbox runs `async_process_requirements` (pip) during
  `async_setup` and that it isn't disabled. Custom integrations frequently ship
  Python deps; without this they fail to import.
- The sandbox image/process therefore needs `pip` + network (and `git` if the
  git-clone path is chosen over tarball download). See `plan-docker.md`.

## Touch points
```
homeassistant/components/sandbox_v2/router.py     (+ integration_source in payload)
homeassistant/components/sandbox_v2/sources.py    (new — resolver registry + builtin default)
homeassistant/components/sandbox_v2/protocol.py   (document the new field; proto message when #3 lands)
sandbox_v2/hass_client/hass_client/entry_runner.py(fetch-before-setup)
sandbox_v2/hass_client/hass_client/sources.py     (new — git/tarball fetch + cache)
```

## Sequencing
- Independent of the fidelity batch. **Couples to the transport rewrite (#3):**
  the new `integration_source` becomes a typed field on the `EntrySetup` proto
  message — land it as plain dict first if this ships before #3, then fold into
  the proto in T2.
- Naturally pairs with the **deferred websocket transport** (a remote/
  containerised sandbox is the prime consumer of fetch-at-startup) and with
  `plan-docker.md` (the ephemeral container).

## Open decisions
- ~~Source-resolution mechanism: (a) HACS index / (b) manifest convention /
  (c) registered resolver hook~~ — **DECIDED 2026-06-03: (c) registered resolver hook.**
- Fetch mechanism: `git` shallow clone vs GitHub tarball download — **lean
  tarball** (no `git` binary dep; matches HACS).
- Cache scope: process-lifetime only (pure ephemeral) vs a bounded on-disk
  cache for faster respawns — **lean process-lifetime** to honour "stateless".

## Final phase — docs up to date
Close with the cross-cutting docs phase (`plan-v1-removal.md` Phase D): document
the `integration_source` field in `protocol.py`, the fetch-before-setup step in
the OVERVIEW entry-lifecycle section, the resolver-hook contract, and the
statelessness payoff in `CLAUDE.md`. Fix current-state docs; leave historical
`STATUS-phase-*` records intact.
