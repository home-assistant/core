"""Intents for the client integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
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
    slot_schema = {vol.Optional("area"): str}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        component: EntityComponent[ClimateEntity] = hass.data[DOMAIN]
        entities: list[ClimateEntity] = list(component.entities)
        climate_entity: ClimateEntity | None = None

        if not entities:
            raise intent.IntentHandleError("No climate entities")

        if "area" in slots:
            # Filter by area
            area_name = slots["area"]["value"]
            climate_state: State | None = None

            for maybe_climate in intent.async_match_states(
                hass, area_name=area_name, domains=[DOMAIN]
            ):
                climate_state = maybe_climate
                break

            if climate_state is None:
                raise intent.IntentHandleError(f"No climate entity in area {area_name}")

            climate_entity = component.get_entity(climate_state.entity_id)
        else:
            # First entity
            climate_entity = entities[0]

        assert climate_entity is not None

        if climate_entity.current_temperature is None:
            raise intent.IntentHandleError(
                f"No temperature for entity: {climate_entity.entity_id}"
            )

        # Construct a state that will be compatible with intent sentences
        temperature_state = State(
            entity_id=climate_entity.entity_id,
            state=str(
                hass.config.units.temperature(
                    climate_entity.current_temperature,
                    climate_entity.temperature_unit,
                )
            ),
            attributes={
                ATTR_UNIT_OF_MEASUREMENT: hass.config.units.temperature_unit,
            },
        )

        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.QUERY_ANSWER
        response.async_set_states(matched_states=[temperature_state])
        return response
