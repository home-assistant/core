"""Data update coordinator for the Papouch integration."""

from datetime import timedelta
import logging
from typing import override

from aiopapouch import PapouchDevice, PapouchTransport
from aiopapouch.exceptions import DeviceAuthError, DeviceConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type PapouchConfigEntry = ConfigEntry[PapouchDataUpdateCoordinator]


class PapouchDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Papouch data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: PapouchTransport,
        entry: PapouchConfigEntry,
        device: PapouchDevice,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api_client = api_client
        self.device = device

    @override
    async def _async_update_data(self) -> dict:
        """Fetch data from the device."""
        try:
            fresh_data = await self.api_client.fetch_data()
            return await self.device.parse_fresh_data(fresh_data)
        except DeviceAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={
                    "name": self.device.name,
                    "location": self.device.location,
                },
            ) from err
        except DeviceConnectionError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_device",
                translation_placeholders={
                    "name": self.device.name,
                    "location": self.device.location,
                },
            ) from err
