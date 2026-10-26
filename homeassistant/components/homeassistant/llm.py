"""LLM tools for the homeassistant integration."""

from collections.abc import Iterator
from decimal import Decimal
from enum import Enum
from operator import attrgetter
from typing import Any, override

import probatio

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.llm import LLMTools
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    async_rounded_state,
)
from homeassistant.const import EntityStateAttribute
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    intent,
    translation,
)
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.llm import (
    LLM_API_ASSIST,
    LLM_API_HOME_ASSISTANT,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.helpers.template import Template
from homeassistant.util import dt as dt_util, yaml as yaml_util

from .const import DOMAIN
from .exposed_entities import async_should_expose

# Domains bucketed out of the exposed-entity overview.
CALENDAR_DOMAIN = "calendar"
SCRIPT_DOMAIN = "script"

TEMPLATE_RENDER_TIMEOUT = 3
TEMPLATE_MAX_OUTPUT = 16 * 1024

ACTION_SEARCH_LIMIT = 3
ACTION_DESCRIPTION_MAX_SIZE = 16 * 1024

NO_ENTITIES_PROMPT = (
    "Only if the user wants to control a device, tell them to expose entities "
    "to their voice assistant in Home Assistant."
)

DYNAMIC_CONTEXT_PROMPT = (
    "You ARE equipped to answer questions about the"
    " current state of\n"
    "the home by retrieving live context."
    " This is a primary function."
    " Do not state you lack the\n"
    "functionality if the question requires live data.\n"
    "If the user asks about device existence/type"
    ' (e.g., "Do I have lights in the bedroom?"):'
    " Answer\n"
    "from the static context below.\n"
    "If the user asks about the CURRENT state, value,"
    ' or mode (e.g., "Is the lock locked?",\n'
    '"Is the fan on?",'
    ' "What mode is the thermostat in?",'
    ' "What is the temperature outside?"):\n'
    "    1.  Recognize this requires live data.\n"
    "    2.  You MUST use the provided tool to retrieve live context."
    " This tool will provide the needed real-time"
    " information (like temperature from the local"
    " weather, lock status, etc.).\n"
    "    3.  Use the tool's response to answer the"
    " user accurately, stating the actual value or"
    " state it returned.\n"
    "For general knowledge questions not about the"
    " home: Answer truthfully from internal"
    " knowledge.\n"
)


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
                # Check the device's effective area
                if (
                    device_area_id := dr.async_get_effective_area_id(hass, device_entry)
                ) is not None and (
                    area_entry := area_registry.async_get_area(device_area_id)
                ) is not None:
                    area_names.append(area_entry.name)
                    area_names.extend(sorted(area_entry.aliases))

        info: dict[str, Any] = {
            "names": ", ".join(names),
            "domain": state.domain,
        }

        if include_state:
            info["state"] = state.state

            # Format numeric states with configured display precision
            if state.domain == SENSOR_DOMAIN:
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
            # Tools take brightness as a 0-100 percentage; the attribute is 0-255.
            if state.domain == LIGHT_DOMAIN and isinstance(
                brightness := state.attributes.get("brightness"), int
            ):
                pct = round(brightness / 255 * 100)
                attributes["brightness_pct"] = str(
                    max(pct, 1) if brightness > 0 else pct
                )
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

    name = "homeassistant__GetLiveContext"
    title = "Get live context"
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
    annotations = ToolAnnotations(read_only=True, open_world=False)
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "name",
                description="Filter entities by name or alias (case-insensitive).",
            ): cv.string,
            probatio.Optional(
                "domain",
                description=(
                    "Filter entities by domain"
                    " (e.g. 'light', 'sensor')."
                    " Accepts a single domain or a list."
                ),
            ): probatio.Any(cv.string, [cv.string]),
            probatio.Optional(
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
    ) -> ToolResult:
        """Get the current state of exposed entities."""
        args = self.parameters(tool_input.tool_args)
        exposed_entities = async_get_exposed_entities(hass, llm_context.assistant)

        if not exposed_entities:
            return ToolResult(data={"error": NO_ENTITIES_PROMPT}, error=True)

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
                return ToolResult(
                    data={
                        "error": _live_context_match_error(
                            match_result, name_filter, area_filter, domain_filter
                        )
                    },
                    error=True,
                )

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
        return ToolResult(data={"result": "\n".join(prompt)})


class RenderTemplateTool(Tool):
    """Tool for rendering a template."""

    name = "homeassistant__render_template"
    title = "Render template"
    description = (
        "Render a Home Assistant Jinja2 template and return the output as a string. "
        "Templates can read the state and attributes of all entities and use "
        "Home Assistant template functions, for example for areas, devices, "
        "labels, and time."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "template", description="The Jinja2 template to render."
            ): cv.string,
            probatio.Optional(
                "variables",
                description=(
                    "Variables available to the template, for example sample "
                    "trigger data: {'trigger': {'to_state': {'state': 'on'}}}."
                ),
            ): dict,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Render the template."""
        args = self.parameters(tool_input.tool_args)
        variables = args.get("variables")
        template = Template(args["template"], hass)
        try:
            # Renders in a thread first, so a slow template cannot block the event loop.
            if await template.async_render_will_timeout(
                TEMPLATE_RENDER_TIMEOUT, variables, strict=True
            ):
                return ToolResult(
                    data={
                        "error": "Template rendering exceeded the maximum time of "
                        f"{TEMPLATE_RENDER_TIMEOUT} seconds"
                    },
                    error=True,
                )
            result = template.async_render(variables, parse_result=False, strict=True)
        except TemplateError as err:
            return ToolResult(data={"error": str(err)}, error=True)
        if len(result) > TEMPLATE_MAX_OUTPUT:
            return ToolResult(
                data={
                    "error": f"Template output of {len(result)} characters exceeded "
                    f"the maximum of {TEMPLATE_MAX_OUTPUT} characters"
                },
                error=True,
            )
        return ToolResult(data={"result": result})


def _action_fields(fields: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield the fields of an action, including the fields inside sections."""
    for field, config in fields.items():
        if "fields" in config:
            yield from config["fields"].items()
        else:
            yield field, config


