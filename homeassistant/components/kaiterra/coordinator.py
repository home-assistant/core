"""Coordinator for the Kaiterra integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_data import (
    KaiterraApiAuthError,
    KaiterraApiClient,
    KaiterraApiError,
    KaiterraDeviceNotFoundError,
)
from .const import LOGGER, UPDATE_INTERVAL

type KaiterraData = dict[str, dict[str, object]]


class KaiterraDataUpdateCoordinator(DataUpdateCoordinator[KaiterraData]):
    """Coordinate Kaiterra API calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: KaiterraConfigEntry,
        api: KaiterraApiClient,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=device_name,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self.device_id = device_id
        self.device_name = device_name

    async def _async_update_data(self) -> KaiterraData:
        """Fetch data from the API."""
        try:
            return await self.api.async_get_latest_sensor_readings(self.device_id)
        except KaiterraApiAuthError as err:
            raise ConfigEntryAuthFailed("Invalid API key") from err
        except KaiterraDeviceNotFoundError as err:
            raise ConfigEntryError(
                f"Configured device {self.device_id} was not found"
            ) from err
        except KaiterraApiError as err:
            raise UpdateFailed("Cannot connect to Kaiterra API") from err


type KaiterraConfigEntry = ConfigEntry[KaiterraDataUpdateCoordinator]
