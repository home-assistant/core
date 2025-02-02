"""Assist Satellite intents."""

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, intent

from .const import DOMAIN, AssistSatelliteEntityFeature


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
        entities = {
            entity: entry
            for entity in hass.states.async_entity_ids(DOMAIN)
            if (entry := ent_reg.async_get(entity))
            and entry.supported_features & AssistSatelliteEntityFeature.ANNOUNCE
        }

        if intent_obj.device_id:
            entities = {
                entity: entry
                for entity, entry in entities.items()
                if entry.device_id != intent_obj.device_id
            }

        await hass.services.async_call(
            DOMAIN,
            "announce",
            {"message": intent_obj.slots["message"]["value"]},
            blocking=True,
            context=intent_obj.context,
            target={"entity_id": list(entities)},
        )

        response = intent_obj.create_response()
        response.async_set_speech("Done")
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
