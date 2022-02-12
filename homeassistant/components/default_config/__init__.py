"""Component providing default configuration for new users."""

try:
    import av
except ImportError:
    av = None

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

DOMAIN = "default_config"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize default configuration."""
    if av is None:
        return True

    return await async_setup_component(hass, "stream", config)