def _describe_action(
    action_id: str, action_description: dict[str, Any], translations: dict[str, str]
) -> dict[str, Any]:
    """Return the name, description, target and fields of an action."""
    domain, action = action_id.split(".", 1)
    key = f"component.{domain}.services.{action}"
    placeholders = action_description.get("description_placeholders", {})

    def text(config: dict[str, Any], item: str, translation_key: str) -> str:
        """Return a text of the description, else its translation."""
        value = config.get(item) or translations.get(translation_key, "")
        for placeholder, replacement in placeholders.items():
            value = value.replace(f"{{{placeholder}}}", replacement)
        return value

    fields: dict[str, dict[str, Any]] = {}
    for field, config in _action_fields(action_description["fields"]):
        field_info: dict[str, Any] = {}
        if description := text(
            config, "description", f"{key}.fields.{field}.description"
        ):
            field_info["description"] = description
        if config.get("required"):
            field_info["required"] = True
        if "selector" in config:
            field_info["selector"] = config["selector"]
        fields[field] = field_info

    result: dict[str, Any] = {
        "action": action_id,
        "name": text(action_description, "name", f"{key}.name"),
        "description": text(action_description, "description", f"{key}.description"),
        "fields": fields,
    }
    if "target" in action_description:
        # An empty target accepts any entity, device, area, floor or label
        result["target"] = action_description["target"] or {}
    return result


class SearchActionsTool(Tool):
    """Tool for searching the actions that Home Assistant can perform."""

    name = "homeassistant__search_actions"
    title = "Search actions"
    description = (
        "Search the actions that Home Assistant can perform. Each word of the query "
        "must appear in the action ID, name or description. An exact action ID or "
        "name ranks first. Returns the "
        f"{ACTION_SEARCH_LIMIT} best matches with their target and fields."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "query",
                description="Words to find, case-insensitive, e.g. 'light turn on'.",
            ): probatio.All(str, probatio.NonEmpty()),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Search the actions."""
        args = self.parameters(tool_input.tool_args)
        query = args["query"].strip().casefold()
        words = query.replace("_", " ").split()
        descriptions = await async_get_all_descriptions(hass)
        translations = await translation.async_get_translations(
            hass, "en", "services", descriptions
        )

        matches: list[tuple[int, str, dict[str, Any]]] = []
        for domain, domain_actions in descriptions.items():
            for action, action_description in domain_actions.items():
                found = _describe_action(
                    f"{domain}.{action}", action_description, translations
                )
                head = f"{found['action']} {found['name']}".replace("_", " ").casefold()
                text = f"{head} {found['description'].casefold()}"
                if not all(word in text for word in words):
                    continue
                # Exact matches first, then matches on ID and name, then description
                if query in (found["action"], found["name"].casefold()):
                    rank = 0
                elif all(word in head for word in words):
                    rank = 1
                else:
                    rank = 2
                matches.append((rank, found["action"], found))
        matches.sort(key=lambda match: match[:2])

        actions = [found for _, _, found in matches[:ACTION_SEARCH_LIMIT]]
        for found in actions:
            # Some actions list so many select options that they would fill the context
            if len(json_dumps(found)) > ACTION_DESCRIPTION_MAX_SIZE:
                for field_info in found["fields"].values():
                    field_info.pop("selector", None)
                found["note"] = (
                    "The selectors of the fields are left out to save space."
                )
        result: dict[str, Any] = {"actions": actions}
        if len(matches) > ACTION_SEARCH_LIMIT:
            result["more"] = (
                f"{len(matches)} actions match. Use a more specific query to "
                "find the others."
            )
        return ToolResult(data=result)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the homeassistant LLM tools for the given API."""
    if api_id == LLM_API_HOME_ASSISTANT:
        return LLMTools(tools=[RenderTemplateTool(), SearchActionsTool()])

    if api_id != LLM_API_ASSIST:
        return None

    exposed_entities = async_get_exposed_entities(
        hass, llm_context.assistant, include_state=False
    )
    if exposed_entities:
        prompt = "\n".join(
            [
                DYNAMIC_CONTEXT_PROMPT,
                "Static Context: An overview of the areas"
                " and the devices in this smart home:",
                yaml_util.dump(list(exposed_entities.values())),
            ]
        )
    else:
        prompt = NO_ENTITIES_PROMPT

    return LLMTools(tools=[GetLiveContextTool()], prompt=prompt)
