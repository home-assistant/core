"""Intents for the input_number integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import DOMAIN, SERVICE_SET_VALUE

INTENT_SET_VALUE = "HassInputNumberSetValue"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the input_number intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_SET_VALUE,
            DOMAIN,
            SERVICE_SET_VALUE,
            description="Sets the value of an input number entity",
            platforms={DOMAIN},
            required_slots={
                "value": intent.IntentSlotInfo(
                    description="The numeric value to set",
                    value_schema=vol.Coerce(float),
                )
            },
        ),
    )
