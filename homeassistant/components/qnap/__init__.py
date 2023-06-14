"""The qnap component."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady

from .const import DOMAIN
from .coordinator import QnapCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set the config entry up."""
    hass.data.setdefault(DOMAIN, {})
    coordinator = QnapCoordinator(hass, config_entry)
    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()
    if not coordinator.last_update_success:
        raise PlatformNotReady
    hass.data[DOMAIN][config_entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)
    return unload_ok
