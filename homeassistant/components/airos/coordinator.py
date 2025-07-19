"""DataUpdateCoordinator for AirOS."""

import logging
from typing import Any, NamedTuple

from airos.airos8 import AirOS

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AirOSData(NamedTuple):
    """AirOS data stored in the DataUpdateCoordinator."""

    device_data: dict[str, Any]
    device_id: str
    hostname: str


class AirOSDataUpdateCoordinator(DataUpdateCoordinator[AirOSData]):
    """Class to manage fetching AirOS data from single endpoint."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, airdevice: AirOS
    ) -> None:
        """Initialize the coordinator."""
        self.airdevice = airdevice
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> AirOSData:
        """Fetch data from AirOS."""
        try:
            await self.airdevice.login()
            status = await self.airdevice.status()

            host_data = status["host"]
            device_id = host_data["device_id"]
            hostname = host_data.get("hostname", "Ubiquiti airOS Device")

            airos_data = AirOSData(
                device_data=status, device_id=device_id, hostname=hostname
            )

        except Exception as err:
            raise ConfigEntryAuthFailed from err
        return airos_data
