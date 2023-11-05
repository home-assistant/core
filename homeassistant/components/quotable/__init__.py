"""The Quotable integration."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Quotable integration."""
    _LOGGER.info("WIP: Setting up the Quotable integration")

    hass.states.set(f"{DOMAIN}.testing", "It Works!")

    return True
