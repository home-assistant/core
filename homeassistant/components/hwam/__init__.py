"""The HWAM Smart Control integration."""

from __future__ import annotations

from hwamsmartctrl.airbox import Airbox

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import StoveDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE]

type AirboxConfigEntry = ConfigEntry[Airbox]  # noqa: F821


async def async_setup_entry(hass: HomeAssistant, entry: AirboxConfigEntry) -> bool:
    """Set up HWAM Smart Control from a config entry."""

    ip = entry.data[CONF_HOST]
    airbox = Airbox(ip)
    entry.runtime_data = airbox
    coordinator = StoveDataUpdateCoordinator(hass, airbox)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirboxConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
