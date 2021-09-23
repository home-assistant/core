"""Platform for the Escea fireplace."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import ESCEA
from .discovery import async_start_discovery_service, async_stop_discovery_service

PLATFORMS = ["climate"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the Escea component config."""
    conf = config.get(ESCEA)
    if not conf:
        return True

    # Explicitly added in the config file, create a config entry.
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            ESCEA, context={"source": config_entries.SOURCE_IMPORT}
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Set up from a config entry."""
    await async_start_discovery_service(hass)
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Unload the config entry and stop discovery process."""
    await async_stop_discovery_service(hass)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
