# hass-client (v2)

Sandbox v2 client library. Independent `uv`-managed environment that depends
on `homeassistant` from the surrounding core checkout via
`[tool.uv.sources]`.

```bash
cd sandbox_v2/hass_client
uv sync
uv run pytest
```

Phase 0 ships an empty package. Phase 1 adds the spike module
(`hass_client.spike`) used to compare the two entity-bridge designs — see
[`../docs/entity-bridge-decision.md`](../docs/entity-bridge-decision.md).
