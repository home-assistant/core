# Sandbox runtime image — runs the `hass_client` sandbox runtime.
#
# NOT a remote-ready artifact today. The runtime talks to main over the
# control channel; the only container-friendly transport that exists right now
# is a unix socket over a shared volume (transport T3). The websocket transport
# (T4) that a genuinely remote sandbox needs is DEFERRED, so this image is
# partly forward-looking: build it now to pin the image's deps and to exercise
# the runtime over a non-stdio transport on the same host. See docs/docker.md
# and docker-compose.test.yml for the transport caveat and the (currently
# blocking) manager gap for a two-container harness.
#
# Two-stage build keeps the final image small: the builder resolves and
# installs `homeassistant` + `hass_client` into a venv; the final stage copies
# only that venv.
#
# Standalone-image alternative (NOT what this file builds): instead of COPYing
# the repo and installing the local checkout, install a pinned
# `homeassistant==<ver>` from PyPI plus a pre-built `hass_client` wheel. The
# test image installs the local checkout so it always matches the surrounding
# core tree.

# ---------------------------------------------------------------------------
# Stage 1 — builder: install homeassistant + hass_client into a venv.
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build toolchain — OPTIONAL. A handful of integration requirements have no
# pre-built wheels for this platform and need a compiler to build at runtime.
# Baking it bloats the image, so it is left off by default; uncomment if the
# integrations under test pull such requirements. (`git` is deliberately NOT
# installed: custom-integration code is fetched as a codeload *tarball* via
# aiohttp — see hass_client/sources.py — not via a `git` clone.)
# RUN apt-get update \
#     && apt-get install -y --no-install-recommends build-essential \
#     && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# COPY the repo context (trimmed by .dockerignore) and install the local
# checkout: the repo root provides `homeassistant`, and ./sandbox/hass_client
# provides `hass-client-v2` (whose `homeassistant` dependency is already
# satisfied by the local install, plus the `protobuf` + `aiohttp` runtime deps).
#
# Integration requirements are deliberately NOT pre-baked here. The runtime
# pip-installs each integration's manifest requirements on demand at setup time
# (`async_process_requirements`) — which is exactly why the final image keeps
# pip and needs network egress at runtime.
COPY . /src
RUN pip install /src /src/sandbox/hass_client

# ---------------------------------------------------------------------------
# Stage 2 — runtime: copy the venv, drop privileges, run the runtime.
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS runtime

# tini as PID 1: a bare Python process running as PID 1 ignores signals whose
# default action would terminate it (e.g. SIGTERM from `docker stop`), so it
# would never shut down cleanly. tini reaps zombies and forwards signals to the
# runtime. (Alternative if you would rather not bake it: run with
# `docker run --init` / compose `init: true` and drop this apt layer.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

# The runtime pip-installs integration requirements at setup time, so the venv
# (its site-packages) must be writable by the non-root runtime user.
RUN useradd --create-home --uid 10001 sandbox
COPY --from=builder --chown=sandbox:sandbox /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    SANDBOX_URL="stdio://" \
    SANDBOX_LOG_LEVEL="INFO"

COPY --chown=sandbox:sandbox sandbox/hass_client/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# No VOLUME and no persistent state: the runtime keeps nothing on disk between
# runs. It writes only an ephemeral config dir under the system temp dir
# (TemporaryDirectory in hass_client/sandbox/__init__.py); storage/restore-state routes
# to main over the channel, and custom-integration code is fetched at startup.
#
# No HEALTHCHECK on purpose: readiness is the `Ready` frame the runtime sends
# on the control channel, which main already supervises — there is no HTTP/port
# probe to hit. Do NOT add one.

USER sandbox
WORKDIR /home/sandbox

# Exec-form entrypoint via tini → the entrypoint script `exec`s python, so
# signals reach the runtime and it shuts down cleanly. The script expands the
# SANDBOX_* env vars into the CLI flags (see docker-entrypoint.sh). The module
# stays `hass_client.sandbox` (the rename to `sandbox` is a separate plan).
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
