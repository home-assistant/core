"""Assist Satellite intents."""

from typing import Final, override

import probatio

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, intent

from .const import DOMAIN, AssistSatelliteEntityFeature

EXCLUDED_DOMAINS: Final[set[str]] = {"voip"}


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the intents."""
    intent.async_register(hass, BroadcastIntentHandler())


@callback
def async_get_broadcast_entity_ids(
    hass: HomeAssistant, exclude_device_id: str | None
) -> list[str]:
    """Return the satellites a broadcast announces on."""
    ent_reg = er.async_get(hass)
    entity_ids: list[str] = []
    for entity_id in hass.states.async_entity_ids(DOMAIN):
        entry = ent_reg.async_get(entity_id)
        if (
            (entry is None)
            or not (entry.supported_features & AssistSatelliteEntityFeature.ANNOUNCE)
            or (exclude_device_id and (entry.device_id == exclude_device_id))
        ):
            continue

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

        entity_ids.append(entity_id)

    return entity_ids


class BroadcastIntentHandler(intent.IntentHandler):
    """Broadcast a message."""

    intent_type = intent.INTENT_BROADCAST
    description = "Broadcast a message through the home"

    @property
    @override
    def slot_schema(self) -> dict | None:
        """Return a slot schema."""
        return {probatio.Required("message"): str}

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Broadcast a message."""
        hass = intent_obj.hass
        entity_ids = async_get_broadcast_entity_ids(hass, intent_obj.device_id)

        await hass.services.async_call(
            DOMAIN,
            "announce",
            {"message": intent_obj.slots["message"]["value"]},
            blocking=True,
            context=intent_obj.context,
            target={"entity_id": entity_ids},
        )

        response = intent_obj.create_response()
        response.async_set_results(
            success_results=[
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.ENTITY,
                    id=entity,
                    name=state.name if (state := hass.states.get(entity)) else entity,
                )
                for entity in entity_ids
            ]
        )
        return response
