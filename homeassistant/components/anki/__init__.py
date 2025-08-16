"""The Anki integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict):
    return True


async def async_setup_entry(hass: HomeAssistant, entry, async_add_devices=None) -> bool:
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True
