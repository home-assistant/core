"""The template component."""

import logging

from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import binary_sensor

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the template platform."""
    await binary_sensor.async_setup_helpers(hass)
    return True
