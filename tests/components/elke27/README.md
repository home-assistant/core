# Elke27 tests

This folder contains unit tests for the `elke27` integration plus opt-in live tests that talk to a real panel.

## Live tests

Live tests are gated to avoid unexpected traffic to a panel. To run them, set the environment variables and use the `live` marker.

### Required environment variables

- `ELKE27_LIVE=1`
- `ELKE27_LIVE_HOST`
- `ELKE27_LIVE_LINK_KEYS` (JSON object string with `tempkey_hex`, `linkkey_hex`, `linkhmac_hex`)

### Optional environment variables

- `ELKE27_LIVE_PORT` (defaults to `2101`)
- `ELKE27_LIVE_INTEGRATION_SERIAL` (defaults to `live`)
- `ELKE27_LIVE_PIN`

### Zone bypass live test

The bypass/unbypass test also requires:

- `ELKE27_LIVE_PIN`
- `ELKE27_LIVE_ZONE_ID`
- `ELKE27_LIVE_BYPASS_TOGGLE=1`
- `ELKE27_LIVE_EVENT_TIMEOUT` (defaults to `30` seconds)

### Run

```bash
pytest -m live tests/components/elke27/test_live.py
```
