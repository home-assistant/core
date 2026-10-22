# pytest-home-assistant

Pytest fixtures and helpers for testing Home Assistant integrations. Create a
Home Assistant instance, mock configuration entries and external services,
simulate events, and check integration behavior.

## Installation and compatibility

Install the package into your custom integration's virtual environment:

```shell
uv pip install pytest-home-assistant
```

Use the package release that matches your Home Assistant version. Upgrade them
together.
The plugin loads automatically. Do not install it together with
`pytest-homeassistant-custom-component`, which supplies overlapping fixtures.

Bluetooth, infrared, and radio-frequency helpers have optional dependencies:
install the corresponding `bluetooth`, `infrared`, or `radio-frequency` extra
when using those helpers. Integration-specific libraries must also be installed
by the consuming project. SQLite recorder tests work with the base installation;
MySQL/PostgreSQL tests additionally need their database driver and
`sqlalchemy-utils`.

## Writing tests

Add this pytest configuration to your project's `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
# Let Home Assistant install its httpx alias before respx is imported.
addopts = "-p no:respx"
pythonpath = ["."]
testpaths = ["tests"]
```

The package's HTTP mocks still use respx directly; only its separate pytest
plugin is disabled. The `hass` fixture enables custom integrations by default.

Tests request fixtures such as `hass` by name and import helpers from
`pytest_homeassistant`. For example, `tests/test_config_entry.py` can create a
configuration entry without setting up the integration:

```python
from homeassistant.core import HomeAssistant
from pytest_homeassistant.common import MockConfigEntry


async def test_config_entry(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain="my_integration", data={"host": "example.local"})
    entry.add_to_hass(hass)

    assert hass.config_entries.async_get_entry(entry.entry_id) is entry
```

Run your tests with `pytest`.

Use `@pytest.mark.usefixtures("entity_registry_enabled_by_default")` when a test
needs entities that are normally disabled in the entity registry.

## Test data and configuration

Load test data with helpers such as `load_fixture` and `load_json_object_fixture`
from `pytest_homeassistant.common`. They read `tests/fixtures` by default. When
given an integration name, they use `tests/components/<domain>/fixtures` if that
integration's test directory exists, otherwise `tests/fixtures`. Set `ha_test_root`
to use another test directory. Paths are relative to pytest's project root.
Snapshots are stored next to the consuming test in `snapshots/`.

The `hass` fixture uses the shared `tests/testing_config` path by default, without
creating or copying a directory. Set `ha_test_config_dir` relative to the project
root to use another path. For tests that need an isolated writable directory,
override `hass_config_dir` to return `hass_tmp_config_dir`. That fixture copies the
shared configuration if it exists, or provides an empty temporary directory.

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

## Migrating from pytest-homeassistant-custom-component

Replace the old package dependency with `pytest-home-assistant` and change imports
of `pytest_homeassistant_custom_component` to `pytest_homeassistant`. Existing
`hass`, `enable_custom_integrations`, registry, HTTP, recorder, and snapshot
fixtures keep their names.
The wrapper fixture requesting `enable_custom_integrations` can be removed;
custom integrations are enabled by default.

## License

Apache License 2.0. See [LICENSE.md](LICENSE.md).
