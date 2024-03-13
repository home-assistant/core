"""Intents for the weather integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent

from . import DOMAIN, WeatherEntity

INTENT_GET_WEATHER = "HassGetWeather"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the weather intents."""
    intent.async_register(hass, GetWeatherIntent())


class GetWeatherIntent(intent.IntentHandler):
    """Handle GetWeather intents."""

    intent_type = INTENT_GET_WEATHER
    slot_schema = {vol.Optional("name"): cv.string}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        weather: WeatherEntity | None = None
        weather_state: State | None = None
        component: EntityComponent[WeatherEntity] = hass.data[DOMAIN]
        entities = list(component.entities)

        if "name" in slots:
            # Named weather entity
            weather_name = slots["name"]["value"]

            # Find matching weather entity
            matching_states = intent.async_match_states(
                hass, name=weather_name, domains=[DOMAIN]
            )
            for maybe_weather_state in matching_states:
                weather = component.get_entity(maybe_weather_state.entity_id)
                if weather is not None:
                    weather_state = maybe_weather_state
                    break

            if weather is None:
                raise intent.IntentHandleError(
                    f"No weather entity named {weather_name}"
                )
        elif entities:
            # First weather entity
            weather = entities[0]
            weather_name = weather.name
            weather_state = hass.states.get(weather.entity_id)

        if weather is None:
            raise intent.IntentHandleError("No weather entity")

        if weather_state is None:
            raise intent.IntentHandleError(f"No state for weather: {weather.name}")

        assert weather is not None
        assert weather_state is not None

        # Create response
        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.QUERY_ANSWER
        response.async_set_results(
            success_results=[
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.ENTITY,
                    name=weather_name,
                    id=weather.entity_id,
                )
            ]
        )

        response.async_set_states(matched_states=[weather_state])

        return response
