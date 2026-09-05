"""Intents for the climate integration."""

from typing import override

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv, intent, translation

from . import (
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_TEMPERATURE,
    DOMAIN,
    INTENT_SET_FAN_MODE,
    INTENT_SET_TEMPERATURE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
)

FAN_MODE_TRANSLATION_PREFIX = (
    f"component.{DOMAIN}.entity_component._.state_attributes.{ATTR_FAN_MODE}.state."
)


def _empty_or_non_empty_string(value: str) -> str:
    """Validate an empty or non-empty string."""
    if value == "":
        return value
    return intent.non_empty_string(value)


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the climate intents."""
    intent.async_register(hass, SetTemperatureIntent())
    intent.async_register(hass, SetFanModeIntent())


class SetTemperatureIntent(intent.IntentHandler):
    """Handle SetTemperature intents."""

    intent_type = INTENT_SET_TEMPERATURE
    description = "Sets the target temperature of a climate device or entity"
    slot_schema = {
        vol.Required("temperature"): vol.Coerce(float),
        vol.Optional("area"): _empty_or_non_empty_string,
        vol.Optional("name"): _empty_or_non_empty_string,
        vol.Optional("floor"): _empty_or_non_empty_string,
        vol.Optional("preferred_area_id"): cv.string,
        vol.Optional("preferred_floor_id"): cv.string,
    }
    platforms = {DOMAIN}

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        temperature: float = slots["temperature"]["value"]

        name: str | None = slots.get("name", {}).get("value") or None
        area_name: str | None = slots.get("area", {}).get("value") or None
        floor_name: str | None = slots.get("floor", {}).get("value") or None

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


class SetFanModeIntent(intent.IntentHandler):
    """Handle SetFanMode intents."""

    intent_type = INTENT_SET_FAN_MODE
    description = "Sets the fan mode of a climate device or entity"
    slot_schema = {
        vol.Required("fan_mode"): intent.non_empty_string,
        vol.Optional("area"): intent.non_empty_string,
        vol.Optional("name"): intent.non_empty_string,
        vol.Optional("floor"): intent.non_empty_string,
        vol.Optional("preferred_area_id"): cv.string,
        vol.Optional("preferred_floor_id"): cv.string,
    }
    platforms = {DOMAIN}

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        requested_fan_mode: str = slots["fan_mode"]["value"]

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
            features=ClimateEntityFeature.FAN_MODE,
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

        fan_mode = await _async_resolve_fan_mode(
            hass, intent_obj.language, climate_state, requested_fan_mode
        )
        if fan_mode is None:
            raise intent.IntentHandleError(
                f"Fan mode {requested_fan_mode} is not supported by "
                f"{climate_state.name}"
            )

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_FAN_MODE,
            service_data={ATTR_FAN_MODE: fan_mode},
            target={ATTR_ENTITY_ID: climate_state.entity_id},
            blocking=True,
            context=intent_obj.context,
        )

        response = intent_obj.create_response()
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


async def _async_resolve_fan_mode(
    hass: HomeAssistant, language: str, climate_state: State, requested: str
) -> str | None:
    """Return a matching fan mode using translations if necessary."""
    available: list[str] = climate_state.attributes.get(ATTR_FAN_MODES) or []
    if requested in available:
        return requested

    by_casefold = {mode.casefold(): mode for mode in available}
    if (fan_mode := by_casefold.get(requested.casefold())) is not None:
        return fan_mode

    translations = await translation.async_get_translations(
        hass, language, "entity_component", {DOMAIN}
    )
    for key, localized in translations.items():
        if key.startswith(FAN_MODE_TRANSLATION_PREFIX) and (
            localized.casefold() == requested.casefold()
        ):
            return by_casefold.get(key.removeprefix(FAN_MODE_TRANSLATION_PREFIX))

    return None
