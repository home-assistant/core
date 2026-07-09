"""LLM tools for the homeassistant integration."""

from decimal import Decimal
from enum import Enum
from operator import attrgetter
from typing import Any, override

import voluptuous as vol

from homeassistant.components.llm import LLMTools
from homeassistant.components.sensor import SensorDeviceClass, async_rounded_state
from homeassistant.const import EntityStateAttribute
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    intent,
)
from homeassistant.helpers.llm import (
    LLM_API_ASSIST,
    NO_ENTITIES_PROMPT,
    LLMContext,
    Tool,
    ToolInput,
)
from homeassistant.util import dt as dt_util, yaml as yaml_util
from homeassistant.util.json import JsonObjectType

from .exposed_entities import async_should_expose

# Domains bucketed out of the exposed-entity overview.
CALENDAR_DOMAIN = "calendar"
SCRIPT_DOMAIN = "script"


@callback
def async_get_exposed_entities(
    hass: HomeAssistant,
    assistant: str,
    include_state: bool = True,
) -> dict[str, dict[str, Any]]:
    """Get exposed entities, ignoring calendars and scripts."""
    area_registry = ar.async_get(hass)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    interesting_attributes = {
        "temperature",
        "current_temperature",
        "temperature_unit",
        "brightness",
        "humidity",
        "unit_of_measurement",
        "device_class",
        "current_position",
        "percentage",
        "volume_level",
        "media_title",
        "media_artist",
        "media_album_name",
    }

    entities: dict[str, dict[str, Any]] = {}

    for state in sorted(hass.states.async_all(), key=attrgetter("name")):
        if not async_should_expose(hass, assistant, state.entity_id):
            continue

        # Calendars and scripts have their own tools; skip them here.
        if state.domain in (CALENDAR_DOMAIN, SCRIPT_DOMAIN):
            continue

        entity_entry = entity_registry.async_get(state.entity_id)
        device_entry = (
            device_registry.async_get(entity_entry.device_id)
            if entity_entry is not None and entity_entry.device_id is not None
            else None
        )
        names = intent.async_get_entity_aliases(hass, entity_entry, state=state)
        area_names = []

        if entity_entry is not None:
            if (
                entity_entry.area_id is not None
                and (area_entry := area_registry.async_get_area(entity_entry.area_id))
                is not None
            ):
                # Entity is in area
                area_names.append(area_entry.name)
                area_names.extend(sorted(area_entry.aliases))
            elif device_entry is not None:
                # Check device area
                if (
                    device_entry.area_id is not None
                    and (
                        area_entry := area_registry.async_get_area(device_entry.area_id)
                    )
                    is not None
                ):
                    area_names.append(area_entry.name)
                    area_names.extend(sorted(area_entry.aliases))

        info: dict[str, Any] = {
            "names": ", ".join(names),
            "domain": state.domain,
        }

        if include_state:
            info["state"] = state.state

            # Format numeric states with configured display precision
            if state.domain == "sensor":
                info["state"] = async_rounded_state(hass, state.entity_id, state)

            # Convert timestamp device_class states from UTC to local time
            if (
                state.attributes.get(EntityStateAttribute.DEVICE_CLASS)
                == SensorDeviceClass.TIMESTAMP
                and state.state
            ):
                if (parsed_utc := dt_util.parse_datetime(state.state)) is not None:
                    info["state"] = dt_util.as_local(parsed_utc).isoformat()

        if area_names:
            info["areas"] = ", ".join(area_names)

        if include_state and (
            attributes := {
                str(attr_name): (
                    str(attr_value)
                    if isinstance(attr_value, (Enum, Decimal, int))
                    else attr_value
                )
                for attr_name, attr_value in state.attributes.items()
                if attr_name in interesting_attributes
            }
        ):
            info["attributes"] = attributes

        entities[state.entity_id] = info

    return entities


def _live_context_match_error(
    match_result: intent.MatchTargetsResult,
    name_filter: str | None,
    area_filter: str | None,
    domain_filter: list[str] | None,
) -> str:
    """Build an actionable error message for a failed GetLiveContext match."""
    reason = match_result.no_match_reason
    if reason is intent.MatchFailedReason.INVALID_AREA:
        return f"Area '{match_result.no_match_name}' does not exist"
    if reason is intent.MatchFailedReason.NAME:
        return f"No exposed entities matched name '{name_filter}'"
    if reason is intent.MatchFailedReason.AREA:
        return f"No exposed entities found in area '{area_filter}'"
    if reason is intent.MatchFailedReason.DOMAIN:
        domains = ", ".join(domain_filter) if domain_filter else ""
        return f"No exposed entities found in domain(s): {domains}"
    return "No entities matched the provided filter"


