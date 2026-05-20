"""Intents for the number integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .const import DOMAIN, SERVICE_SET_VALUE

INTENT_SET_VALUE = "HassNumberSetValue"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the number intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_SET_VALUE,
            DOMAIN,
            SERVICE_SET_VALUE,
            description="Sets the value of a number entity",
            platforms={DOMAIN},
            required_slots={
                "value": intent.IntentSlotInfo(
                    description="The numeric value to set",
                    value_schema=vol.Coerce(float),
                )
            },
        ),
    )
