"""Intents for the light integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
import homeassistant.util.color as color_util

from . import ATTR_BRIGHTNESS_PCT, ATTR_RGB_COLOR, DOMAIN

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
                ("brightness", ATTR_BRIGHTNESS_PCT): vol.All(
                    vol.Coerce(int), vol.Range(0, 100)
                ),
            },
            description="Sets the brightness or color of a light",
        ),
    )
