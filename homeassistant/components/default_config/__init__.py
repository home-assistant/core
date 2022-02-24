"""Component providing default configuration for new users."""

try:
    import av
except ImportError:
    av = None

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN
from homeassistant.components.hassio import is_hassio
from homeassistant.components.stream import DOMAIN as STREAM_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

DOMAIN = "default_config"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize default configuration."""
    if not is_hassio(hass):
        await async_setup_component(hass, BACKUP_DOMAIN, config)

    if av is None:
        return True

    return await async_setup_component(hass, STREAM_DOMAIN, config)
