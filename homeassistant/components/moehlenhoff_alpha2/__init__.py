"""Support for the Moehlenhoff Alpha2."""
import asyncio
import logging
import time

from moehlenhoff_alpha2 import Alpha2Base

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate"]


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up Alpha2 integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a config entry."""
    base = Alpha2Base(entry.data["host"])
    try:
        await base.update_data()
    except TimeoutError as err:
        raise exceptions.ConfigEntryNotReady from err

    base_uh = Alpha2BaseUpdateHandler(base, 60)
    hass.data.setdefault(DOMAIN, {"connections": {}, "devices": set()})
    hass.data[DOMAIN]["connections"][entry.entry_id] = base_uh

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

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

    def __init__(self, base, scan_interval):
        """Initialize the base handle."""
        self.base = base
        self.scan_interval = scan_interval
        self._last_update = 0
        self._heatarea_update_callbacks = {}
        self._loop = asyncio.get_event_loop()

    def add_heatarea_update_callback(self, callback, heatarea_nr):
        """Add a callback which will be run when data of the given heatarea is updated."""
        if heatarea_nr not in self._heatarea_update_callbacks:
            self._heatarea_update_callbacks[heatarea_nr] = []
        self._heatarea_update_callbacks[heatarea_nr].append(callback)

    async def async_update(self):
        """Pull the latest data from the Alpha2 base."""
        # Only update every update_interval
        if (time.monotonic() - self._last_update) >= self.scan_interval:
            self._last_update = time.monotonic()
            _LOGGER.debug("Updating")
            await self.base.update_data()
            for heatarea in self.base.heatareas:
                _LOGGER.debug("Heatarea: %s", heatarea)
                for callback in self._heatarea_update_callbacks.get(heatarea["NR"], []):
                    try:
                        callback(heatarea)
                    except Exception as cb_err:  # pylint: disable=broad-except
                        _LOGGER.error(
                            "Failed to run callback '%s': %s", callback, cb_err
                        )
        else:
            _LOGGER.debug("Skipping update")

    def update(self):
        """Pull the latest data from the Alpha2 base (sync version)."""
        asyncio.run_coroutine_threadsafe(self.async_update(), self._loop)

    async def async_set_target_temperature(self, heatarea_id, target_temperature):
        """Set the target temperature of the given heatarea."""
        _LOGGER.info(
            "Setting target temperature of heatarea %s to %0.1f",
            heatarea_id,
            target_temperature,
        )
        await self.base.update_heatarea(heatarea_id, {"T_TARGET": target_temperature})

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
