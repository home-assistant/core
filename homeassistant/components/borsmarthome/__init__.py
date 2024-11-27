"""The BorSmartHome integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from . import hub

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.COVER]

# TODO Create ConfigEntry type alias with API object
# TODO Rename type alias and update all entry annotations
type HubConfigEntry = ConfigEntry[hub.AveHub]  # noqa: F821


async def async_setup_entry(hass: HomeAssistant, entry: HubConfigEntry) -> bool:
    """Set up BorSmartHome from a config entry."""

    entry.runtime_data = avehub = hub.AveHub(
        hass, entry.data[CONF_HOST], entry.data[CONF_API_TOKEN]
    )

    await avehub.async_load_entities()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


# TODO Update entry annotation
async def async_unload_entry(hass: HomeAssistant, entry: HubConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
