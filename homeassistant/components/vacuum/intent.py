"""Intents for the vacuum integration."""

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, config_validation as cv, intent

from . import (
    DOMAIN,
    SERVICE_CLEAN_AREA,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
    VacuumEntityFeature,
)

_LOGGER = logging.getLogger(__name__)

INTENT_VACUUM_START = "HassVacuumStart"
INTENT_VACUUM_RETURN_TO_BASE = "HassVacuumReturnToBase"
INTENT_VACUUM_CLEAN_AREA = "HassVacuumCleanArea"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the vacuum intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_VACUUM_START,
            DOMAIN,
            SERVICE_START,
            description="Starts a vacuum",
            required_domains={DOMAIN},
            platforms={DOMAIN},
            required_features=VacuumEntityFeature.START,
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_VACUUM_RETURN_TO_BASE,
            DOMAIN,
            SERVICE_RETURN_TO_BASE,
            description="Returns a vacuum to base",
            required_domains={DOMAIN},
            platforms={DOMAIN},
            required_features=VacuumEntityFeature.RETURN_HOME,
        ),
    )
    intent.async_register(hass, CleanAreaIntentHandler())


class CleanAreaIntentHandler(intent.IntentHandler):
    """Intent handler for cleaning a specific area with a vacuum.

    The area slot is used as a service parameter (cleaning_area_id),
    not for entity matching.
    """

    intent_type = INTENT_VACUUM_CLEAN_AREA
    platforms = {DOMAIN}
    description = "Tells a vacuum to clean a specific area"

    @property
    def slot_schema(self) -> dict:
        """Return a slot schema."""
        return {
            vol.Required("area"): cv.string,
            vol.Optional("name"): cv.string,
            vol.Optional("preferred_area_id"): cv.string,
            vol.Optional("preferred_floor_id"): cv.string,
        }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        # Resolve the area name to an area ID
        area_name = slots["area"]["value"]
        area_reg = ar.async_get(hass)
        matched_areas = list(intent.find_areas(area_name, area_reg))
        if not matched_areas:
            raise intent.MatchFailedError(
                result=intent.MatchTargetsResult(
                    is_match=False,
                    no_match_reason=intent.MatchFailedReason.INVALID_AREA,
                    no_match_name=area_name,
                ),
                constraints=intent.MatchTargetsConstraints(
                    area_name=area_name,
                ),
            )

        # Use preferred area/floor from conversation context to disambiguate
        preferred_area_id = slots.get("preferred_area_id", {}).get("value")
        preferred_floor_id = slots.get("preferred_floor_id", {}).get("value")
        if len(matched_areas) > 1 and preferred_area_id is not None:
            filtered = [a for a in matched_areas if a.id == preferred_area_id]
            if filtered:
                matched_areas = filtered
        if len(matched_areas) > 1 and preferred_floor_id is not None:
            filtered = [a for a in matched_areas if a.floor_id == preferred_floor_id]
            if filtered:
                matched_areas = filtered

        # Match vacuum entity by name
        name_slot = slots.get("name", {})
        entity_name: str | None = name_slot.get("value")

        match_constraints = intent.MatchTargetsConstraints(
            name=entity_name,
            domains={DOMAIN},
            features=VacuumEntityFeature.CLEAN_AREA,
            assistant=intent_obj.assistant,
        )

        # Use the resolved cleaning area and its floor as preferences
        # for entity disambiguation
        target_area = matched_areas[0]
        match_preferences = intent.MatchTargetsPreferences(
            area_id=target_area.id,
            floor_id=target_area.floor_id,
        )

        match_result = intent.async_match_targets(
            hass, match_constraints, match_preferences
        )
        if not match_result.is_match:
            raise intent.MatchFailedError(
                result=match_result,
                constraints=match_constraints,
                preferences=match_preferences,
            )

        # Update intent slots to include any transformations done by the schemas
        intent_obj.slots = slots

        return await self._async_handle_service(intent_obj, match_result, matched_areas)

    async def _async_handle_service(
        self,
        intent_obj: intent.Intent,
        match_result: intent.MatchTargetsResult,
        matched_areas: list[ar.AreaEntry],
    ) -> intent.IntentResponse:
        """Call clean_area for all matched areas."""
        hass = intent_obj.hass
        states = match_result.states

        entity_ids = [state.entity_id for state in states]
        area_ids = [area.id for area in matched_areas]

        try:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CLEAN_AREA,
                {
                    "entity_id": entity_ids,
                    "cleaning_area_id": area_ids,
                },
                context=intent_obj.context,
                blocking=True,
            )
        except Exception:
            _LOGGER.exception(
                "Failed to call %s for areas: %s with vacuums: %s",
                SERVICE_CLEAN_AREA,
                area_ids,
                entity_ids,
            )
            raise intent.IntentHandleError(
                f"Failed to call {SERVICE_CLEAN_AREA} for areas: {area_ids}"
                f" with vacuums: {entity_ids}"
            ) from None

        success_results: list[intent.IntentResponseTarget] = [
            intent.IntentResponseTarget(
                type=intent.IntentResponseTargetType.AREA,
                name=area.name,
                id=area.id,
            )
            for area in matched_areas
        ]
        success_results.extend(
            intent.IntentResponseTarget(
                type=intent.IntentResponseTargetType.ENTITY,
                name=state.name,
                id=state.entity_id,
            )
            for state in states
        )

        response = intent_obj.create_response()

        response.async_set_results(success_results)

        # Update all states
        states = [hass.states.get(state.entity_id) or state for state in states]
        response.async_set_states(states)

        return response
