"""The BZUTech integration."""

from __future__ import annotations

from bzutech import BzuTech

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

PLATFORMS: list[Platform] = [Platform.SENSOR]

type BzuTechConfigEntry = ConfigEntry[BzuTech]


async def async_setup_entry(hass: HomeAssistant, entry: BzuTechConfigEntry) -> bool:
    """Set up BZUTech from a config entry."""
    bzu_api = BzuTech(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    if not await bzu_api.start():
        raise ConfigEntryNotReady("Invalid authentication")

    entry.runtime_data = bzu_api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
