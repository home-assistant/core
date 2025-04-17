"""Built-in Home Assistant conversation agent."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .const import CONVERSATION_DOMAIN, DOMAIN

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up assist conversation."""
    await async_load_platform(hass, CONVERSATION_DOMAIN, DOMAIN, config, config)
    return True
