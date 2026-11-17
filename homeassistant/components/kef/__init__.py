"""The KEF Wireless Speakers component."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import async_setup_services

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the KEF Wireless Speakers component."""
    async_setup_services(hass)
    return True
