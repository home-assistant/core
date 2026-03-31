"""Intents for the input_select integration."""

from __future__ import annotations

from homeassistant.components.select import ATTR_OPTION, ATTR_OPTIONS, SERVICE_SELECT_OPTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent

from . import DOMAIN

INTENT_SELECT_OPTION = "HassInputSelectSelectOption"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the input_select intents."""
    intent.async_register(hass, InputSelectOptionIntentHandler())


class InputSelectOptionIntentHandler(intent.ServiceIntentHandler):
    """Handle input_select option intents."""

    def __init__(self) -> None:
        """Create input_select option handler."""
        super().__init__(
            INTENT_SELECT_OPTION,
            DOMAIN,
            SERVICE_SELECT_OPTION,
            description="Selects an option for an input select entity",
            platforms={DOMAIN},
            required_slots={
                ATTR_OPTION: intent.IntentSlotInfo(
                    description="The option to select",
                    value_schema=cv.string,
                )
            },
        )

    async def async_handle_states(
        self,
        intent_obj: intent.Intent,
        match_result: intent.MatchTargetsResult,
        match_constraints: intent.MatchTargetsConstraints,
        match_preferences: intent.MatchTargetsPreferences | None = None,
    ) -> intent.IntentResponse:
        """Validate option against each matched entity before calling the service."""
        option = intent_obj.slots[ATTR_OPTION]["value"]
        for state in match_result.states:
            valid_options = state.attributes.get(ATTR_OPTIONS) or []
            if option not in valid_options:
                raise intent.IntentHandleError(
                    f"Entity {state.name} does not support option '{option}'. "
                    f"Valid options are: {valid_options}"
                )
        return await super().async_handle_states(
            intent_obj, match_result, match_constraints, match_preferences
        )
