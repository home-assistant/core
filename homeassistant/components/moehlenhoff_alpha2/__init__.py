"""Support for the Moehlenhoff Alpha2."""
from datetime import timedelta
import logging
from typing import Dict

from moehlenhoff_alpha2 import Alpha2Base

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate"]

UPDATE_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    base = Alpha2Base(entry.data["host"])
    coordinator = Alpha2BaseCoordinator(hass, base)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class Alpha2BaseCoordinator(DataUpdateCoordinator[Dict[str, Dict]]):
    """Keep the base instance in one place and centralize the update."""

    def __init__(self, hass: HomeAssistant, base: Alpha2Base) -> None:
        """Initialize Alpha2Base data updater."""
        self.base = base
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="alpha2_base",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> Dict[str, Dict]:
        """Fetch the latest data from the source."""
        await self.base.update_data()
        return {ha["ID"]: ha for ha in self.base.heatareas if ha.get("ID")}

    def get_cooling(self) -> bool:
        """Return if cooling mode is enabled."""
        return self.base.cooling

    async def async_set_cooling(self, enabled: bool) -> None:
        """Enable or disable cooling mode."""
        await self.base.set_cooling(enabled)
        for update_callback in self._listeners:
            update_callback()

    async def async_set_target_temperature(
        self, heatarea_id: str, target_temperature: float
    ) -> None:
        """Set the target temperature of the given heatarea."""
        _LOGGER.debug(
            "Setting target temperature of heatarea %s to %0.1f",
            heatarea_id,
            target_temperature,
        )
        await self.base.update_heatarea(heatarea_id, {"T_TARGET": target_temperature})
        for update_callback in self._listeners:
            update_callback()

    async def async_set_heatarea_mode(
        self, heatarea_id: str, heatarea_mode: int
    ) -> None:
        """Set the mode of the given heatarea."""
        # HEATAREA_MODE: 0=Auto, 1=Tag, 2=Nacht
        assert heatarea_mode in (0, 1, 2)
        _LOGGER.debug(
            "Setting mode of heatarea %s to %d",
            heatarea_id,
            heatarea_mode,
        )
        await self.base.update_heatarea(heatarea_id, {"HEATAREA_MODE": heatarea_mode})
        for update_callback in self._listeners:
            update_callback()
