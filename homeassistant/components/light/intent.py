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
                "color": intent.IntentSlotInfo(
                    service_data_name=ATTR_RGB_COLOR,
                    value_schema=color_util.color_name_to_rgb,
                ),
                "temperature": intent.IntentSlotInfo(
                    service_data_name=ATTR_COLOR_TEMP_KELVIN,
                    value_schema=cv.positive_int,
                ),
                "brightness": intent.IntentSlotInfo(
                    service_data_name=ATTR_BRIGHTNESS_PCT,
                    description="The brightness percentage of the light between 0 and 100, where 0 is off and 100 is fully lit",
                    value_schema=vol.All(vol.Coerce(int), vol.Range(0, 100)),
                ),
            },
            description="Sets the brightness percentage or color of a light",
            platforms={DOMAIN},
        ),
    )
