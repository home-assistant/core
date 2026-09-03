"""Intents for the light integration."""

import logging
from typing import override

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.util import color as color_util

from . import (
    ATTR_BRIGHTNESS_PCT,
    ATTR_BRIGHTNESS_STEP_PCT,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    brightness_supported,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

INTENT_SET = "HassLightSet"
INTENT_SET_BRIGHTNESS_RELATIVE = "HassSetBrightnessRelative"

# Used when the sentence only says "up"/"down" without an amount.
DEFAULT_BRIGHTNESS_STEP_PCT = 10


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the light intents."""
    intent.async_register(hass, SetBrightnessRelativeHandler())
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
                    description=(
                        "The brightness percentage of the"
                        " light between 0 and 100, where 0"
                        " is off and 100 is fully lit"
                    ),
                    value_schema=vol.All(vol.Coerce(int), vol.Range(0, 100)),
                ),
            },
            description="Sets the brightness percentage or color of a light",
            required_domains={DOMAIN},
            platforms={DOMAIN},
        ),
    )


class SetBrightnessRelativeHandler(intent.IntentHandler):
    """Handler for increasing or decreasing the brightness of a light."""

    description = "Increases or decreases the brightness of a light"

    intent_type = INTENT_SET_BRIGHTNESS_RELATIVE
    slot_schema = {
        vol.Required("brightness_step"): vol.Any(
            "up",
            "down",
            vol.All(vol.Coerce(int), vol.Range(min=-100, max=100)),
        ),
        # Optional name/area/floor slots handled by intent matcher
        vol.Optional("name"): cv.string,
        vol.Optional("area"): cv.string,
        vol.Optional("floor"): cv.string,
        vol.Optional("preferred_area_id"): cv.string,
        vol.Optional("preferred_floor_id"): cv.string,
    }
    platforms = {DOMAIN}

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        brightness_step = slots["brightness_step"]["value"]
        if brightness_step == "up":
            brightness_step = DEFAULT_BRIGHTNESS_STEP_PCT
        elif brightness_step == "down":
            brightness_step = -DEFAULT_BRIGHTNESS_STEP_PCT

        match_constraints = intent.MatchTargetsConstraints(
            name=slots.get("name", {}).get("value"),
            area_name=slots.get("area", {}).get("value"),
            floor_name=slots.get("floor", {}).get("value"),
            domains={DOMAIN},
            assistant=intent_obj.assistant,
        )
        match_preferences = intent.MatchTargetsPreferences(
            area_id=slots.get("preferred_area_id", {}).get("value"),
            floor_id=slots.get("preferred_floor_id", {}).get("value"),
        )
        match_result = intent.async_match_targets(
            hass, match_constraints, match_preferences
        )
        if not match_result.is_match:
            raise intent.MatchFailedError(
                result=match_result,
                constraints=match_constraints,
                preferences=match_preferences,
            )

        match_result.states = [
            state
            for state in match_result.states
            if brightness_supported(state.attributes.get(ATTR_SUPPORTED_COLOR_MODES))
        ]
        if not match_result.states:
            raise intent.MatchFailedError(
                result=intent.MatchTargetsResult(
                    is_match=False, no_match_reason=intent.MatchFailedReason.FEATURE
                ),
                constraints=match_constraints,
                preferences=match_preferences,
            )

        try:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: [state.entity_id for state in match_result.states],
                    ATTR_BRIGHTNESS_STEP_PCT: brightness_step,
                },
                blocking=True,
                context=intent_obj.context,
            )
        except HomeAssistantError as err:
            _LOGGER.error("Error setting relative brightness: %s", err)
            raise intent.IntentHandleError(
                f"Error setting relative brightness: {err}"
            ) from err

        response = intent_obj.create_response()
        response.async_set_states(
            [hass.states.get(state.entity_id) or state for state in match_result.states]
        )
        return response
