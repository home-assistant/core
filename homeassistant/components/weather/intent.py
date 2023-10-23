"""Intents for the weather integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant
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
        slots = self.async_validate_slots(intent_obj.slots)

        weather: WeatherEntity | None = None
        component: EntityComponent[WeatherEntity] = intent_obj.hass.data[DOMAIN]
        entities = list(component.entities)

        if "name" in slots:
            # Named weather entity
            name = str(slots["name"]["value"]).strip().casefold()
            for maybe_weather in entities:
                if not isinstance(maybe_weather.name, str):
                    continue

                if maybe_weather.name.strip().casefold() == name:
                    weather = maybe_weather
                    break

            if weather is None:
                raise intent.IntentHandleError(f"No weather entity named {name}")

        if (weather is None) and entities:
            # First weather entity
            weather = entities[0]

        if weather is None:
            raise intent.IntentHandleError("No weather entity")

        assert weather is not None

        # Create response
        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.QUERY_ANSWER
        response.async_set_results(
            success_results=[
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.ENTITY,
                    name=weather.name if isinstance(weather.name, str) else "",
                    id=weather.entity_id,
                )
            ]
        )

        state = intent_obj.hass.states.get(weather.entity_id)
        if state is None:
            raise intent.IntentHandleError(f"No state for {weather.entity_id}")

        assert state is not None
        response.async_set_states(matched_states=[state])

        return response
