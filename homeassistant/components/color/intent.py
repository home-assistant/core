"""Intents for the Color helper."""

from typing import Any, override

import voluptuous as vol

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import intent
from homeassistant.util import color as color_util

from .const import (
    DOMAIN,
    FIELD_BRIGHTNESS,
    FIELD_KELVIN,
    FIELD_RGB,
    MAX_KELVIN,
    MIN_KELVIN,
    SERVICE_SET_BRIGHTNESS,
    SERVICE_SET_COLOR,
)

INTENT_SET = "HassColorSet"

# Slots that carry a color. Their absence is what routes a brightness-only
# command to `set_brightness`, since `set_color` requires a color.
COLOR_SLOTS = ("color", "temperature")


def _brightness_pct_to_value(value: Any) -> int:
    """Convert a spoken brightness percentage to the stored 0-255 scale.

    Assist expresses brightness as a percentage everywhere else, so the
    intent takes a percentage and converts, rather than making callers
    say "brightness 128".
    """
    percentage: int = vol.All(vol.Coerce(int), vol.Range(min=0, max=100))(value)
    return round(percentage * 255 / 100)


class ColorSetIntentHandler(intent.DynamicServiceIntentHandler):
    """Set the color, the color temperature, and/or the brightness.

    `set_color` rejects a call with no color, so a command that only
    adjusts brightness has to reach `set_brightness` instead.
    """

    @override
    def get_domain_and_service(
        self, intent_obj: intent.Intent, state: State
    ) -> tuple[str, str]:
        """Route to the service that matches the slots that were filled."""
        if any(slot in intent_obj.slots for slot in COLOR_SLOTS):
            return (DOMAIN, SERVICE_SET_COLOR)
        return (DOMAIN, SERVICE_SET_BRIGHTNESS)


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the color intents."""
    intent.async_register(
        hass,
        ColorSetIntentHandler(
            INTENT_SET,
            # Constrain matching to this domain rather than relying on the
            # sentence templates to pass a `domain` slot.
            required_domains={DOMAIN},
            optional_slots={
                "color": intent.IntentSlotInfo(
                    service_data_name=FIELD_RGB,
                    # Same vocabulary the light intent uses, so a color name
                    # means the same thing whether it is spoken at a light or
                    # at a color helper. The result is a tuple, and
                    # `cv.ensure_list` would wrap rather than convert it.
                    value_schema=vol.All(
                        color_util.color_name_to_rgb, vol.Coerce(list)
                    ),
                ),
                "temperature": intent.IntentSlotInfo(
                    service_data_name=FIELD_KELVIN,
                    description=(
                        "The color temperature in Kelvin, between"
                        f" {MIN_KELVIN} and {MAX_KELVIN}"
                    ),
                    value_schema=vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_KELVIN, max=MAX_KELVIN)
                    ),
                ),
                "brightness": intent.IntentSlotInfo(
                    service_data_name=FIELD_BRIGHTNESS,
                    description=(
                        "The brightness percentage stored alongside the color,"
                        " between 0 and 100"
                    ),
                    value_schema=_brightness_pct_to_value,
                ),
            },
            description="Sets the color, color temperature or brightness of a color helper",
            platforms={DOMAIN},
        ),
    )
