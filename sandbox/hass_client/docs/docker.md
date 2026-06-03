# Sandbox v2 runtime — Docker image

A container image that runs the `hass_client` sandbox runtime
(`python -m hass_client.sandbox_v2`). Files:

- [`../Dockerfile`](../Dockerfile) — the image.
- [`../.dockerignore`](../.dockerignore) — local build-context excludes (see
  the context note below).
- [`../docker-entrypoint.sh`](../docker-entrypoint.sh) — expands the `SANDBOX_*`
  env vars into the runtime's CLI flags.
- [`../docker-compose.test.yml`](../docker-compose.test.yml) — the intended
  same-host unix-socket harness (forward-looking — see "Compose harness gap").

## Not a remote-ready artifact today

The runtime talks to main over the control channel. A genuinely remote sandbox
needs the **websocket transport (T4), which is DEFERRED**. The transports that
exist today — stdio and unix socket (T3) — run between main and a child process
it spawned *inside its own container*. So this image is **partly
forward-looking**: build it now to

- pin the image's dependencies, and
- package the runtime so it is ready when WS lands,

but do not mistake it for something that lets a separate sandbox container join
a remote main today. The transport caveat is repeated in the Dockerfile and the
compose file so it is hard to miss.

## What the image contains (and deliberately omits)

- **Base:** `python:3.14-slim` (HA's minimum is 3.14).
- **Two stages:** a builder installs `homeassistant` (from the local checkout)
  plus `hass_client` (and its `protobuf` + `aiohttp` deps) into a venv; the
  final stage copies only that venv. Keeps the image lean.
- **No pre-baked integration requirements.** The runtime pip-installs each
  integration's manifest requirements **on demand** at setup time
  (`async_process_requirements`). This is why the final image keeps `pip` and
  **needs network egress at runtime** (PyPI for deps, GitHub codeload for
  custom-integration code). This is what closes the pip/egress runtime gap that
  `plan-ephemeral-sources` flagged: the container is where pip + egress live.
- **No `git`.** Custom-integration code is fetched as a codeload **tarball**
  over aiohttp (`hass_client/sources.py`), not via a `git` clone — so no `git`
  binary is needed.
- **`build-essential` is optional** (commented out in the Dockerfile).
  Uncomment it only if the integrations under test pull requirements that have
  no pre-built wheel and must compile at runtime; baking it otherwise just
  bloats the image.
- **Non-root** (`sandbox`, uid 10001). The venv is `chown`ed to that user so
  the runtime's on-demand `pip install` can write into site-packages.
- **No persistent volumes / no state.** The runtime writes only an ephemeral
  config dir under the system temp dir; storage and restore-state route to main
  over the channel, and custom code is fetched at startup.
- **No `HEALTHCHECK`.** Readiness is the `Ready` frame on the control channel,
  which main supervises — there is no port/HTTP probe. Do not add one.
- **`tini` as PID 1** so `docker stop`'s SIGTERM reaches the runtime (a bare
  Python PID 1 would ignore it). Equivalent alternative: drop `tini` and run
  with `docker run --init` / compose `init: true`.

## Environment variables (entrypoint)

| Var                 | Required | Default     | Maps to       |
| ------------------- | -------- | ----------- | ------------- |
| `SANDBOX_NAME`      | yes      | —           | `--name`      |
| `SANDBOX_TOKEN`     | yes      | —           | `--token`     |
| `SANDBOX_URL`       | no       | `stdio://`  | `--url`       |
| `SANDBOX_LOG_LEVEL` | no       | `INFO`      | `--log-level` |

`SANDBOX_URL` selects the transport by scheme: `stdio://` (default),
`unix://<path>`, or `ws://…` (rejected — reserved for the deferred websocket
work).

## Build

The build context is the **repo root** (two levels up) because the image
installs the local `homeassistant` checkout:

```bash
# from the repo root
docker build -f sandbox_v2/hass_client/Dockerfile -t sandbox_v2_test .
```

### Build-context / `.dockerignore` note

Because the context is the repo root, Docker reads the **repo-root**
`.dockerignore` (which already excludes `.git`, `tests`, `.venv`, `docs`,
`config`, `__pycache__`). The `.dockerignore` next to the Dockerfile applies
only when the build context is `sandbox_v2/hass_client/` itself; it is kept for
that case and to document intent.

## Compose harness gap

`docker-compose.test.yml` models the intended same-host **unix-socket**
harness: a `main` service and a `sandbox` service sharing a volume for the
socket. **It does not run against today's manager.** Two manager capabilities
are missing (neither is hacked in):

1. **Configurable socket path.** The manager puts its unix socket in a private
   per-attempt tempdir (`tempfile.mkdtemp`), not on a shared path. The harness
   needs the socket on the shared volume (`/shared/sandbox.sock`); there is no
   option to point it there.
2. **Listen-only / attach mode.** The manager *spawns* the runtime as its own
   child (`create_subprocess_exec`) and listens for that child to dial back. It
   never waits for a separately started runtime to connect — so the `sandbox`
   service would never be used; `main` would spawn its own in-container child
   instead. A two-container split needs a manager mode that listens on a known
   socket and attaches to an externally launched runtime.

The genuinely remote variant arrives with the **websocket transport (T4)**,
which is deferred: with WS, `main` listens and the sandbox container dials in
over the network — no shared volume, no spawn. Until either (1)+(2) or WS
lands, the working model is single-container (main spawns its sandbox children
over stdio/unix inside one container).

Validate the compose file parses without running it:

```bash
docker compose -f sandbox_v2/hass_client/docker-compose.test.yml config
```
