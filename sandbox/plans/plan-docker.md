# Plan: Dockerfile for testing a hass_client sandbox

> Goal: a container image that runs the `hass_client` sandbox runtime, for
> testing the client against a main instance — and the basis for the ephemeral
> remote sandbox (`plan-ephemeral-sources.md`).

## Transport reality (read first)

A containerised sandbox talks to main over the network → it really wants the
**websocket transport, which is DEFERRED** (`plan-transport.md` T4). Until WS
lands, a container can only reach main via:
- **unix socket over a shared volume** (main + sandbox share a mounted dir;
  works for same-host docker testing), or
- the **in-process test plugin** (no container needed).

So this Dockerfile is partly forward-looking. Build it now for unix-socket
testing + to pin down the image (deps, git/pip for ephemeral fetch); it becomes
fully useful for remote testing when WS ships. Stated plainly so it isn't
mistaken for a remote-ready artifact today.

## Image design

Location: `sandbox_v2/hass_client/Dockerfile` (+ `.dockerignore`).

- **Base:** `python:3.14-slim` (HA min is 3.14).
- **System deps:** `pip` (present), `git` only if the git-clone fetch path is
  chosen (`plan-ephemeral-sources.md` leans tarball → may skip `git`); plus the
  build toolchain a handful of integration wheels need (`build-essential`) —
  keep optional/commented to keep the image small.
- **Python install:** the runtime needs `homeassistant` + `hass_client`. For a
  test image, COPY the repo and `pip install ./sandbox_v2/hass_client` (which
  pulls `homeassistant` via its path source). For a standalone image, install a
  pinned `homeassistant==<ver>` from PyPI + the built `hass_client` wheel.
- **Integration requirements:** do **not** pre-bake them. The runtime installs
  each integration's manifest requirements on demand via
  `async_process_requirements` (pip at setup time) — consistent with the
  ephemeral model. Image stays lean; needs pip + network at runtime.
- **Entrypoint:** `python -m hass_client.sandbox_v2` with args from env:
  `--name $SANDBOX_NAME --url $SANDBOX_URL --token $SANDBOX_TOKEN`
  (+ `--log-level`). (`--name` per fidelity-batch #2.)
- **Non-root user** for the runtime; **no persistent volumes** (the whole point
  is statelessness — storage routes to main, code is fetched at startup).
- Multi-stage: builder (resolve+install deps) → slim final (copy site-packages).
- Skip a Docker HEALTHCHECK — readiness is the `Ready` frame on the channel, not
  an HTTP/port probe; main already supervises readiness.

## Test harness (optional but useful)

`sandbox_v2/hass_client/docker-compose.test.yml`: a `main` service (HA core) and
a `sandbox` service (this image), sharing a volume for the **unix-socket**
transport, with `SANDBOX_URL=unix:///shared/sandbox.sock`. Lets CI exercise a
real cross-process sandbox over a non-stdio transport once T3 (unix socket)
lands. Document that the WS-based remote variant arrives with T4.

## Sequencing
- Depends on fidelity-batch **#2** (`--name`) for the entrypoint flag.
- Depends on transport **T3** (unix socket) to be exercisable cross-container;
  fully remote testing waits on **T4** (websocket).
- Pairs with `plan-ephemeral-sources.md` (git/tarball + pip at runtime).
