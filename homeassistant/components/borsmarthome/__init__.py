"""The BorSmartHome integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from . import hub

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.COVER]

type HubConfigEntry = ConfigEntry[hub.AveHub]


async def async_setup_entry(hass: HomeAssistant, entry: HubConfigEntry) -> bool:
    """Set up BorSmartHome from a config entry."""

    entry.runtime_data = avehub = hub.AveHub(
        hass, entry.data[CONF_HOST], entry.data[CONF_API_TOKEN]
    )

    await avehub.async_load_entities()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HubConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.session.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
