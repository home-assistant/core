"""Intents for the climate integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent

from . import (
    ATTR_TEMPERATURE,
    DOMAIN,
    INTENT_SET_TEMPERATURE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
)


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the climate intents."""
    intent.async_register(hass, SetTemperatureIntent())


class SetTemperatureIntent(intent.IntentHandler):
    """Handle SetTemperature intents."""

    intent_type = INTENT_SET_TEMPERATURE
    description = "Sets the target temperature of a climate device or entity"
    slot_schema = {
        vol.Required("temperature"): vol.Coerce(float),
        vol.Optional("area"): intent.non_empty_string,
        vol.Optional("name"): intent.non_empty_string,
        vol.Optional("floor"): intent.non_empty_string,
        vol.Optional("preferred_area_id"): cv.string,
        vol.Optional("preferred_floor_id"): cv.string,
    }
    platforms = {DOMAIN}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        temperature: float = slots["temperature"]["value"]

        name: str | None = None
        if "name" in slots:
            name = slots["name"]["value"]

        area_name: str | None = None
        if "area" in slots:
            area_name = slots["area"]["value"]

        floor_name: str | None = None
        if "floor" in slots:
            floor_name = slots["floor"]["value"]

        match_constraints = intent.MatchTargetsConstraints(
            name=name,
            area_name=area_name,
            floor_name=floor_name,
            domains=[DOMAIN],
            assistant=intent_obj.assistant,
            features=ClimateEntityFeature.TARGET_TEMPERATURE,
            single_target=True,
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
                result=match_result, constraints=match_constraints
            )

        assert match_result.states
        climate_state = match_result.states[0]

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            service_data={ATTR_TEMPERATURE: temperature},
            target={ATTR_ENTITY_ID: climate_state.entity_id},
            blocking=True,
        )

        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.ACTION_DONE
        response.async_set_results(
            success_results=[
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.ENTITY,
                    name=climate_state.name,
                    id=climate_state.entity_id,
                )
            ]
        )
        response.async_set_states(matched_states=[climate_state])
        return response
