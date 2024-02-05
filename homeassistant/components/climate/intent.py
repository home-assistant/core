"""Intents for the client integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import intent
from homeassistant.helpers.entity_component import EntityComponent

from . import DOMAIN, ClimateEntity

INTENT_GET_TEMPERATURE = "HassClimateGetTemperature"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the climate intents."""
    intent.async_register(hass, GetTemperatureIntent())


class GetTemperatureIntent(intent.IntentHandler):
    """Handle GetTemperature intents."""

    intent_type = INTENT_GET_TEMPERATURE
    slot_schema = {vol.Optional("area"): str, vol.Optional("name"): str}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        component: EntityComponent[ClimateEntity] = hass.data[DOMAIN]
        entities: list[ClimateEntity] = list(component.entities)
        climate_entity: ClimateEntity | None = None
        climate_state: State | None = None

        if not entities:
            raise intent.IntentHandleError("No climate entities")

        if "area" in slots:
            # Filter by area
            area_name = slots["area"]["value"]

            for maybe_climate in intent.async_match_states(
                hass, area_name=area_name, domains=[DOMAIN]
            ):
                climate_state = maybe_climate
                break

            if climate_state is None:
                raise intent.IntentHandleError(f"No climate entity in area {area_name}")

            climate_entity = component.get_entity(climate_state.entity_id)
        elif "name" in slots:
            # Filter by name
            entity_name = slots["name"]["value"]

            for maybe_climate in intent.async_match_states(
                hass, name=entity_name, domains=[DOMAIN]
            ):
                climate_state = maybe_climate
                break

            if climate_state is None:
                raise intent.IntentHandleError(f"No climate entity named {entity_name}")

            climate_entity = component.get_entity(climate_state.entity_id)
        else:
            # First entity
            climate_entity = entities[0]
            climate_state = hass.states.get(climate_entity.entity_id)

        assert climate_entity is not None

        if climate_state is None:
            raise intent.IntentHandleError(f"No state for {climate_entity.name}")

        assert climate_state is not None

        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.QUERY_ANSWER
        response.async_set_states(matched_states=[climate_state])
        return response
