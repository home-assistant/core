"""Built-in Home Assistant conversation agent."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .conversation import async_setup_default_agent

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up assist conversation."""
    await async_setup_default_agent(hass, config)
    return True
