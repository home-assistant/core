"""Intents for the fan integration."""

import probatio

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .const import DOMAIN, FanService, FanServiceArgument

INTENT_FAN_SET_SPEED = "HassFanSetSpeed"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the fan intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_FAN_SET_SPEED,
            DOMAIN,
            FanService.TURN_ON,
            description="Sets a fan's speed by percentage",
            required_domains={DOMAIN},
            platforms={DOMAIN},
            required_slots={
                FanServiceArgument.PERCENTAGE: intent.IntentSlotInfo(
                    description="The speed percentage of the fan",
                    value_schema=probatio.All(
                        probatio.Coerce(int), probatio.Percentage()
                    ),
                )
            },
        ),
    )