class GetLiveContextTool(Tool):
    """Tool for getting the current state of exposed entities.

    This returns state for all entities that have been exposed to
    the assistant. This is different than the GetState intent, which
    returns state for entities based on intent parameters.
    """

    name = "GetLiveContext"
    description = (
        "Provides real-time information about the"
        " CURRENT state, value, or mode of devices,"
        " sensors, entities, or areas. "
        "Use this tool for: "
        "1. Answering questions about current"
        " conditions (e.g., 'Is the light on?'). "
        "2. As the first step in conditional actions"
        " (e.g., 'If the weather is rainy, turn off"
        " sprinklers' requires checking the weather"
        " first). "
        "You may filter for devices by name, domain,"
        " and area, including combining those"
        " filters. "
        "Prefer filtering by domain when searching"
        " for multiple devices of the same type."
    )
    parameters = vol.Schema(
        {
            vol.Optional(
                "name",
                description="Filter entities by name or alias (case-insensitive).",
            ): cv.string,
            vol.Optional(
                "domain",
                description=(
                    "Filter entities by domain"
                    " (e.g. 'light', 'sensor')."
                    " Accepts a single domain or a list."
                ),
            ): vol.Any(cv.string, [cv.string]),
            vol.Optional(
                "area",
                description="Filter entities by area name or alias (case-insensitive).",
            ): cv.string,
        }
    )

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: ToolInput,
        llm_context: LLMContext,
    ) -> JsonObjectType:
        """Get the current state of exposed entities."""
        args = self.parameters(tool_input.tool_args)
        exposed_entities = async_get_exposed_entities(hass, llm_context.assistant)

        if not exposed_entities:
            return {"success": False, "error": NO_ENTITIES_PROMPT}

        name_filter = args.get("name")
        area_filter = args.get("area")
        domain_filter = args.get("domain")

        if isinstance(domain_filter, str):
            domain_filter = [domain_filter]

        if domain_filter is not None:
            domain_filter = [
                normalized_domain
                for domain in domain_filter
                if (normalized_domain := domain.strip().lower())
            ]

        if name_filter or area_filter or domain_filter:
            exposed_states = [
                state
                for entity_id in exposed_entities
                if (state := hass.states.get(entity_id)) is not None
            ]
            match_result = intent.async_match_targets(
                hass,
                intent.MatchTargetsConstraints(
                    name=name_filter,
                    area_name=area_filter,
                    domains=domain_filter,
                    # This tool only returns context, so multiple entities
                    # sharing a name (e.g. "AC" in two areas) should all be
                    # returned rather than failing as an ambiguous match.
                    allow_duplicate_names=True,
                ),
                states=exposed_states,
            )

            if not match_result.is_match:
                return {
                    "success": False,
                    "error": _live_context_match_error(
                        match_result, name_filter, area_filter, domain_filter
                    ),
                }

            matched_ids = {state.entity_id for state in match_result.states}
            entities = [
                info
                for entity_id, info in exposed_entities.items()
                if entity_id in matched_ids
            ]
        else:
            entities = list(exposed_entities.values())

        prompt = [
            "Live Context: An overview of the areas"
            " and the devices in this smart home:",
            yaml_util.dump(entities),
        ]
        return {
            "success": True,
            "result": "\n".join(prompt),
        }


class GetCurrentLocationTool(Tool):
    """Tool for getting the area (and floor) of the requesting device."""

    name = "GetCurrentLocation"
    description = (
        "Returns the user's current area, and floor when set. "
        "Call this to resolve the area when a request names a generic "
        "device without specifying one."
    )

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: ToolInput,
        llm_context: LLMContext,
    ) -> JsonObjectType:
        """Get the area and floor of the requesting device."""
        if not llm_context.device_id:
            return {
                "success": False,
                "error": "This request is not associated with a device",
            }

        device = dr.async_get(hass).async_get(llm_context.device_id)
        if device is None:
            return {
                "success": False,
                "error": "The requesting device was not found",
            }
        if device.area_id is None:
            return {
                "success": False,
                "error": "The requesting device is not assigned to an area",
            }

        area = ar.async_get(hass).async_get_area(device.area_id)
        if area is None:
            return {
                "success": False,
                "error": "The area assigned to the requesting device was not found",
            }

        result: dict[str, Any] = {"area": area.name}
        if area.floor_id and (
            floor := fr.async_get(hass).async_get_floor(area.floor_id)
        ):
            result["floor"] = floor.name

        return {"success": True, "result": result}


GENERIC_DEVICE_WITH_AREA_PROMPT = (
    "When a request names a generic device without an area, "
    "treat it as the user's current area and call "
    "`GetCurrentLocation` to resolve it before targeting."
)
GENERIC_DEVICE_WITHOUT_AREA_PROMPT = (
    "When a request names a generic device without an area, "
    "ask the user to specify which area they mean before targeting."
)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the homeassistant integration's LLM tools.

    GetLiveContext is always offered and reports when nothing is exposed at
    call time. GetCurrentLocation is offered only when the request carries a
    device_id, and the prompt directs the model to resolve the current area
    through it rather than embedding a per-device area in the system prompt,
    which keeps the prompt cacheable across speakers.
    """
    if api_id != LLM_API_ASSIST:
        return None

    tools: list[Tool] = [GetLiveContextTool()]

    if llm_context.device_id:
        tools.append(GetCurrentLocationTool())
        prompt = GENERIC_DEVICE_WITH_AREA_PROMPT
    else:
        prompt = GENERIC_DEVICE_WITHOUT_AREA_PROMPT

    return LLMTools(tools=tools, prompt=prompt)
