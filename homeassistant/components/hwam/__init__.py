"""The HWAM Smart Control integration."""

from __future__ import annotations

from pystove import Stove

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import StoveDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type StoveConfigEntry = ConfigEntry[Stove]  # noqa: F821


async def async_setup_entry(hass: HomeAssistant, entry: StoveConfigEntry) -> bool:
    """Set up HWAM Smart Control from a config entry."""

    ip = entry.data[CONF_HOST]
    stove = await Stove.create(ip)
    entry.runtime_data = stove
    coordinator = StoveDataUpdateCoordinator(hass, stove)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: StoveConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.destroy()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
