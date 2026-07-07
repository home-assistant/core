# STATUS — plan-docker (test Dockerfile + unix-socket compose harness)

**One-line:** Shipped the multi-stage `python:3.14-slim` runtime image for the
`hass_client` sandbox + docs + a forward-looking unix-socket compose harness.
The image is correct and lean; the two-container compose harness does **not**
run against today's manager (it spawns its own child runtime rather than
attaching to an external one) — documented precisely as a small follow-up, not
hacked. Could not build/parse with Docker (no daemon/CLI on this box); validated
by review + `sh -n` + YAML parse. prek clean.

## Commits (not pushed — parent pushes)

| SHA | Subject |
|-----|---------|
| `1224f16df1e` | `sandbox_v2: test Dockerfile + unix-socket compose harness` |
| `<this commit>` | `sandbox_v2: docker tracker tick + STATUS` |

The plan file was **not** modified.

## Files added/changed

- `sandbox_v2/hass_client/Dockerfile` (new) — the image.
- `sandbox_v2/hass_client/.dockerignore` (new) — local build-context excludes
  (see context caveat below).
- `sandbox_v2/hass_client/docker-entrypoint.sh` (new) — expands `SANDBOX_*`
  env into the runtime CLI flags and `exec`s the module.
- `sandbox_v2/hass_client/docker-compose.test.yml` (new) — intended same-host
  unix-socket harness (forward-looking; see gap below).
- `sandbox_v2/hass_client/docs/docker.md` (new) — full docs.
- `sandbox_v2/hass_client/README.md` — Docker pointer section (replaced the
  stale "Phase 0 ships an empty package" line).
- `sandbox_v2/CLAUDE.md` — repo-layout + tests pointers to the image.
- `sandbox_v2/plans/whats-changed.md` — Test-Dockerfile box `[ ]`→`[x]`
  + SHA `1224f16df1e`.

## Image design

- **Base:** `python:3.14-slim` (HA min is 3.14; pyproject `requires-python
  >=3.14.2`).
- **Two stages:**
  - *builder* — `python -m venv /opt/venv`, then
    `pip install /src /src/sandbox_v2/hass_client`. `/src` (the repo root,
    added via `COPY`) installs the **local** `homeassistant` checkout; the second
    path installs `hass-client-v2` (its `homeassistant` dep already satisfied,
    plus `protobuf==6.32.0` + `aiohttp`).
  - *runtime* — copies only `/opt/venv` (chowned to the runtime user), adds
    `tini`, drops to a non-root user.
- **Installed:** `homeassistant` core + `hass_client` + their base deps. **NOT
  installed:** integration manifest requirements (the runtime pip-installs them
  on demand at setup via `async_process_requirements`) and `git`.
- **Entrypoint:** `tini -- docker-entrypoint.sh`, which `exec`s
  `python -m hass_client.sandbox_v2 --name $SANDBOX_NAME --url $SANDBOX_URL
  --token $SANDBOX_TOKEN --log-level $SANDBOX_LOG_LEVEL`. Module name unchanged
  (no `sandbox` rename — out of scope).
- **Non-root:** user `sandbox` (uid 10001); the venv is chowned so the
  runtime's on-demand `pip install` can write into site-packages.
- **No VOLUME / no state:** the runtime writes only an ephemeral
  `TemporaryDirectory` under the system temp dir (`hass_client/sandbox.py`);
  storage/restore-state routes to main; custom code is fetched at startup.
- **No HEALTHCHECK** (commented why): readiness is the `Ready` frame on the
  channel, supervised by main — no port/HTTP probe.

### Deliberately NOT baked

- Integration requirements (runtime pip, on demand).
- `git` (see below).
- `build-essential` — left commented; a toggle for integrations whose wheels
  must compile at runtime, otherwise it just bloats the image.

## Was `git` needed?

**No.** Custom (HACS) integration code is fetched as a **codeload tarball**
over `aiohttp` (`hass_client/sources.py` → `_default_fetch` /
`https://codeload.github.com/<owner>/<repo>/tar.gz/<ref>`), not via a `git`
clone. No `git` binary is required, so it is omitted.

## Could it be built?

**No — there is no Docker daemon or CLI on this machine** (`docker` /
`docker compose` / `hadolint` all absent). So:

- `docker build …` — **not run.**
- `docker compose … config` — **not run.** Instead validated the compose file
  is well-formed YAML with `python -c "yaml.safe_load(...)"` → valid.
- `hadolint` — **not available**, so no Dockerfile lint. Reviewed by hand
  against the plan/brief constraints.
