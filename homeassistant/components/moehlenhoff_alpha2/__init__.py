"""Support for the Moehlenhoff Alpha2."""
import asyncio
from datetime import timedelta
import logging

import aiohttp
from moehlenhoff_alpha2 import Alpha2Base

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, SIGNAL_HEATAREA_DATA_UPDATED

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate"]

UPDATE_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a config entry."""
    base = Alpha2Base(entry.data["host"])
    try:
        await base.update_data()
    except (
        aiohttp.client_exceptions.ClientConnectorError,
        asyncio.TimeoutError,
    ) as err:
        raise exceptions.ConfigEntryNotReady from err

    base_uh = Alpha2BaseUpdateHandler(hass, base)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"connection": base_uh, "devices": set()}

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    # Trigger updates at regular intervals.
    async_track_time_interval(hass, base_uh.async_update, UPDATE_INTERVAL)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class Alpha2BaseUpdateHandler:
    """Keep the base instance in one place and centralize the update."""

    def __init__(self, hass: HomeAssistant, base: Alpha2Base) -> None:
        """Initialize the base handle."""
        self._hass = hass
        self.base = base
        self._loop = asyncio.get_event_loop()

    async def async_update(self, now=None):
        """Pull the latest data from the Alpha2 base."""
        await self.base.update_data()
        for heatarea in self.base.heatareas:
            _LOGGER.debug("Heatarea: %s", heatarea)
            async_dispatcher_send(self._hass, SIGNAL_HEATAREA_DATA_UPDATED, heatarea)

    def get_cooling(self):
        """Return if cooling mode is enabled."""
        return self.base.cooling

    async def async_set_cooling(self, enabled: bool):
        """Enable or disable cooling mode."""
        await self.base.set_cooling(enabled)
        for heatarea in self.base.heatareas:
            async_dispatcher_send(self._hass, SIGNAL_HEATAREA_DATA_UPDATED, heatarea)

    async def async_set_target_temperature(self, heatarea_id, target_temperature):
        """Set the target temperature of the given heatarea."""
        _LOGGER.info(
            "Setting target temperature of heatarea %s to %0.1f",
            heatarea_id,
            target_temperature,
        )
        await self.base.update_heatarea(heatarea_id, {"T_TARGET": target_temperature})
        await self.async_update()

    async def async_set_heatarea_mode(self, heatarea_id, heatarea_mode):
        """Set the mode of the given heatarea."""
        # HEATAREA_MODE: 0=Auto, 1=Tag, 2=Nacht
        assert heatarea_mode in (0, 1, 2)
        _LOGGER.info(
            "Setting mode of heatarea %s to %d",
            heatarea_id,
            heatarea_mode,
        )
        await self.base.update_heatarea(heatarea_id, {"HEATAREA_MODE": heatarea_mode})
        await self.async_update()
