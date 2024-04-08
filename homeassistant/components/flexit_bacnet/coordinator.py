"""DataUpdateCoordinator for Flexit Nordic (BACnet) integration.."""

import asyncio.exceptions
from datetime import timedelta
import logging

from flexit_bacnet import FlexitBACnet
from flexit_bacnet.bacnet import DecodingError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FlexitCoordinator(DataUpdateCoordinator[FlexitBACnet]):
    """Class to manage fetching data from a Flexit Nordic (BACnet) device."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, device_id: str) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}",
            update_interval=timedelta(seconds=60),
        )

        self.device = FlexitBACnet(
            self.config_entry.data[CONF_IP_ADDRESS],
            self.config_entry.data[CONF_DEVICE_ID],
        )

    async def _async_update_data(self) -> FlexitBACnet:
        """Fetch data from the device."""

        try:
            await self.device.update()
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise ConfigEntryNotReady(
                f"Timeout while connecting to {self.config_entry.data[CONF_IP_ADDRESS]}"
            ) from exc

        return self.device
