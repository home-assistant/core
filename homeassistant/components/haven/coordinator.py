"""Coordinator for HAVEN local API polling."""

from datetime import timedelta
from typing import override

from haveniaq import (
    DeviceInfo,
    HavenApiError,
    HavenClient,
    HavenUnsupportedApiVersionError,
    HavenUnsupportedProductError,
    SensorData,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

UPDATE_INTERVAL = timedelta(minutes=1)

type HavenConfigEntry = ConfigEntry[HavenDataUpdateCoordinator]


class HavenDataUpdateCoordinator(DataUpdateCoordinator[SensorData]):
    """Coordinate sequential polling of a HAVEN device."""

    def __init__(self, hass: HomeAssistant, entry: HavenConfigEntry) -> None:
        """Initialize the coordinator."""
        host = entry.data[CONF_HOST]
        super().__init__(
            hass,
            logger=LOGGER,
            name=f"{DOMAIN}_{host}",
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.client = HavenClient(host, session=async_get_clientsession(hass))
        self.info: DeviceInfo

    @override
    async def _async_setup(self) -> None:
        """Fetch stable device metadata before the first poll."""
        try:
            self.info = await self.client.get_info()
        except HavenUnsupportedApiVersionError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="unsupported_api_version",
            ) from err
        except HavenUnsupportedProductError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="unsupported_product",
            ) from err
        except HavenApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
            ) from err

    @override
    async def _async_update_data(self) -> SensorData:
        try:
            return await self.client.get_sensors()
        except HavenApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
            ) from err
