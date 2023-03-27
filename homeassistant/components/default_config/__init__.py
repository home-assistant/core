"""Component providing default configuration for new users."""
from homeassistant.components.hassio import is_hassio
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

DOMAIN = "default_config"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize default configuration."""
    if not is_hassio(hass):
        await async_setup_component(hass, "backup", config)

    return True
