"""Intents for the client integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import DOMAIN

INTENT_GET_TEMPERATURE = "HassClimateGetTemperature"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the climate intents."""
    intent.async_register(hass, GetTemperatureIntent())


class GetTemperatureIntent(intent.IntentHandler):
    """Handle GetTemperature intents."""

    intent_type = INTENT_GET_TEMPERATURE
    description = "Gets the current temperature of a climate device or entity"
    slot_schema = {
        vol.Optional("area"): intent.non_empty_string,
        vol.Optional("name"): intent.non_empty_string,
    }
    platforms = {DOMAIN}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        name: str | None = None
        if "name" in slots:
            name = slots["name"]["value"]

        area: str | None = None
        if "area" in slots:
            area = slots["area"]["value"]

        match_constraints = intent.MatchTargetsConstraints(
            name=name, area_name=area, domains=[DOMAIN], assistant=intent_obj.assistant
        )
        match_result = intent.async_match_targets(hass, match_constraints)
        if not match_result.is_match:
            raise intent.MatchFailedError(
                result=match_result, constraints=match_constraints
            )

        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.QUERY_ANSWER
        response.async_set_states(matched_states=match_result.states)
        return response
