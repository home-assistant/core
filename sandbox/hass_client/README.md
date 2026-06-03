# hass-client (v2)

Sandbox v2 client library. Independent `uv`-managed environment that depends
on `homeassistant` from the surrounding core checkout via
`[tool.uv.sources]`.

```bash
cd sandbox_v2/hass_client
uv sync
uv run pytest
```

## Docker

A container image runs the sandbox runtime (`python -m hass_client.sandbox_v2`)
for testing the client against main — see [`docs/docker.md`](docs/docker.md) for
how to build it, the env vars, and the transport caveat (unix socket today,
websocket later). It is partly forward-looking: not a remote-ready artifact
today. The accompanying `docker-compose.test.yml` captures the intended
same-host unix-socket harness but does not run against today's manager (gaps
documented in `docs/docker.md`).