- Entrypoint script `sh -n` → OK (shellcheck not installed).

Recommend a manual `docker build -f sandbox_v2/hass_client/Dockerfile -t
sandbox_v2_test .` (context = repo root) on a box with a daemon before relying
on the image. The one build risk worth watching: `pip install /src` building
the local `homeassistant` wheel and pulling its base deps (expected; that is
the image's bulk).

## Compose harness shape + the socket-path / spawn gap

`docker-compose.test.yml` models the intended **same-host unix-socket** harness:
a `main` service + a `sandbox` service sharing a named volume (`/shared`) for the
socket, with `SANDBOX_URL=unix:///shared/sandbox.sock`. **It is forward-looking
and does not run against today's manager.** Two manager gaps, neither hacked:

1. **Socket path is not configurable.** `SandboxProcess._run_one_unix`
   (`homeassistant/components/sandbox_v2/manager.py:370`) puts the socket in a
   private per-attempt `tempfile.mkdtemp(...)/control.sock`, not on a shared
   path. The harness needs it on the shared volume; there is no option for that.
2. **Spawn, not attach (the deeper gap).** The manager **spawns the runtime as
   its own child** (`create_subprocess_exec`, manager.py:388) and then listens
   for *that child* to dial back. It never waits for a separately started
   runtime to connect — so the compose `sandbox` service would never be used;
   `main` would spawn its own in-container child instead. A real two-container
   split needs a manager mode that listens on a known socket and **attaches** to
   an externally launched runtime.

So a cross-container harness needs (1)+(2), or the **websocket transport (T4)**
(deferred), where `main` listens and the sandbox dials in over the network (no
shared volume, no spawn). Today's working model is single-container: main spawns
its sandbox children over stdio/unix inside one container. All of this is
documented in `docs/docker.md` ("Compose harness gap") and in prominent comments
in the compose file itself, so the file is not mistaken for a working harness.

**Follow-up (small):** add a manager "listen-only + configurable shared socket
path" mode (or land WS/T4) to make the two-container harness real. The compose
file is the ready-made template for when that lands.

## How this closes ephemeral-sources' pip/egress follow-up

`STATUS-plan-ephemeral-sources.md` follow-up #2 flagged that the bare-HA sandbox
must run `async_process_requirements` (pip) for custom integrations that ship
Python deps and needs network egress (GitHub + PyPI), which was unvalidated
there. This image is the answer: the final stage keeps `pip` (in the venv,
writable by the non-root user) and is documented to require **network egress at
runtime** — the container is where pip + egress live. (Still not *exercised*
end-to-end here, since there is no daemon to run it; the image is built to
provide the capability the follow-up named.)

## Build-context / `.dockerignore` caveat

The documented build uses the **repo root** as context (the image installs the
local `homeassistant`), so Docker reads the **repo-root** `.dockerignore` (which
already excludes `.git`, `tests`, `.venv`, `docs`, `config`, `__pycache__`) — I
did **not** modify that core file. The `.dockerignore` next to the Dockerfile
applies only when the build context is `sandbox_v2/hass_client/` itself; it is
kept per the brief and to document intent, and is self-sufficient for that case.

## Signal handling / tini

A bare Python process as PID 1 ignores default-action signals (e.g. SIGTERM
from `docker stop`), so it would never shut down cleanly. The image bakes
**`tini`** as PID 1 (forwards signals; the entrypoint `exec`s python so the
runtime is tini's direct child). Documented alternative: drop tini and run with
`docker run --init` / compose `init: true` (the compose file also sets
`init: true` on the sandbox service as belt-and-braces). One small apt layer
(`tini`) is the only system package added.

## prek result

`uv run prek run --files <7 touched files>` → codespell, yamllint, prettier all
**Passed**; ruff/mypy/pylint/hassfest skipped (no matching files). No prettier
reformat needed (files already conformant). "don't commit to branch" passed
(on `sandbox`, not `dev`).

## Anything weird / gaps

- **The compose harness can't run today** — see the spawn-not-attach gap above.
  This is the main caveat. The Dockerfile + docs that ARE correct shipped; the
  harness ships as a documented template + follow-up, per the brief's fallback.
- **No daemon to build/verify** — image correctness rests on review, not a real
  build. Flagged above with the one build risk to watch.
- **tree-vs-ref verification** of fetched custom code remains as
  ephemeral-sources noted (out of scope here).
- whats-changed Test-Dockerfile box ticked (`1224f16df1e`).
