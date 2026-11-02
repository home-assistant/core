"""Intents for the light integration."""

import logging

import probatio

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.util import color as color_util

from .const import DOMAIN, LightService, LightServiceArgument

_LOGGER = logging.getLogger(__name__)

INTENT_SET = "HassLightSet"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the light intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_SET,
            DOMAIN,
            LightService.TURN_ON,
            optional_slots={
                "color": intent.IntentSlotInfo(
                    service_data_name=LightServiceArgument.RGB_COLOR,
                    value_schema=color_util.color_name_to_rgb,
                ),
                "temperature": intent.IntentSlotInfo(
                    service_data_name=LightServiceArgument.COLOR_TEMP_KELVIN,
                    value_schema=cv.positive_int,
                ),
                "brightness": intent.IntentSlotInfo(
                    service_data_name=LightServiceArgument.BRIGHTNESS_PCT,
                    description=(
                        "The brightness percentage of the"
                        " light between 0 and 100, where 0"
                        " is off and 100 is fully lit"
                    ),
                    value_schema=probatio.All(
                        probatio.Coerce(int), probatio.Range(0, 100)
                    ),
                ),
            },
            description="Sets the brightness percentage or color of a light",
            required_domains={DOMAIN},
            platforms={DOMAIN},
        ),
    )
