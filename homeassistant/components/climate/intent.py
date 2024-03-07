"""Intents for the client integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import intent
from homeassistant.helpers.entity_component import EntityComponent

from . import DOMAIN, ClimateEntity
from .const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
)

INTENT_GET_TEMPERATURE = "HassClimateGetTemperature"
INTENT_SET_TEMPERATURE = "HassClimateSetTemperature"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the climate intents."""
    intent.async_register(hass, GetTemperatureIntent())
    intent.async_register(hass, SetTemperatureIntent())


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

        name_slot = slots.get("name", {})
        entity_name: str | None = name_slot.get("value")
        entity_text: str | None = name_slot.get("text")

        area_slot = slots.get("area", {})
        area_id = area_slot.get("value")

        if area_id:
            # Filter by area and optionally name
            area_name = area_slot.get("text")

            for maybe_climate in intent.async_match_states(
                hass, name=entity_name, area_name=area_id, domains=[DOMAIN]
            ):
                climate_state = maybe_climate
                break

            if climate_state is None:
                raise intent.NoStatesMatchedError(
                    reason=intent.MatchFailedReason.AREA,
                    name=entity_text or entity_name,
                    area=area_name or area_id,
                    floor=None,
                    domains={DOMAIN},
                    device_classes=None,
                )

            climate_entity = component.get_entity(climate_state.entity_id)
        elif entity_name:
            # Filter by name
            for maybe_climate in intent.async_match_states(
                hass, name=entity_name, domains=[DOMAIN]
            ):
                climate_state = maybe_climate
                break

            if climate_state is None:
                raise intent.NoStatesMatchedError(
                    reason=intent.MatchFailedReason.NAME,
                    name=entity_name,
                    area=None,
                    floor=None,
                    domains={DOMAIN},
                    device_classes=None,
                )

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


class SetTemperatureIntent(intent.ServiceIntentHandler):
    """Intent handler for setting the temperature of a climate entity."""

    intent_type = INTENT_SET_TEMPERATURE

    def __init__(self) -> None:
        """Create set position handler."""
        super().__init__(
            INTENT_SET_TEMPERATURE,
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            extra_slots={ATTR_TEMPERATURE: vol.All(vol.Range(min=-100, max=200))},
        )

    async def async_call_service(
        self, domain: str, service: str, intent_obj: intent.Intent, state: State
    ) -> None:
        """Call service on entity with handling for special cases."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        target_temperature_slot = slots.get("temperature", {})
        target_temperature = target_temperature_slot.get("value")

        if target_temperature is None:
            raise intent.IntentHandleError("Target temperature missing")

        assert target_temperature is not None

        service_call_data = {ATTR_ENTITY_ID: state.entity_id}

        if ClimateEntityFeature.TARGET_TEMPERATURE in state.attributes.get(
            ATTR_SUPPORTED_FEATURES, []
        ):
            service_call_data.update({ATTR_TEMPERATURE: target_temperature})
        elif ClimateEntityFeature.TARGET_TEMPERATURE_RANGE in state.attributes.get(
            ATTR_SUPPORTED_FEATURES, []
        ):
            service_call_data.update(
                {
                    ATTR_TARGET_TEMP_LOW: target_temperature,
                    ATTR_TARGET_TEMP_HIGH: target_temperature,
                }
            )

        await self._run_then_background(
            hass.async_create_task(
                hass.services.async_call(
                    DOMAIN,
                    SERVICE_SET_TEMPERATURE,
                    service_call_data,
                    context=intent_obj.context,
                    blocking=True,
                )
            )
        )
