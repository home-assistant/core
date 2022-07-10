"""The eq3btsmart component."""

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

PLATFORMS = [Platform.CLIMATE]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up eq3 environment."""
    if (conf := config.get("climate")) is None:
        return True
    # TODO: note hard coded pieces, how to properly initialize from the old platform-based config?
    # This just misuses the config data to pass the name along for the config flow.
    for config_entry in conf:
        for name, data in config_entry["devices"].items():
            data["name"] = name
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data=data,
                ),
            )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up songpal media player."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload songpal media player."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
