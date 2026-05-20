"""Intents for the text integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent

from .const import ATTR_VALUE, DOMAIN, SERVICE_SET_VALUE

INTENT_SET_VALUE = "HassTextSetValue"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the text intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_SET_VALUE,
            DOMAIN,
            SERVICE_SET_VALUE,
            description="Sets the value of a text entity",
            platforms={DOMAIN},
            required_slots={
                ATTR_VALUE: intent.IntentSlotInfo(
                    description="The text value to set",
                    value_schema=cv.string,
                )
            },
        ),
    )
