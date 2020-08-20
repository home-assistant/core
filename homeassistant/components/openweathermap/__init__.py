from homeassistant.core import Config, HomeAssistant

from .const import (
    ATTR_FORECAST,
    CONF_FORECAST,
    COORDINATOR,
    DOMAIN,
)

PLATFORMS = ["sensor", "weather"]


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured OpenWeatherMap."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass, config_entry) -> bool:
    """Set up configured OpenWeatherMap."""
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )
    return True
