"""The BorSmartHome integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import hub

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.COVER]

# TODO Create ConfigEntry type alias with API object
# TODO Rename type alias and update all entry annotations
type HubConfigEntry = ConfigEntry[hub.AveHub]  # noqa: F821


# TODO Update entry annotation
async def async_setup_entry(hass: HomeAssistant, entry: HubConfigEntry) -> bool:
    """Set up BorSmartHome from a config entry."""

    # TODO 1. Create API instance
    # TODO 2. Validate the API connection (and authentication)
    # TODO 3. Store an API object for your platforms to access
    # entry.runtime_data = MyAPI(...)

    # entry.runtime_data = TapparellaEntity("Tapparella test")
    entry.runtime_data = hub.AveHub(hass, "192.168.1.10")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


# TODO Update entry annotation
async def async_unload_entry(hass: HomeAssistant, entry: HubConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
