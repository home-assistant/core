"""Intents for the fan integration."""

import probatio

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import ATTR_PERCENTAGE, SERVICE_TURN_ON
from .const import DOMAIN

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
                    value_schema=probatio.All(
                        probatio.Coerce(int), probatio.Range(min=0, max=100)
                    ),
                )
            },
        ),
    )
