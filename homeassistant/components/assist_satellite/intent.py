"""Assist Satellite intents."""

from typing import Final

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er, intent

from .const import DOMAIN, AssistSatelliteEntityFeature

EXCLUDED_DOMAINS: Final[set[str]] = {"voip"}


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the intents."""
    intent.async_register(hass, BroadcastIntentHandler())


class BroadcastIntentHandler(intent.IntentHandler):
    """Broadcast a message."""

    intent_type = intent.INTENT_BROADCAST
    description = (
        "Broadcast a message through the home to specific areas, floors, or satellites"
    )

    @property
    def slot_schema(self) -> dict | None:
        """Return a slot schema."""
        return {
            vol.Required("message"): str,
            vol.Optional("name"): intent.non_empty_string,
            vol.Optional("area"): intent.non_empty_string,
            vol.Optional("floor"): intent.non_empty_string,
            vol.Optional("preferred_area_id"): cv.string,
            vol.Optional("preferred_floor_id"): cv.string,
        }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Broadcast a message."""
        hass = intent_obj.hass
        ent_reg = er.async_get(hass)
        slots = self.async_validate_slots(intent_obj.slots)

        # Extract message and optional targeting parameters
        message = slots["message"]["value"]
        name = slots.get("name", {}).get("value")
        area_name = slots.get("area", {}).get("value")
        floor_name = slots.get("floor", {}).get("value")

        # Build constraints for entity matching
        match_constraints = intent.MatchTargetsConstraints(
            name=name,
            area_name=area_name,
            floor_name=floor_name,
            domains=[DOMAIN],
            features=AssistSatelliteEntityFeature.ANNOUNCE,
            assistant=None,  # Don't filter by assistant - broadcast to all satellites
            single_target=False,
        )

        # Build preferences for disambiguation
        match_preferences = intent.MatchTargetsPreferences(
            area_id=slots.get("preferred_area_id", {}).get("value"),
            floor_id=slots.get("preferred_floor_id", {}).get("value"),
        )

        # Match entities based on constraints
        match_result = intent.async_match_targets(
            hass, match_constraints, match_preferences
        )

        # Raise error if no matches found (invalid area/floor/name)
        if not match_result.is_match:
            raise intent.MatchFailedError(
                result=match_result, constraints=match_constraints
            )

        # Post-filter: exclude invoking device and excluded domains
        filtered_states = []
        for state in match_result.states:
            entry = ent_reg.async_get(state.entity_id)
            if entry is None:
                continue

            # Exclude invoking device
            if intent_obj.device_id and (entry.device_id == intent_obj.device_id):
                continue

            # Check domain of config entry against excluded domains
            if (
                entry.config_entry_id
                and (
                    config_entry := hass.config_entries.async_get_entry(
                        entry.config_entry_id
                    )
                )
                and (config_entry.domain in EXCLUDED_DOMAINS)
            ):
                continue

            filtered_states.append(state)

        # Call announce service with filtered entities
        if filtered_states:
            await hass.services.async_call(
                DOMAIN,
                "announce",
                {"message": message},
                blocking=True,
                context=intent_obj.context,
                target={"entity_id": [state.entity_id for state in filtered_states]},
            )

        # Build response
        response = intent_obj.create_response()
        response.async_set_results(
            success_results=[
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.ENTITY,
                    id=state.entity_id,
                    name=state.name,
                )
                for state in filtered_states
            ]
        )
        return response
