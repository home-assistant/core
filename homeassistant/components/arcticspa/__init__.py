"""The Arctic Spa integration."""
from __future__ import annotations

from http import HTTPStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ArcticSpaDataUpdateCoordinator
from .hottub import Device

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an Arctic Spa from a config entry."""

    device = Device(entry.data[CONF_API_KEY])
    code = await device.async_authenticate()
    if code != HTTPStatus.OK:
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ArcticSpaDataUpdateCoordinator(
        hass, device
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
