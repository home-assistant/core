"""HelloWorld integration for Home Assistant."""

import logging

from homeassistant.config_entries import ConfigType
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HelloWorld integration."""
    _LOGGER.warning("Hello from my demo change!")
    hass.states.async_set("helloworld.world", "Hello, state!")
    return True
