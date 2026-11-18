"""The Code Mode integration."""

from homeassistant.components.conversation import DATA_CODE_MODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import async_create_api_instance
from .const import DOMAIN

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Make Code Mode available to conversations."""
    hass.data[DATA_CODE_MODE] = async_create_api_instance
    return True
