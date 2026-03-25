"""Intents for the fan integration."""

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import ATTR_PERCENTAGE, DOMAIN, SERVICE_TURN_ON

INTENT_FAN_SET_SPEED = "HassFanSetSpeed"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the fan intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_FAN_SET_SPEED,
            DOMAIN,
            SERVICE_TURN_ON,
            description="Sets a fan's speed by percentage",
            required_domains={DOMAIN},
            platforms={DOMAIN},
            required_slots={
                ATTR_PERCENTAGE: intent.IntentSlotInfo(
                    description="The speed percentage of the fan",
                    value_schema=vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                )
            },
        ),
    )
