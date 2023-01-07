"""The EVSE Wifi integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, CONF_INTERVAL, CONF_MAX_CURRENT, CONF_NAME, DOMAIN
from .evse import EVSE

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EVSE Wifi from a config entry."""

    evse = EVSE(
        name=entry.data[CONF_NAME],
        host=entry.data[CONF_HOST],
        max_current=entry.data[CONF_MAX_CURRENT],
        interval=entry.data[CONF_INTERVAL],
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = evse

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
