# Build the worker with the matching Core checkout.

FROM python:3.14-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . /src
RUN pip install /src /src/packages/home-assistant-sandbox

FROM python:3.14-slim AS runtime

# tini forwards termination signals and reaps child processes.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

# Integration requirements are installed by the worker user.
RUN useradd --create-home --uid 10001 sandbox
COPY --from=builder --chown=sandbox:sandbox /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    SANDBOX_URL="stdio://" \
    SANDBOX_LOG_LEVEL="INFO"

COPY --chown=sandbox:sandbox packages/home-assistant-sandbox/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER sandbox
WORKDIR /home/sandbox

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
