# pytest-home-assistant

Pytest fixtures and helpers for testing Home Assistant integrations. This package
contains the shared testing tools used by Home Assistant Core, with the goal of
making those same tools available to third-party integration authors.

Use these tools to create a Home Assistant instance for a test, mock configuration
entries and external services, simulate events, and check integration behavior.
The Python import namespace is `pytest_homeassistant`.

## Installation and compatibility

The package requires Python 3.14.2 or newer and pins the matching Home Assistant
version. Upgrade the two together; helpers depend on Home Assistant's internal
APIs and are not compatible with older releases.

Until the package is published, install Home Assistant and the helpers from the
same Core checkout into your custom integration's virtual environment:

```shell
uv pip install /path/to/core /path/to/core/packages/pytest-home-assistant
```

Both are installed as packages; the checkout is not required when running tests.
The plugin loads automatically. Do not install it together with
`pytest-homeassistant-custom-component`, which supplies overlapping fixtures.

Bluetooth, infrared, and radio-frequency helpers have optional dependencies:
install the corresponding `bluetooth`, `infrared`, or `radio-frequency` extra
when using those helpers. Integration-specific libraries must also be installed
by the consuming project. SQLite recorder tests work with the base installation;
MySQL/PostgreSQL tests additionally need their database driver and
`sqlalchemy-utils`.

## Custom integrations

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
plugin is disabled. Enable loading your custom integration in `tests/conftest.py`:

```python
import pytest


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow loading this project's custom integrations."""
```

Import helpers from `pytest_homeassistant`, for example:

```python
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture
```

When migrating from `pytest-homeassistant-custom-component`, replace imports of
`pytest_homeassistant_custom_component` with `pytest_homeassistant`. Existing
`hass`, `enable_custom_integrations`, registry, HTTP, recorder, and snapshot
fixtures keep their names.

Fixture loaders read `tests/fixtures` by default. A Core-style
`tests/components/<domain>/fixtures` directory is used when that integration's
test directory exists; otherwise an integration argument still resolves to
`tests/fixtures`. Set `ha_test_root` to use another test directory. Paths are
relative to pytest's project root, so invoking pytest from another directory
also works. Snapshots are stored next to the consuming test in `snapshots/`.

Each test gets an empty temporary Home Assistant configuration directory. To use
a prepared configuration, set `ha_test_config_dir` relative to the project root,
or override the `hass_config_dir` fixture. The `hass_tmp_config_dir` fixture copies
that prepared configuration into a temporary directory when configured.

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
work: the original Core test modules re-export the same helpers. Core configures its test and configuration paths explicitly, so fixture loaders
still read from the Core test tree.

## Building

Build both distributions from the Core repository root:

```shell
uv build packages/pytest-home-assistant
```

Core's CI installs the built wheel and Home Assistant in a clean environment,
then runs the standalone custom-integration tests outside the checkout. Package
releases must update the package version and Home Assistant dependency together.
Publishing is a separate release step.

## License

Apache License 2.0. See [LICENSE.md](LICENSE.md).
