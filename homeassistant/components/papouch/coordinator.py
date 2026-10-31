"""Data update coordinator for the Papouch integration."""

from datetime import timedelta
import logging
from typing import Any, override

from aiopapouch import PapouchHTTPClient, PapouchNetworkDevice
from aiopapouch.exceptions import DeviceAuthError, DeviceConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type PapouchConfigEntry = ConfigEntry[PapouchNetworkDataUpdateCoordinator]


class PapouchNetworkDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Papouch network data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: PapouchHTTPClient,
        entry: PapouchConfigEntry,
        device: PapouchNetworkDevice,
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

    def get_device(self) -> PapouchNetworkDevice:
        """Return the single network device as a list."""

        return self.device

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device."""

        try:
            parsed_data = await self.device.get_fresh_data()
        except DeviceAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={
                    "name": self.device.conf.name,
                    "location": self.device.conf.location,
                },
            ) from err
        except DeviceConnectionError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_device",
                translation_placeholders={
                    "name": self.device.conf.name,
                    "location": self.device.conf.location,
                },
            ) from err

        return {self.device.conf.identifier: parsed_data}
