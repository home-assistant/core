"""Intents for the weather integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import intent

from . import DOMAIN

INTENT_GET_WEATHER = "HassGetWeather"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the weather intents."""
    intent.async_register(hass, GetWeatherIntent())


class GetWeatherIntent(intent.IntentHandler):
    """Handle GetWeather intents."""

    intent_type = INTENT_GET_WEATHER
    description = "Gets the current weather"
    slot_schema = {vol.Optional("name"): intent.non_empty_string}
    platforms = {DOMAIN}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        weather_state: State | None = None
        name: str | None = None
        if "name" in slots:
            name = slots["name"]["value"]

        match_constraints = intent.MatchTargetsConstraints(
            name=name, domains=[DOMAIN], assistant=intent_obj.assistant
        )
        match_result = intent.async_match_targets(hass, match_constraints)
        if not match_result.is_match:
            raise intent.MatchFailedError(
                result=match_result, constraints=match_constraints
            )

        weather_state = match_result.states[0]

        # Create response
        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.QUERY_ANSWER
        response.async_set_results(
            success_results=[
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.ENTITY,
                    name=weather_state.name,
                    id=weather_state.entity_id,
                )
            ]
        )

        response.async_set_states(matched_states=[weather_state])

        return response
