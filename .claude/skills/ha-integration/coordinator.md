# Data Update Coordinator Reference

The coordinator pattern centralizes data fetching and provides efficient polling.

## Basic Coordinator

```python
"""DataUpdateCoordinator for My Integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from my_library import MyClient, MyData, MyError, AuthError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import MyIntegrationConfigEntry

_LOGGER = logging.getLogger(__name__)


class MyCoordinator(DataUpdateCoordinator[MyData]):
    """My integration data update coordinator."""

    config_entry: MyIntegrationConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MyIntegrationConfigEntry,
        client: MyClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
            config_entry=entry,
        )
        self.client = client

    async def _async_update_data(self) -> MyData:
        """Fetch data from API."""
        try:
            return await self.client.get_data()
        except AuthError as err:
            raise ConfigEntryAuthFailed("Invalid credentials") from err
        except MyError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
```

## Key Points

### Always Pass config_entry

```python
super().__init__(
    hass,
    logger=_LOGGER,
    name=DOMAIN,
    update_interval=timedelta(minutes=1),
    config_entry=entry,  # Always include this
)
```

### Generic Type Parameter

Specify the data type returned by `_async_update_data`:

```python
class MyCoordinator(DataUpdateCoordinator[MyData]):
    ...
```

### Error Types

- **`UpdateFailed`**: API communication errors (will retry)
- **`ConfigEntryAuthFailed`**: Authentication issues (triggers reauth flow)

## Polling Intervals

**Integration determines intervals** - never make them user-configurable.

```python
# Constants (in const.py)
SCAN_INTERVAL_LOCAL = timedelta(seconds=30)
SCAN_INTERVAL_CLOUD = timedelta(minutes=5)

# In coordinator
class MyCoordinator(DataUpdateCoordinator[MyData]):
    def __init__(self, hass: HomeAssistant, entry: MyIntegrationConfigEntry, client: MyClient) -> None:
        # Determine interval based on connection type
        interval = SCAN_INTERVAL_LOCAL if client.is_local else SCAN_INTERVAL_CLOUD

        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=interval,
            config_entry=entry,
        )
```

**Minimum intervals:**
- Local network: 5 seconds
- Cloud services: 60 seconds

## Coordinator with Device Info

```python
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


class MyCoordinator(DataUpdateCoordinator[MyData]):
    """Coordinator with device information."""

    config_entry: MyIntegrationConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MyIntegrationConfigEntry,
        client: MyClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
            config_entry=entry,
        )
        self.client = client
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, client.serial_number)},
            name=client.name,
            manufacturer="My Company",
            model=client.model,
            sw_version=client.firmware_version,
        )

    async def _async_update_data(self) -> MyData:
        """Fetch data from API."""
        try:
            return await self.client.get_data()
        except MyError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
```

## Multiple Data Sources

```python
from dataclasses import dataclass


@dataclass
class MyCoordinatorData:
    """Data class for coordinator."""

    sensors: dict[str, SensorData]
    status: DeviceStatus
    settings: DeviceSettings


class MyCoordinator(DataUpdateCoordinator[MyCoordinatorData]):
    """Coordinator for multiple data sources."""

    async def _async_update_data(self) -> MyCoordinatorData:
        """Fetch all data sources."""
        try:
            # Fetch all data concurrently
            sensors, status, settings = await asyncio.gather(
                self.client.get_sensors(),
                self.client.get_status(),
                self.client.get_settings(),
            )
        except MyError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

        return MyCoordinatorData(
            sensors=sensors,
            status=status,
            settings=settings,
        )
```

## Setup in __init__.py

```python
async def async_setup_entry(hass: HomeAssistant, entry: MyIntegrationConfigEntry) -> bool:
    """Set up My Integration from a config entry."""
    client = MyClient(entry.data[CONF_HOST], entry.data[CONF_API_KEY])

    coordinator = MyCoordinator(hass, entry, client)

    # Perform first refresh - raises ConfigEntryNotReady on failure
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
```

## Testing Coordinators

```python
@pytest.fixture
def mock_coordinator(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> MyCoordinator:
    """Return a mocked coordinator."""
    coordinator = MyCoordinator(hass, mock_config_entry, MagicMock())
    coordinator.data = MyData(temperature=21.5, humidity=45)
    return coordinator


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_client: MagicMock,
) -> None:
    """Test coordinator handles update failure."""
    mock_client.get_data.side_effect = MyError("Connection failed")

    coordinator = MyCoordinator(hass, mock_config_entry, mock_client)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
```
