# Data Update Coordinator

This skill covers implementing data update coordinators for efficient data fetching.

## When to Use

- Fetching data from devices or APIs that multiple entities share
- Implementing polling-based updates
- Centralizing error handling for data fetching

## Basic Coordinator

```python
"""Data update coordinator for My Integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MyCoordinator(DataUpdateCoordinator[MyData]):
    """My Integration data update coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: MyClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
            config_entry=config_entry,  # ✅ Pass config_entry - it's accepted and recommended
        )
        self.client = client
        self.device_id = config_entry.unique_id

    async def _async_update_data(self) -> MyData:
        """Fetch data from the device."""
        try:
            return await self.client.async_get_data()
        except AuthError as err:
            raise ConfigEntryAuthFailed("Invalid credentials") from err
        except ConnectionError as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err
```

## Error Types

- **UpdateFailed**: API/connection errors (temporary)
- **ConfigEntryAuthFailed**: Authentication issues (triggers reauth flow)

## Polling Intervals

**Polling intervals are NOT user-configurable.**

```python
# Good - integration determines interval
update_interval=timedelta(minutes=5)

# Good - interval based on device type
interval = timedelta(seconds=30) if client.is_local else timedelta(minutes=5)

# Bad - user-configurable
update_interval=timedelta(minutes=entry.data.get("scan_interval", 5))
```

### Minimum Intervals

- Local network: 5 seconds minimum
- Cloud services: 60 seconds minimum

## Using in __init__.py

```python
"""The My Integration integration."""

from .coordinator import MyCoordinator

type MyIntegrationConfigEntry = ConfigEntry[MyRuntimeData]


@dataclass
class MyRuntimeData:
    """Runtime data for My Integration."""

    client: MyClient
    coordinator: MyCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
) -> bool:
    """Set up My Integration from a config entry."""
    client = MyClient(entry.data[CONF_HOST])

    coordinator = MyCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = MyRuntimeData(client=client, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
```

## Entity Integration

```python
"""Sensor platform."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MyCoordinator


class MySensor(CoordinatorEntity[MyCoordinator], SensorEntity):
    """Sensor entity using coordinator."""

    def __init__(self, coordinator: MyCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        return self.coordinator.data.temperature
```

## Parallel Updates

Control concurrent entity updates:

```python
# In platform file (e.g., sensor.py)
PARALLEL_UPDATES = 1  # Serialize updates to prevent overwhelming device
# OR
PARALLEL_UPDATES = 0  # Unlimited (for coordinator-based or read-only)
```

## Coordinator with Device Info

```python
class MyCoordinator(DataUpdateCoordinator[MyData]):
    """Coordinator with device information."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MyClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
            config_entry=config_entry,
        )
        self.client = client

    @property
    def device_id(self) -> str:
        """Return the device ID."""
        return self.config_entry.unique_id

    @property
    def device_name(self) -> str:
        """Return the device name."""
        return self.data.name

    @property
    def device_model(self) -> str:
        """Return the device model."""
        return self.data.model
```

## Try/Catch Best Practices

Keep try blocks minimal:

```python
async def _async_update_data(self) -> MyData:
    """Fetch data from the device."""
    try:
        data = await self.client.async_get_data()
    except ConnectionError as err:
        raise UpdateFailed(f"Connection error: {err}") from err

    # Process data outside try block
    processed_data = self._process_data(data)
    return processed_data
```

## Unavailability Logging

Log once when unavailable, once when recovered:

```python
class MyCoordinator(DataUpdateCoordinator[MyData]):
    """Coordinator with unavailability logging."""

    def __init__(self, ...) -> None:
        """Initialize."""
        super().__init__(...)
        self._unavailable_logged = False

    async def _async_update_data(self) -> MyData:
        """Fetch data."""
        try:
            data = await self.client.async_get_data()
        except ConnectionError as err:
            if not self._unavailable_logged:
                _LOGGER.info("Device is unavailable: %s", err)
                self._unavailable_logged = True
            raise UpdateFailed(f"Connection error: {err}") from err

        if self._unavailable_logged:
            _LOGGER.info("Device is back online")
            self._unavailable_logged = False

        return data
```

## Related Skills

- `entity` - Using coordinator in entities
- `async-programming` - Async best practices
- `write-tests` - Testing coordinator behavior
