# Write Tests

This skill covers testing patterns and requirements for Home Assistant integrations.

## When to Use

- Writing tests for a new integration
- Adding test coverage for existing code
- Understanding testing patterns and fixtures

## Core Requirements

- **Location**: `tests/components/{domain}/`
- **Coverage**: Above 95% for all modules
- **Config flow coverage**: 100% required

## Running Tests

```bash
# Integration-specific tests (recommended)
pytest ./tests/components/<domain> \
  --cov=homeassistant.components.<domain> \
  --cov-report term-missing \
  --durations-min=1 \
  --durations=0 \
  --numprocesses=auto

# Quick test of changed files
pytest --timeout=10 --picked

# Update test snapshots
pytest ./tests/components/<domain> --snapshot-update
# ⚠️ Omit test results after using --snapshot-update
# Always run tests again without the flag to verify snapshots
```

## Test Structure

```
tests/components/my_integration/
├── __init__.py
├── conftest.py          # Shared fixtures
├── test_init.py         # Setup/unload tests
├── test_config_flow.py  # Config flow tests
├── test_sensor.py       # Platform tests
├── test_diagnostics.py  # Diagnostics tests
└── fixtures/            # JSON fixture data
    └── device_data.json
```

## Essential Fixtures

### conftest.py

```python
"""Fixtures for My Integration tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.my_integration.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My Device",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id="device_serial_123",
    )


@pytest.fixture
def mock_device_api() -> Generator[MagicMock]:
    """Return a mocked device API."""
    with patch(
        "homeassistant.components.my_integration.MyDeviceAPI",
        autospec=True,
    ) as api_mock:
        api = api_mock.return_value
        api.get_data.return_value = MyDeviceData.from_json(
            load_fixture("device_data.json", DOMAIN)
        )
        yield api


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return PLATFORMS


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_api: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.my_integration.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
```

## Config Flow Testing

**100% coverage required for all config flow paths.**

```python
"""Test config flow."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_USER_INPUT


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_device_api: MagicMock,
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_USER_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Device"
    assert result["data"] == TEST_USER_INPUT


async def test_flow_connection_error(
    hass: HomeAssistant,
    mock_device_api: MagicMock,
) -> None:
    """Test connection error handling."""
    mock_device_api.get_data.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_USER_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_api: MagicMock,
) -> None:
    """Test duplicate prevention."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_USER_INPUT,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
```

## Entity Testing with Snapshots

```python
"""Test sensor entities."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Override platforms fixture."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all sensor entities."""
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry.entry_id
    )

    # Verify device assignment
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "device_unique_id")}
    )
    assert device_entry

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id
```

## Testing Best Practices

### Do

- Use fixtures from `tests.common`
- Mock all external dependencies
- Use snapshots for complex data structures
- Test through proper integration setup
- Verify entities are registered with devices

### Don't

- Access `hass.data` directly in tests
- Test entities in isolation
- Use real network calls
- Skip error scenarios

## Debugging Tests

### Enable Debug Logging

```python
async def test_with_debug_logging(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test with debug logging enabled."""
    import logging
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.my_integration")
    # ... test code
    assert "Expected message" in caplog.text
```

### Common Test Issues

| Problem | Solution |
|---------|----------|
| Integration won't load | Check `manifest.json` syntax and required fields |
| Entities not appearing | Verify `unique_id` and `has_entity_name` implementation |
| Config flow errors | Check `strings.json` entries match error keys |
| Mock not working | Verify patch location (where used, not defined) |
| Async issues | Ensure `await hass.async_block_till_done()` after setup |

### Validation Commands

```bash
# Check integration structure
python -m script.hassfest --integration-path homeassistant/components/my_integration

# Run with verbose output
pytest ./tests/components/my_integration -v --tb=short

# Run single test with debugging
pytest ./tests/components/my_integration/test_sensor.py::test_sensor_state -v -s
```

## Related Skills

- `config-flow` - Config flow implementation (100% test coverage required)
- `entity` - Entity testing patterns
- `coordinator` - Testing coordinator behavior
