"""OpenAI functions to be called from GPT."""

import json
import logging

from homeassistant.components.conversation import DOMAIN as CONVERSATION_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, intent, template

from .const import EXPORTED_ATTRIBUTES

_LOGGER = logging.getLogger(__name__)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "entity_registry_inquiry",
            "description": "Get entities defined in Home Assistant",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Return the entity with this name only.",
                    },
                    "area": {
                        "type": "string",
                        "description": "Return entities in this area only.",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Return entities with this domain only. Only valid Home Assistant domains are accepted.",
                    },
                    "device_class": {
                        "type": "string",
                        "description": "Return entities with this device class. Only valid Home Assistant device classes are accepted.",
                    },
                    "state": {
                        "type": "string",
                        "description": "Return entities with this state only.",
                    },
                },
                "required": [],
            },
        },
    }
]


@callback
def call_function(hass: HomeAssistant, function_name: str, function_args: str) -> dict:
    """Wrap the function call to parse the arguments and handle exceptions."""

    available_functions = {"entity_registry_inquiry": entity_registry_inquiry}

    _LOGGER.debug("Function call: %s(%s)", function_name, function_args)

    try:
        function_to_call = available_functions[function_name]
        function_args = json.loads(function_args)
        response = function_to_call(hass, **function_args)
        response = json.dumps(response)

    except Exception as e:
        response = {"error": type(e).__name__}
        if len(str(e)):
            response["error_text"] = str(e)
        response = json.dumps(response)

    _LOGGER.debug("Function response: %s", response)

    return response


@callback
def entity_registry_inquiry(
    hass: HomeAssistant,
    name: str | None = None,
    area: str | None = None,
    domain: str | None = None,
    device_class: str | None = None,
    state: str | None = None,
) -> dict:
    """Get entities defined in Home Assistant."""

    states = intent.async_match_states(
        hass,
        name=name,
        area_name=area,
        domains=[domain] if domain is not None else None,
        device_classes=[device_class] if device_class is not None else None,
        assistant=CONVERSATION_DOMAIN,
    )

    entity_registry = er.async_get(hass)
    result = []

    for entity_state in states:
        entity_state = template.TemplateState(hass, entity_state, collect=False)

        if (
            state is not None
            and entity_state.state != state
            and entity_state.state_with_unit != state
        ):
            continue

        entry = {
            "name": entity_state.name,
            "entity_id": entity_state.entity_id,
            "state": entity_state.state_with_unit,
        }

        if registry_entry := entity_registry.async_get(entity_state.entity_id):
            if area_name := template.area_name(hass, entity_state.entity_id):
                entry["area"] = area_name
            if len(registry_entry.aliases):
                entry["aliases"] = registry_entry.aliases

        attributes = {}
        for attribute, value in entity_state.attributes.items():
            if attribute in EXPORTED_ATTRIBUTES:
                attributes[attribute] = value
        if attributes:
            entry["attributes"] = attributes

        result.append(entry)

    if result:
        return {"entities": result}

    error_text = "Entities matching the criteria are not found or not exposed"
    if device_class:
        error_text += (
            ". Please note that not all entities have device_class set up,"
            " so you may want to repeat the function call without device_class parameter"
            " if the expected entities were not found."
        )
    return {"error": error_text}
