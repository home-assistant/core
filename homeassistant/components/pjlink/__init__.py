"""The PJLink integration."""

from __future__ import annotations

from aiopjlink import PJLink

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

_PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

type PJLinkConfigEntry = ConfigEntry[PJLink]


async def async_setup_entry(hass: HomeAssistant, entry: PJLinkConfigEntry) -> bool:
    """Set up PJLink from a config entry."""

    client = PJLink(
        entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data.get(CONF_PASSWORD)
    )

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PJLinkConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
