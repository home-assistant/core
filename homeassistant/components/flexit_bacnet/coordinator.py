"""DataUpdateCoordinator for Flexit Nordic (BACnet) integration.."""

from __future__ import annotations

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

type FlexitConfigEntry = ConfigEntry[FlexitCoordinator]


class FlexitCoordinator(DataUpdateCoordinator[FlexitBACnet]):
    """Class to manage fetching data from a Flexit Nordic (BACnet) device."""

    config_entry: FlexitConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: FlexitConfigEntry) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{config_entry.data[CONF_DEVICE_ID]}",
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
                translation_domain=DOMAIN,
                translation_key="not_ready",
                translation_placeholders={
                    "ip": str(self.config_entry.data[CONF_IP_ADDRESS]),
                },
            ) from exc

        return self.device
