# Test Fixtures Reference

## Common Fixtures from tests.common

```python
from tests.common import (
    MockConfigEntry,
    load_fixture,
    snapshot_platform,
)
```

## MockConfigEntry

```python
from tests.common import MockConfigEntry

@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My Device",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_API_KEY: "test_key",
        },
        unique_id="device_serial_123",
        version=1,
        minor_version=1,
    )
```

## Loading Fixture Files

Create JSON files in `tests/components/my_integration/fixtures/`:

```python
from tests.common import load_fixture

# Load fixture file
data = load_fixture("device_data.json", DOMAIN)

# Parse as JSON
import json
parsed = json.loads(load_fixture("device_data.json", DOMAIN))
```

## Entity Registry Fixture

```python
from homeassistant.helpers import entity_registry as er

@pytest.fixture
def entity_registry(hass: HomeAssistant) -> er.EntityRegistry:
    """Return the entity registry."""
    return er.async_get(hass)
```

## Device Registry Fixture

```python
from homeassistant.helpers import device_registry as dr

@pytest.fixture
def device_registry(hass: HomeAssistant) -> dr.DeviceRegistry:
    """Return the device registry."""
    return dr.async_get(hass)
```

## Enable All Entities

```python
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(hass: HomeAssistant) -> None:
    """Test with all entities enabled."""
```

## Freezing Time

```python
from freezegun.api import FrozenDateTimeFactory

async def test_with_frozen_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test time-dependent behavior."""
    freezer.move_to("2024-01-15 12:00:00")
    # ... test code
    freezer.tick(timedelta(minutes=5))
```

## Snapshot Testing

```python
from syrupy.assertion import SnapshotAssertion
from tests.common import snapshot_platform

@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all entities match snapshot."""
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry.entry_id
    )
```

## Mocking External APIs

```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_device_api() -> Generator[MagicMock]:
    """Return a mocked device API."""
    with patch(
        "homeassistant.components.my_integration.MyDeviceAPI",
        autospec=True,
    ) as api_mock:
        api = api_mock.return_value
        api.async_get_data = AsyncMock(return_value=mock_data)
        api.async_get_status = AsyncMock(return_value="online")
        yield api
```

## Integration Setup Fixture

```python
@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_api: MagicMock,
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
```

## Platform-Specific Setup

```python
from homeassistant.const import Platform

@pytest.fixture
def platforms() -> list[Platform]:
    """Override platforms to test."""
    return [Platform.SENSOR]

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
