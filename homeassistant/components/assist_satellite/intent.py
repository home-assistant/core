"""Assist Satellite intents."""

from typing import Final

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, intent

from .const import DOMAIN, AssistSatelliteEntityFeature

EXCLUDED_DOMAINS: Final[set[str]] = {"voip"}


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the intents."""
    intent.async_register(hass, BroadcastIntentHandler())


class BroadcastIntentHandler(intent.IntentHandler):
    """Broadcast a message."""

    intent_type = intent.INTENT_BROADCAST
    description = "Broadcast a message through the home"

    @property
    def slot_schema(self) -> dict | None:
        """Return a slot schema."""
        return {vol.Required("message"): str}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Broadcast a message."""
        hass = intent_obj.hass
        ent_reg = er.async_get(hass)

        # Find all assist satellite entities that are not the one invoking the intent
        entities: dict[str, er.RegistryEntry] = {}
        for entity in hass.states.async_entity_ids(DOMAIN):
            entry = ent_reg.async_get(entity)
            if (
                (entry is None)
                or (
                    # Supports announce
                    not (
                        entry.supported_features & AssistSatelliteEntityFeature.ANNOUNCE
                    )
                )
                # Not the invoking device
                or (intent_obj.device_id and (entry.device_id == intent_obj.device_id))
            ):
                # Skip satellite
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

            entities[entity] = entry

        await hass.services.async_call(
            DOMAIN,
            "announce",
            {"message": intent_obj.slots["message"]["value"]},
            blocking=True,
            context=intent_obj.context,
            target={"entity_id": list(entities)},
        )

        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.ACTION_DONE
        response.async_set_results(
            success_results=[
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.ENTITY,
                    id=entity,
                    name=state.name if (state := hass.states.get(entity)) else entity,
                )
                for entity in entities
            ]
        )
        return response
