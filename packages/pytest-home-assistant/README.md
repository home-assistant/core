# pytest-home-assistant

Pytest fixtures and helpers for testing Home Assistant integrations. This package
contains the shared testing tools used by Home Assistant Core, with the goal of
making those same tools available to third-party integration authors.

Use these tools to create a Home Assistant instance for a test, mock configuration
entries and external services, simulate events, and check integration behavior.
The Python import namespace is `pytest_homeassistant`.

## Current status

**This package is not yet ready for external consumption.** It is being extracted
from Home Assistant Core and currently requires a Core development checkout. It
can be built as a wheel and source distribution, but standalone use and publishing
are not yet supported.

Runtime dependencies and automatic pytest plugin registration are not yet
declared. Some helpers also depend on Core's test data, configuration, and
historical recorder migration schemas. Installing the wheel alone does not
provide a working test environment for a custom integration.

The helpers evolve alongside Core. For now, use them with the Core checkout they
come from; compatibility across Home Assistant versions is not guaranteed.

## What's included

| Module | Purpose |
| --- | --- |
| `pytest_homeassistant.plugins` | Shared fixtures and pytest hooks, including `hass`, HTTP and WebSocket clients, registry fixtures, and mocks for storage, networking, and authentication. |
| `pytest_homeassistant.common` | Helpers such as `MockConfigEntry`, fixture file loaders, event capture, service mocks, and simulated time changes. |
| `pytest_homeassistant.components.common` | Shared assertions for entities, platforms, and integration behavior. |
| `pytest_homeassistant.components.bluetooth` | Bluetooth device, advertisement, and scanner test helpers. |
| `pytest_homeassistant.components.mqtt.common` | MQTT client mocks, message helpers, and shared assertions. |
| `pytest_homeassistant.components.recorder.common` | Recorder setup, database, and history test helpers. |
| `pytest_homeassistant.components.diagnostics` | Helpers for requesting integration and device diagnostics. |
| `pytest_homeassistant.components.repairs` | Helpers for listing repair issues and starting and completing repair flows. |
| `pytest_homeassistant.components.infrared.common`, `.radio_frequency.common` | Mock IR and RF entities and commands, plus integration setup helpers. |
| `pytest_homeassistant.test_util.aiohttp` | Mock HTTP client responses and sessions. |
| `pytest_homeassistant.syrupy` | Snapshot extensions for Home Assistant objects. |
| `pytest_homeassistant.typing` | Type aliases for shared test fixtures. |

The package also includes the JSON, time, and recorder patches used by Core's test
environment, plus support for detecting uncaught exceptions.

## Using helpers in Core tests

Set up a Core development checkout with `script/setup`, then run tests from the
repository root. Core configures the package's import path and loads its shared
fixtures and hooks through `tests/conftest.py`.

For example, a test can create a configuration entry without setting up the
integration:

```python
from homeassistant.core import HomeAssistant

from pytest_homeassistant.common import MockConfigEntry


async def test_config_entry(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain="my_integration", data={"host": "example.local"})
    entry.add_to_hass(hass)

    assert hass.config_entries.async_get_entry(entry.entry_id) is entry
```

Existing imports such as `from tests.common import MockConfigEntry` continue to
work: the original Core test modules re-export the same helpers. Core initializes
the test data path in `tests/__init__.py`, so fixture loaders still read from the
Core test tree.

## Building

Build both distributions from the Core repository root:

```shell
uv build packages/pytest-home-assistant
```

Core's CI builds the package to check that it remains buildable. Publishing and
standalone installation support will be added separately.

## License

Apache License 2.0. See [LICENSE.md](LICENSE.md).
