"""Support for launching a web browser on the host machine."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import setup_services

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Listen for browse_url events."""
    setup_services(hass)
    return True
