"""Component for integrating entur public transport."""

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

PLATFORMS = (Platform.SENSOR,)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Entur integration."""
    if hass.config_entries.async_entries(DOMAIN):
        return True

    for sensor_config in config.get("sensor", []):
        if sensor_config.get("platform") != DOMAIN:
            continue
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=dict(sensor_config),
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Entur from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Entur config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
