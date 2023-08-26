"""The Flexit Nordic (BACnet) integration."""
from __future__ import annotations

import asyncio.exceptions
from datetime import timedelta
import logging

from flexit_bacnet import FlexitBACnet
from flexit_bacnet.bacnet import DecodingError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_IP_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.FAN, Platform.SENSOR]


class FlexitDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from Flexit Nordic ventilation machine."""

    def __init__(self, hass: HomeAssistant, flexit_bacnet: FlexitBACnet) -> None:
        """Initialize shared Flexit data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=flexit_bacnet.update,
            update_interval=timedelta(seconds=30),
        )
        self.flexit_bacnet = flexit_bacnet


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flexit Nordic (BACnet) from a config entry."""

    flexit_bacnet = FlexitBACnet(
        entry.data[CONF_IP_ADDRESS], entry.data[CONF_DEVICE_ID]
    )

    try:
        await flexit_bacnet.update()
    except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
        raise ConfigEntryNotReady(
            f"Timeout while connecting to {entry.data[CONF_IP_ADDRESS]}"
        ) from exc

    data_coordinator = FlexitDataUpdateCoordinator(
        hass,
        flexit_bacnet=flexit_bacnet,
    )

    # Fetch initial data from the Flexit unit. If fails, will start the
    # configuration automatically process again.
    await data_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
