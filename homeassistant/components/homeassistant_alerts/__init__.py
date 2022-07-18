"""The Home Assistant alerts integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import alert
from .const import DOMAIN


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Home Assistant alerts."""
    hass.data[DOMAIN] = {}

    await alert.async_setup(hass)

    return True
