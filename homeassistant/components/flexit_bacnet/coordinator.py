from datetime import timedelta
import logging

from homeassistant.const import CONF_DEVICE_ID, CONF_IP_ADDRESS, Platform
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
import asyncio.exceptions

from flexit_bacnet import FlexitBACnet
from flexit_bacnet.bacnet import DecodingError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from .const import (
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class FlexitCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from a Flexit Nordic (BACnet) device."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize my coordinator."""

        self.config_entry = entry
        self.device = FlexitBACnet(
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_DEVICE_ID]
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_DEVICE_ID]}",
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self):
        """Fetch data from the device."""

        try:
            await self.device.update()
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise ConfigEntryNotReady(
                f"Timeout while connecting to {self.config_entry.data['address']}"
            ) from exc

        return self.device
