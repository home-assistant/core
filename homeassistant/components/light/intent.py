"""Intents for the light integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.util import color as color_util

from . import ATTR_BRIGHTNESS_PCT, ATTR_COLOR_TEMP_KELVIN, ATTR_RGB_COLOR
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

INTENT_SET = "HassLightSet"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the light intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_SET,
            DOMAIN,
            SERVICE_TURN_ON,
            optional_slots={
                ("color", ATTR_RGB_COLOR): color_util.color_name_to_rgb,
                ("temperature", ATTR_COLOR_TEMP_KELVIN): cv.positive_int,
                (
                    "brightness",
                    ATTR_BRIGHTNESS_PCT,
                    "The brightness percentage of the light between 0 and 100, where 0 is off and 100 is fully lit",
                ): vol.All(vol.Coerce(int), vol.Range(0, 100)),
            },
            description="Sets the brightness percentage or color",
            platforms={DOMAIN},
        ),
    )
