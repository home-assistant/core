"""Coordinate device updates from the Hitron CODA router."""

from datetime import timedelta
import logging
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, DeviceData, HitronCodaClient, InvalidAuth
from .const import DEFAULT_TYPE, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type HitronCodaConfigEntry = ConfigEntry[HitronCodaDataUpdateCoordinator]


class HitronCodaDataUpdateCoordinator(DataUpdateCoordinator[DeviceData]):
    """Poll the router once for all tracked devices."""

    config_entry: HitronCodaConfigEntry

    def __init__(self, hass: HomeAssistant, entry: HitronCodaConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.data.get(
                    CONF_SCAN_INTERVAL, UPDATE_INTERVAL.total_seconds()
                )
            ),
        )
        self.client = HitronCodaClient(
            entry.data[CONF_HOST],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data.get(CONF_TYPE, DEFAULT_TYPE),
        )

    @override
    async def _async_update_data(self) -> DeviceData:
        """Fetch data without blocking the event loop."""
        try:
            return await self.hass.async_add_executor_job(self.client.get_devices)
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed("Invalid router credentials") from err
        except CannotConnect as err:
            raise UpdateFailed(str(err)) from err
