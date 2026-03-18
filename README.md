# hass-client

`hass-client` is a Python compatibility layer for Home Assistant that keeps the
`homeassistant.core.HomeAssistant` API surface available in a standalone Python
process while sourcing remote data from a Home Assistant websocket connection.

The current focus is the compatibility harness:

- Preserve `HomeAssistant`, `StateMachine`, `EventBus`, and `ServiceRegistry`
  semantics from core.
- Add an opt-in remote websocket client for state, service, and entity-registry
  sync.
- Run Home Assistant core tests against a `RemoteHomeAssistant` subclass by
  loading a pytest bridge instead of modifying the core checkout.

## Test Harness

This repository is set up for `uv`. Pin the local interpreter with:

```bash
uv python pin 3.14
```

Set up the repo-local Home Assistant core checkout with:

```bash
./script/setup
```

Update that checkout to the latest upstream `dev` branch with:

```bash
./script/bootstrap
```

Run the Home Assistant core compatibility suite with:

```bash
./script/test-core -q
```

By default this runs:

- `tests/test_*.py`
- `tests/helpers`

The compatibility harness expects Home Assistant core to live in `./core`.

Useful environment variables:

- `HASS_CLIENT_TOKEN`
- `HASS_CLIENT_SSL` (`true` / `false`)
- `HASS_CLIENT_SYNC_STATES`
- `HASS_CLIENT_SYNC_ENTITY_REGISTRY`
- `HASS_CLIENT_SYNC_REMOTE_SERVICES`
- `HASS_CLIENT_CORE_REPO`
- `HASS_CLIENT_CORE_BRANCH`
- `HASS_CLIENT_PYTHON`
- `HASS_CLIENT_TEST_TARGET`
  Use a whitespace-separated pytest target list, for example:
  `HASS_CLIENT_TEST_TARGET="tests/test_core.py tests/helpers/test_event.py"`

Remote sync is enabled only when `HASS_CLIENT_WS_URL` is set.
