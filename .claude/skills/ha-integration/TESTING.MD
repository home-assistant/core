# Testing Reference

Testing patterns for Home Assistant integrations.

## Test Structure

```
tests/components/my_integration/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_config_flow.py      # Config flow tests (100% coverage required)
├── test_init.py             # Integration setup tests
├── test_sensor.py           # Sensor platform tests
├── test_diagnostics.py      # Diagnostics tests
├── snapshots/               # Snapshot files
│   └── test_sensor.ambr
└── fixtures/                # Test data fixtures
    └── device_data.json
```

## conftest.py

```python
"""Fixtures for My Integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.my_integration.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="My Device",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_API_KEY: "test_api_key",
        },
        unique_id="device_serial_123",
    )


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Return a mocked client."""
    with patch(
        "homeassistant.components.my_integration.MyClient",
        autospec=True,
    ) as client_mock:
        client = client_mock.return_value
        client.get_data = AsyncMock(
            return_value=MyData.from_json(load_fixture("device_data.json", DOMAIN))
        )
        client.serial_number = "device_serial_123"
        client.name = "My Device"
        client.model = "Model X"
        client.firmware_version = "1.2.3"
        yield client


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to test."""
    return [Platform.SENSOR, Platform.BINARY_SENSOR]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.my_integration.PLATFORMS",
        platforms,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
```

## Config Flow Tests

**100% coverage required for all paths:**

```python
"""Test config flow for My Integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.my_integration.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_API_KEY: "test_key",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Device"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_API_KEY: "test_key",
    }
    assert result["result"].unique_id == "device_serial_123"


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test connection error in user flow."""
    mock_client.get_data.side_effect = ConnectionError("Cannot connect")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_API_KEY: "test_key",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test already configured error."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_API_KEY: "test_key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"
```

## Entity Tests with Snapshots

```python
"""Test sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Override platforms for sensor tests."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_sensor_device_assignment(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors are assigned to correct device."""
    device = device_registry.async_get_device(
        identifiers={("my_integration", "device_serial_123")}
    )
    assert device is not None

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity in entities:
        assert entity.device_id == device.id
```

## Coordinator Tests

```python
"""Test coordinator."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_coordinator_update_success(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test successful coordinator update."""
    coordinator = MyCoordinator(hass, mock_config_entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.data.temperature == 21.5
    assert coordinator.last_update_success


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test coordinator handles API error."""
    mock_client.get_data.side_effect = MyError("Connection failed")

    coordinator = MyCoordinator(hass, mock_config_entry, mock_client)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_auth_failed(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test coordinator handles auth error."""
    mock_client.get_data.side_effect = AuthError("Invalid token")

    coordinator = MyCoordinator(hass, mock_config_entry, mock_client)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
```

## Diagnostics Tests

```python
"""Test diagnostics."""

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.my_integration import snapshot_platform
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == snapshot
```

## Common Fixtures

```python
from tests.common import MockConfigEntry, load_fixture

# Load JSON fixture
data = load_fixture("device_data.json", DOMAIN)

# Enable all entities (including disabled by default)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")

# Freeze time
from freezegun.api import FrozenDateTimeFactory

async def test_with_frozen_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.tick(timedelta(minutes=5))
    await hass.async_block_till_done()
```

## Update Snapshots

```bash
# Update snapshots
pytest tests/components/my_integration --snapshot-update

# Always re-run without flag to verify
pytest tests/components/my_integration
```

## Test Commands

```bash
# Run tests with coverage
pytest tests/components/my_integration \
  --cov=homeassistant.components.my_integration \
  --cov-report term-missing \
  --numprocesses=auto

# Run specific test
pytest tests/components/my_integration/test_config_flow.py::test_user_flow_success

# Quick test of changed files
pytest --timeout=10 --picked
```

## Best Practices

1. **Never access `hass.data` directly** - Use fixtures and proper setup
2. **Mock all external APIs** - Use fixtures with realistic JSON data
3. **Use snapshot testing** - For entity states and attributes
4. **Test error paths** - Connection errors, auth failures, invalid data
5. **Test edge cases** - Empty data, missing fields, None values
6. **>95% coverage required** - All code paths must be tested
