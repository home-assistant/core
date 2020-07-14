"""The Growatt RS232 component."""

import asyncio
from datetime import timedelta
import logging

from growattRS232 import GrowattRS232, ModbusException, PortException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PORT
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PLATFORMS, STARTUP_MESSAGE

SCAN_INTERVAL = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: Config):
    """Set up this integration using YAML is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
        _LOGGER.info(STARTUP_MESSAGE)

    port = entry.data[CONF_PORT]
    address = entry.data[CONF_ADDRESS]

    coordinator = GrowattRS232DataUpdateCoordinator(hass, port=port, address=address)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in PLATFORMS:
        if entry.options.get(platform, True):
            coordinator.platforms.append(platform)
            hass.async_add_job(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Handle removal of an entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
                if platform in coordinator.platforms
            ]
        )
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


class GrowattRS232DataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Growatt data from the inverter."""

    def __init__(self, hass, port, address):
        """Initialize."""
        self.api = GrowattRS232(port, address)
        self.platforms = []

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Update data via library."""
        try:
            data = await self.api.async_update()
            return data
        except (PortException, ModbusException, ConnectionError) as exception:
            raise UpdateFailed(exception)
