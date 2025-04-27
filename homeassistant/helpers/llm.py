"""Module to coordinate llm tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field as dc_field
from datetime import timedelta
from decimal import Decimal
from enum import Enum
from functools import cache, partial
from operator import attrgetter
from typing import Any, cast

import slugify as unicode_slug
import voluptuous as vol
from voluptuous_openapi import UNSUPPORTED, convert

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    SERVICE_GET_EVENTS,
)
from homeassistant.components.cover import INTENT_CLOSE_COVER, INTENT_OPEN_COVER
from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.intent import async_device_supports_timers
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.components.todo import DOMAIN as TODO_DOMAIN, TodoServices
from homeassistant.components.weather import INTENT_GET_WEATHER
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_SERVICE,
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_SERVICE_REMOVED,
)
from homeassistant.core import Context, Event, HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util, yaml as yaml_util
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import JsonObjectType
from homeassistant.util.ulid import ulid_now

from . import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    intent,
    selector,
    service,
)
from .singleton import singleton

ACTION_PARAMETERS_CACHE: HassKey[
    dict[str, dict[str, tuple[str | None, vol.Schema]]]
] = HassKey("llm_action_parameters_cache")


LLM_API_ASSIST = "assist"

BASE_PROMPT = (
    'Current time is {{ now().strftime("%H:%M:%S") }}. '
    'Today\'s date is {{ now().strftime("%Y-%m-%d") }}.\n'
)

DEFAULT_INSTRUCTIONS_PROMPT = """You are a voice assistant for Home Assistant.
Answer questions about the world truthfully.
Answer in plain text. Keep it simple and to the point.
"""

NO_ENTITIES_PROMPT = (
    "Only if the user wants to control a device, tell them to expose entities "
    "to their voice assistant in Home Assistant."
)

DYNAMIC_CONTEXT_PROMPT = """You ARE equipped to answer questions about the current state of
the home using the `GetLiveContext` tool. This is a primary function. Do not state you lack the
functionality if the question requires live data.
If the user asks about device existence/type (e.g., "Do I have lights in the bedroom?"): Answer
from the static context below.
If the user asks about the CURRENT state, value, or mode (e.g., "Is the lock locked?",
"Is the fan on?", "What mode is the thermostat in?", "What is the temperature outside?"):
    1.  Recognize this requires live data.
    2.  You MUST call `GetLiveContext`. This tool will provide the needed real-time information (like temperature from the local weather, lock status, etc.).
    3.  Use the tool's response** to answer the user accurately (e.g., "The temperature outside is [value from tool].").
For general knowledge questions not about the home: Answer truthfully from internal knowledge.
"""


@callback
def async_render_no_api_prompt(hass: HomeAssistant) -> str:
    """Return the prompt to be used when no API is configured.

    No longer used since Home Assistant 2024.7.
    """
    return ""


@singleton("llm")
@callback
def _async_get_apis(hass: HomeAssistant) -> dict[str, API]:
    """Get all the LLM APIs."""
    return {
        LLM_API_ASSIST: AssistAPI(hass=hass),
    }


@callback
def async_register_api(hass: HomeAssistant, api: API) -> Callable[[], None]:
    """Register an API to be exposed to LLMs."""
    apis = _async_get_apis(hass)

    if api.id in apis:
        raise HomeAssistantError(f"API {api.id} is already registered")

    apis[api.id] = api

    @callback
    def unregister() -> None:
        """Unregister the API."""
        apis.pop(api.id)

    return unregister


async def async_get_api(
    hass: HomeAssistant, api_id: str | list[str], llm_context: LLMContext
) -> APIInstance:
    """Get an API.

    This returns a single APIInstance for one or more API ids, merging into
    a single instance of necessary.
    """
    apis = _async_get_apis(hass)

    if isinstance(api_id, str):
        api_id = [api_id]

    for key in api_id:
        if key not in apis:
            raise HomeAssistantError(f"API {key} not found")

    api: API
    if len(api_id) == 1:
        api = apis[api_id[0]]
    else:
        api = MergedAPI([apis[key] for key in api_id])

    return await api.async_get_api_instance(llm_context)


@callback
def async_get_apis(hass: HomeAssistant) -> list[API]:
    """Get all the LLM APIs."""
    return list(_async_get_apis(hass).values())


@dataclass(slots=True)
class LLMContext:
    """Tool input to be processed."""

    platform: str
    context: Context | None
    user_prompt: str | None
    language: str | None
    assistant: str | None
    device_id: str | None


@dataclass(slots=True)
class ToolInput:
    """Tool input to be processed."""

    tool_name: str
    tool_args: dict[str, Any]
    # Using lambda for default to allow patching in tests
    id: str = dc_field(default_factory=lambda: ulid_now())  # pylint: disable=unnecessary-lambda


class Tool:
    """LLM Tool base class."""

    name: str
    description: str | None = None
    parameters: vol.Schema = vol.Schema({})

    @abstractmethod
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Call the tool."""
        raise NotImplementedError

    def __repr__(self) -> str:
        """Represent a string of a Tool."""
        return f"<{self.__class__.__name__} - {self.name}>"


@dataclass
class APIInstance:
    """Instance of an API to be used by an LLM."""

    api: API
    api_prompt: str
    llm_context: LLMContext
    tools: list[Tool]
    custom_serializer: Callable[[Any], Any] | None = None

    async def async_call_tool(self, tool_input: ToolInput) -> JsonObjectType:
        """Call a LLM tool, validate args and return the response."""
        # pylint: disable=import-outside-toplevel
        from homeassistant.components.conversation import (
            ConversationTraceEventType,
            async_conversation_trace_append,
        )

        async_conversation_trace_append(
            ConversationTraceEventType.TOOL_CALL,
            {"tool_name": tool_input.tool_name, "tool_args": tool_input.tool_args},
        )

        for tool in self.tools:
            if tool.name == tool_input.tool_name:
                break
        else:
            raise HomeAssistantError(f'Tool "{tool_input.tool_name}" not found')

        return await tool.async_call(self.api.hass, tool_input, self.llm_context)


@dataclass(slots=True, kw_only=True)
class API(ABC):
    """An API to expose to LLMs."""

    hass: HomeAssistant
    id: str
    name: str

    @abstractmethod
    async def async_get_api_instance(self, llm_context: LLMContext) -> APIInstance:
        """Return the instance of the API."""
        raise NotImplementedError


class IntentTool(Tool):
    """LLM Tool representing an Intent."""

    def __init__(
        self,
        name: str,
        intent_handler: intent.IntentHandler,
    ) -> None:
        """Init the class."""
        self.name = name
        self.description = (
            intent_handler.description or f"Execute Home Assistant {self.name} intent"
        )
        self.extra_slots = None
        if not (slot_schema := intent_handler.slot_schema):
            return

        slot_schema = {**slot_schema}
        extra_slots = set()

        for field in ("preferred_area_id", "preferred_floor_id"):
            if field in slot_schema:
                extra_slots.add(field)
                del slot_schema[field]

        self.parameters = vol.Schema(slot_schema)
        if extra_slots:
            self.extra_slots = extra_slots

    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Handle the intent."""
        slots = {key: {"value": val} for key, val in tool_input.tool_args.items()}

        if self.extra_slots and llm_context.device_id:
            device_reg = dr.async_get(hass)
            device = device_reg.async_get(llm_context.device_id)

            area: ar.AreaEntry | None = None
            floor: fr.FloorEntry | None = None
            if device:
                area_reg = ar.async_get(hass)
                if device.area_id and (area := area_reg.async_get_area(device.area_id)):
                    if area.floor_id:
                        floor_reg = fr.async_get(hass)
                        floor = floor_reg.async_get_floor(area.floor_id)

            for slot_name, slot_value in (
                ("preferred_area_id", area.id if area else None),
                ("preferred_floor_id", floor.floor_id if floor else None),
            ):
                if slot_value and slot_name in self.extra_slots:
                    slots[slot_name] = {"value": slot_value}

        intent_response = await intent.async_handle(
            hass=hass,
            platform=llm_context.platform,
            intent_type=self.name,
            slots=slots,
            text_input=llm_context.user_prompt,
            context=llm_context.context,
            language=llm_context.language,
            assistant=llm_context.assistant,
            device_id=llm_context.device_id,
        )
        response = intent_response.as_dict()
        del response["language"]
        del response["card"]
        return response


class NamespacedTool(Tool):
    """A tool that wraps another tool, prepending a namespace.

    This is used to support tools from multiple API. This tool dispatches
    the original tool with the original non-namespaced name.
    """

    def __init__(self, namespace: str, tool: Tool) -> None:
        """Init the class."""
        self.namespace = namespace
        self.name = f"{namespace}.{tool.name}"
        self.description = tool.description
        self.parameters = tool.parameters
        self.tool = tool

    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Handle the intent."""
        return await self.tool.async_call(
            hass,
            ToolInput(
                tool_name=self.tool.name,
                tool_args=tool_input.tool_args,
                id=tool_input.id,
            ),
            llm_context,
        )


class MergedAPI(API):
    """An API that represents a merged view of multiple APIs."""

    def __init__(self, llm_apis: list[API]) -> None:
        """Init the class."""
        if not llm_apis:
            raise ValueError("No APIs provided")
        hass = llm_apis[0].hass
        api_ids = [unicode_slug.slugify(api.id) for api in llm_apis]
        if len(set(api_ids)) != len(api_ids):
            raise ValueError("API IDs must be unique")
        super().__init__(
            hass=hass,
            id="|".join(unicode_slug.slugify(api.id) for api in llm_apis),
            name="Merged LLM API",
        )
        self.llm_apis = llm_apis

    async def async_get_api_instance(self, llm_context: LLMContext) -> APIInstance:
        """Return the instance of the API."""
        # These usually don't do I/O and execute right away
        llm_apis = [
            await llm_api.async_get_api_instance(llm_context)
            for llm_api in self.llm_apis
        ]
        prompt_parts = []
        tools: list[Tool] = []
        for api_instance in llm_apis:
            namespace = unicode_slug.slugify(api_instance.api.name)
            prompt_parts.append(
                f'Follow these instructions for tools from "{namespace}":\n'
            )
            prompt_parts.append(api_instance.api_prompt)
            prompt_parts.append("\n\n")
            tools.extend(
                [NamespacedTool(namespace, tool) for tool in api_instance.tools]
            )

        return APIInstance(
            api=self,
            api_prompt="".join(prompt_parts),
            llm_context=llm_context,
            tools=tools,
            custom_serializer=self._custom_serializer(llm_apis),
        )

    def _custom_serializer(
        self, llm_apis: list[APIInstance]
    ) -> Callable[[Any], Any] | None:
        serializers = [
            api_instance.custom_serializer
            for api_instance in llm_apis
            if api_instance.custom_serializer is not None
        ]
        if not serializers:
            return None

        def merged(x: Any) -> Any:
            for serializer in serializers:
                if (result := serializer(x)) is not None:
                    return result
            return x

        return merged


class AssistAPI(API):
    """API exposing Assist API to LLMs."""

    IGNORE_INTENTS = {
        intent.INTENT_GET_TEMPERATURE,
        INTENT_GET_WEATHER,
        INTENT_OPEN_COVER,  # deprecated
        INTENT_CLOSE_COVER,  # deprecated
        intent.INTENT_GET_STATE,
        intent.INTENT_NEVERMIND,
        intent.INTENT_TOGGLE,
        intent.INTENT_GET_CURRENT_DATE,
        intent.INTENT_GET_CURRENT_TIME,
        intent.INTENT_RESPOND,
    }

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the class."""
        super().__init__(
            hass=hass,
            id=LLM_API_ASSIST,
            name="Assist",
        )
        self.cached_slugify = cache(
            partial(unicode_slug.slugify, separator="_", lowercase=False)
        )

    async def async_get_api_instance(self, llm_context: LLMContext) -> APIInstance:
        """Return the instance of the API."""
        if llm_context.assistant:
            exposed_entities: dict | None = _get_exposed_entities(
                self.hass, llm_context.assistant, include_state=False
            )
        else:
            exposed_entities = None

        return APIInstance(
            api=self,
            api_prompt=self._async_get_api_prompt(llm_context, exposed_entities),
            llm_context=llm_context,
            tools=self._async_get_tools(llm_context, exposed_entities),
            custom_serializer=_selector_serializer,
        )

    @callback
    def _async_get_api_prompt(
        self, llm_context: LLMContext, exposed_entities: dict | None
    ) -> str:
        if not exposed_entities or not exposed_entities["entities"]:
            return NO_ENTITIES_PROMPT
        return "\n".join(
            [
                *self._async_get_preable(llm_context),
                *self._async_get_exposed_entities_prompt(llm_context, exposed_entities),
            ]
        )

    @callback
    def _async_get_preable(self, llm_context: LLMContext) -> list[str]:
        """Return the prompt for the API."""

        prompt = [
            (
                "When controlling Home Assistant always call the intent tools. "
                "Use HassTurnOn to lock and HassTurnOff to unlock a lock. "
                "When controlling a device, prefer passing just name and domain. "
                "When controlling an area, prefer passing just area name and domain."
            )
        ]
        area: ar.AreaEntry | None = None
        floor: fr.FloorEntry | None = None
        if llm_context.device_id:
            device_reg = dr.async_get(self.hass)
            device = device_reg.async_get(llm_context.device_id)

            if device:
                area_reg = ar.async_get(self.hass)
                if device.area_id and (area := area_reg.async_get_area(device.area_id)):
                    floor_reg = fr.async_get(self.hass)
                    if area.floor_id:
                        floor = floor_reg.async_get_floor(area.floor_id)

            extra = "and all generic commands like 'turn on the lights' should target this area."

        if floor and area:
            prompt.append(f"You are in area {area.name} (floor {floor.name}) {extra}")
        elif area:
            prompt.append(f"You are in area {area.name} {extra}")
        else:
            prompt.append(
                "When a user asks to turn on all devices of a specific type, "
                "ask user to specify an area, unless there is only one device of that type."
            )

        if not llm_context.device_id or not async_device_supports_timers(
            self.hass, llm_context.device_id
        ):
            prompt.append("This device is not able to start timers.")

        prompt.append(DYNAMIC_CONTEXT_PROMPT)

        return prompt

    @callback
    def _async_get_exposed_entities_prompt(
        self, llm_context: LLMContext, exposed_entities: dict | None
    ) -> list[str]:
        """Return the prompt for the API for exposed entities."""
        prompt = []

        if exposed_entities and exposed_entities["entities"]:
            prompt.append(
                "Static Context: An overview of the areas and the devices in this smart home:"
            )
            prompt.append(yaml_util.dump(list(exposed_entities["entities"].values())))

        return prompt

    @callback
    def _async_get_tools(
        self, llm_context: LLMContext, exposed_entities: dict | None
    ) -> list[Tool]:
        """Return a list of LLM tools."""
        ignore_intents = self.IGNORE_INTENTS
        if not llm_context.device_id or not async_device_supports_timers(
            self.hass, llm_context.device_id
        ):
            ignore_intents = ignore_intents | {
                intent.INTENT_START_TIMER,
                intent.INTENT_CANCEL_TIMER,
                intent.INTENT_INCREASE_TIMER,
                intent.INTENT_DECREASE_TIMER,
                intent.INTENT_PAUSE_TIMER,
                intent.INTENT_UNPAUSE_TIMER,
                intent.INTENT_TIMER_STATUS,
            }

        intent_handlers = [
            intent_handler
            for intent_handler in intent.async_get(self.hass)
            if intent_handler.intent_type not in ignore_intents
        ]

        exposed_domains: set[str] | None = None
        if exposed_entities is not None:
            exposed_domains = {
                info["domain"] for info in exposed_entities["entities"].values()
            }

            intent_handlers = [
                intent_handler
                for intent_handler in intent_handlers
                if intent_handler.platforms is None
                or intent_handler.platforms & exposed_domains
            ]

        tools: list[Tool] = [
            IntentTool(self.cached_slugify(intent_handler.intent_type), intent_handler)
            for intent_handler in intent_handlers
        ]

        if exposed_entities:
            if exposed_entities[CALENDAR_DOMAIN]:
                names = []
                for info in exposed_entities[CALENDAR_DOMAIN].values():
                    names.extend(info["names"].split(", "))
                tools.append(CalendarGetEventsTool(names))

            if exposed_domains is not None and TODO_DOMAIN in exposed_domains:
                names = []
                for info in exposed_entities["entities"].values():
                    if info["domain"] != TODO_DOMAIN:
                        continue
                    names.extend(info["names"].split(", "))
                tools.append(TodoGetItemsTool(names))

            tools.extend(
                ScriptTool(self.hass, script_entity_id)
                for script_entity_id in exposed_entities[SCRIPT_DOMAIN]
            )

        if exposed_domains:
            tools.append(GetLiveContextTool())

        return tools


def _get_exposed_entities(
    hass: HomeAssistant,
    assistant: str,
    include_state: bool = True,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Get exposed entities.

    Splits out calendars and scripts.
    """
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

    entities = {}
    data: dict[str, dict[str, Any]] = {
        SCRIPT_DOMAIN: {},
        CALENDAR_DOMAIN: {},
    }

    for state in sorted(hass.states.async_all(), key=attrgetter("name")):
        if not async_should_expose(hass, assistant, state.entity_id):
            continue

        description: str | None = None
        entity_entry = entity_registry.async_get(state.entity_id)
        names = [state.name]
        area_names = []

        if entity_entry is not None:
            names.extend(entity_entry.aliases)
            if entity_entry.area_id and (
                area := area_registry.async_get_area(entity_entry.area_id)
            ):
                # Entity is in area
                area_names.append(area.name)
                area_names.extend(area.aliases)
            elif entity_entry.device_id and (
                device := device_registry.async_get(entity_entry.device_id)
            ):
                # Check device area
                if device.area_id and (
                    area := area_registry.async_get_area(device.area_id)
                ):
                    area_names.append(area.name)
                    area_names.extend(area.aliases)

        info: dict[str, Any] = {
            "names": ", ".join(names),
            "domain": state.domain,
        }

        if include_state:
            info["state"] = state.state

        if description:
            info["description"] = description

        if area_names:
            info["areas"] = ", ".join(area_names)

        if include_state and (
            attributes := {
                attr_name: (
                    str(attr_value)
                    if isinstance(attr_value, (Enum, Decimal, int))
                    else attr_value
                )
                for attr_name, attr_value in state.attributes.items()
                if attr_name in interesting_attributes
            }
        ):
            info["attributes"] = attributes

        if state.domain in data:
            data[state.domain][state.entity_id] = info
        else:
            entities[state.entity_id] = info

    data["entities"] = entities
    return data


def _selector_serializer(schema: Any) -> Any:  # noqa: C901
    """Convert selectors into OpenAPI schema."""
    if not isinstance(schema, selector.Selector):
        return UNSUPPORTED

    if isinstance(schema, selector.BackupLocationSelector):
        return {"type": "string", "pattern": "^(?:\\/backup|\\w+)$"}

    if isinstance(schema, selector.BooleanSelector):
        return {"type": "boolean"}

    if isinstance(schema, selector.ColorRGBSelector):
        return {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 3,
            "maxItems": 3,
            "format": "RGB",
        }

    if isinstance(schema, selector.ConditionSelector):
        return convert(cv.CONDITIONS_SCHEMA)

    if isinstance(schema, selector.ConstantSelector):
        return convert(vol.Schema(schema.config["value"]))

    result: dict[str, Any]
    if isinstance(schema, selector.ColorTempSelector):
        result = {"type": "number"}
        if "min" in schema.config:
            result["minimum"] = schema.config["min"]
        elif "min_mireds" in schema.config:
            result["minimum"] = schema.config["min_mireds"]
        if "max" in schema.config:
            result["maximum"] = schema.config["max"]
        elif "max_mireds" in schema.config:
            result["maximum"] = schema.config["max_mireds"]
        return result

    if isinstance(schema, selector.CountrySelector):
        if schema.config.get("countries"):
            return {"type": "string", "enum": schema.config["countries"]}
        return {"type": "string", "format": "ISO 3166-1 alpha-2"}

    if isinstance(schema, selector.DateSelector):
        return {"type": "string", "format": "date"}

    if isinstance(schema, selector.DateTimeSelector):
        return {"type": "string", "format": "date-time"}

    if isinstance(schema, selector.DurationSelector):
        return convert(cv.time_period_dict)

    if isinstance(schema, selector.EntitySelector):
        if schema.config.get("multiple"):
            return {"type": "array", "items": {"type": "string", "format": "entity_id"}}

        return {"type": "string", "format": "entity_id"}

    if isinstance(schema, selector.LanguageSelector):
        if schema.config.get("languages"):
            return {"type": "string", "enum": schema.config["languages"]}
        return {"type": "string", "format": "RFC 5646"}

    if isinstance(schema, (selector.LocationSelector, selector.MediaSelector)):
        return convert(schema.DATA_SCHEMA)

    if isinstance(schema, selector.NumberSelector):
        result = {"type": "number"}
        if "min" in schema.config:
            result["minimum"] = schema.config["min"]
        if "max" in schema.config:
            result["maximum"] = schema.config["max"]
        return result

    if isinstance(schema, selector.ObjectSelector):
        return {"type": "object", "additionalProperties": True}

    if isinstance(schema, selector.SelectSelector):
        options = [
            x["value"] if isinstance(x, dict) else x for x in schema.config["options"]
        ]
        if schema.config.get("multiple"):
            return {
                "type": "array",
                "items": {"type": "string", "enum": options},
                "uniqueItems": True,
            }
        return {"type": "string", "enum": options}

    if isinstance(schema, selector.TargetSelector):
        return convert(cv.TARGET_SERVICE_FIELDS)

    if isinstance(schema, selector.TemplateSelector):
        return {"type": "string", "format": "jinja2"}

    if isinstance(schema, selector.TimeSelector):
        return {"type": "string", "format": "time"}

    if isinstance(schema, selector.TriggerSelector):
        return {"type": "array", "items": {"type": "string"}}

    if schema.config.get("multiple"):
        return {"type": "array", "items": {"type": "string"}}

    return {"type": "string"}


def _get_cached_action_parameters(
    hass: HomeAssistant, domain: str, action: str
) -> tuple[str | None, vol.Schema]:
    """Get action description and schema."""
    description = None
    parameters = vol.Schema({})

    parameters_cache = hass.data.get(ACTION_PARAMETERS_CACHE)

    if parameters_cache is None:
        parameters_cache = hass.data[ACTION_PARAMETERS_CACHE] = {}

        @callback
        def clear_cache(event: Event) -> None:
            """Clear action parameter cache on action removal."""
            if (
                event.data[ATTR_DOMAIN] in parameters_cache
                and event.data[ATTR_SERVICE]
                in parameters_cache[event.data[ATTR_DOMAIN]]
            ):
                parameters_cache[event.data[ATTR_DOMAIN]].pop(event.data[ATTR_SERVICE])

        cancel = hass.bus.async_listen(EVENT_SERVICE_REMOVED, clear_cache)

        @callback
        def on_homeassistant_close(event: Event) -> None:
            """Cleanup."""
            cancel()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, on_homeassistant_close)

    if domain in parameters_cache and action in parameters_cache[domain]:
        return parameters_cache[domain][action]

    if action_desc := service.async_get_cached_service_description(
        hass, domain, action
    ):
        description = action_desc.get("description")
        schema: dict[vol.Marker, Any] = {}
        fields = action_desc.get("fields", {})

        for field, config in fields.items():
            field_description = config.get("description")
            if not field_description:
                field_description = config.get("name")
            key: vol.Marker
            if config.get("required"):
                key = vol.Required(field, description=field_description)
            else:
                key = vol.Optional(field, description=field_description)
            if "selector" in config:
                schema[key] = selector.selector(config["selector"])
            else:
                schema[key] = cv.string

        parameters = vol.Schema(schema)

        if domain == SCRIPT_DOMAIN:
            entity_registry = er.async_get(hass)
            if (
                entity_id := entity_registry.async_get_entity_id(domain, domain, action)
            ) and (entity_entry := entity_registry.async_get(entity_id)):
                aliases: list[str] = []
                if entity_entry.name:
                    aliases.append(entity_entry.name)
                if entity_entry.aliases:
                    aliases.extend(entity_entry.aliases)
                if aliases:
                    if description:
                        description = description + ". Aliases: " + str(list(aliases))
                    else:
                        description = "Aliases: " + str(list(aliases))

        parameters_cache.setdefault(domain, {})[action] = (description, parameters)

    return description, parameters


class ActionTool(Tool):
    """LLM Tool representing an action."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        action: str,
    ) -> None:
        """Init the class."""
        self._domain = domain
        self._action = action
        self.name = f"{domain}.{action}"
        self.description, self.parameters = _get_cached_action_parameters(
            hass, domain, action
        )

    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Call the action."""

        for field, validator in self.parameters.schema.items():
            if field not in tool_input.tool_args:
                continue
            if isinstance(validator, selector.AreaSelector):
                area_reg = ar.async_get(hass)
                if validator.config.get("multiple"):
                    areas: list[ar.AreaEntry] = []
                    for area in tool_input.tool_args[field]:
                        areas.extend(intent.find_areas(area, area_reg))
                    tool_input.tool_args[field] = list({area.id for area in areas})
                else:
                    area = tool_input.tool_args[field]
                    area = list(intent.find_areas(area, area_reg))[0].id
                    tool_input.tool_args[field] = area

            elif isinstance(validator, selector.FloorSelector):
                floor_reg = fr.async_get(hass)
                if validator.config.get("multiple"):
                    floors: list[fr.FloorEntry] = []
                    for floor in tool_input.tool_args[field]:
                        floors.extend(intent.find_floors(floor, floor_reg))
                    tool_input.tool_args[field] = list(
                        {floor.floor_id for floor in floors}
                    )
                else:
                    floor = tool_input.tool_args[field]
                    floor = list(intent.find_floors(floor, floor_reg))[0].floor_id
                    tool_input.tool_args[field] = floor

        result = await hass.services.async_call(
            self._domain,
            self._action,
            tool_input.tool_args,
            context=llm_context.context,
            blocking=True,
            return_response=True,
        )

        return {"success": True, "result": result}


class ScriptTool(ActionTool):
    """LLM Tool representing a Script."""

    def __init__(
        self,
        hass: HomeAssistant,
        script_entity_id: str,
    ) -> None:
        """Init the class."""
        script_name = split_entity_id(script_entity_id)[1]

        action = script_name
        entity_registry = er.async_get(hass)
        entity_entry = entity_registry.async_get(script_entity_id)
        if entity_entry and entity_entry.unique_id:
            action = entity_entry.unique_id

        super().__init__(hass, SCRIPT_DOMAIN, action)

        self.name = script_name
        if self.name[0].isdigit():
            self.name = "_" + self.name


class CalendarGetEventsTool(Tool):
    """LLM Tool allowing querying a calendar."""

    name = "calendar_get_events"
    description = (
        "Get events from a calendar. "
        "When asked if something happens, search the whole week. "
        "Results are RFC 5545 which means 'end' is exclusive."
    )

    def __init__(self, calendars: list[str]) -> None:
        """Init the get events tool."""
        self.parameters = vol.Schema(
            {
                vol.Required("calendar"): vol.In(calendars),
                vol.Required("range"): vol.In(["today", "week"]),
            }
        )

    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Query a calendar."""
        data = self.parameters(tool_input.tool_args)
        result = intent.async_match_targets(
            hass,
            intent.MatchTargetsConstraints(
                name=data["calendar"],
                domains=[CALENDAR_DOMAIN],
                assistant=llm_context.assistant,
            ),
        )
        if not result.is_match:
            return {"success": False, "error": "Calendar not found"}

        entity_id = result.states[0].entity_id
        if data["range"] == "today":
            start = dt_util.now()
            end = dt_util.start_of_local_day() + timedelta(days=1)
        elif data["range"] == "week":
            start = dt_util.now()
            end = dt_util.start_of_local_day() + timedelta(days=7)

        service_data = {
            "entity_id": entity_id,
            "start_date_time": start.isoformat(),
            "end_date_time": end.isoformat(),
        }

        service_result = await hass.services.async_call(
            CALENDAR_DOMAIN,
            SERVICE_GET_EVENTS,
            service_data,
            context=llm_context.context,
            blocking=True,
            return_response=True,
        )

        events = [
            event if "T" in event["start"] else {**event, "all_day": True}
            for event in cast(dict, service_result)[entity_id]["events"]
        ]

        return {"success": True, "result": events}


class TodoGetItemsTool(Tool):
    """LLM Tool allowing querying a to-do list."""

    name = "todo_get_items"
    description = (
        "Get items from a to-do list. Returns items with optional status filtering."
    )

    def __init__(self, todo_lists: list[str]) -> None:
        """Init the get items tool."""
        self.parameters = vol.Schema(
            {
                vol.Required("todo_list"): vol.In(todo_lists),
                vol.Optional(
                    "status",
                    description="Filter returned items by status, by default returns incomplete items",
                    default=["needs_action"],
                ): vol.Any(cv.ensure_list, [vol.In(["needs_action", "completed"])]),
            }
        )

    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Query a to-do list."""
        data = self.parameters(tool_input.tool_args)
        result = intent.async_match_targets(
            hass,
            intent.MatchTargetsConstraints(
                name=data["todo_list"],
                domains=[TODO_DOMAIN],
                assistant=llm_context.assistant,
            ),
        )
        if not result.is_match:
            return {"success": False, "error": "To-do list not found"}
        entity_id = result.states[0].entity_id
        service_data = {"entity_id": entity_id}
        if "status" in data:
            service_data["status"] = data["status"]
        service_result = await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.GET_ITEMS,
            service_data,
            context=llm_context.context,
            blocking=True,
            return_response=True,
        )
        if not service_result:
            return {"success": False, "error": "To-do list not found"}
        items = cast(dict, service_result)[entity_id]["items"]
        return {"success": True, "result": items}


class GetLiveContextTool(Tool):
    """Tool for getting the current state of exposed entities.

    This returns state for all entities that have been exposed to
    the assistant. This is different than the GetState intent, which
    returns state for entities based on intent parameters.
    """

    name = "GetLiveContext"
    description = (
        "Use this tool when the user asks a question about the CURRENT state, "
        "value, or mode of a specific device, sensor, entity, or area in the "
        "smart home, and the answer can be improved with real-time data not "
        "available in the static device overview list. "
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: ToolInput,
        llm_context: LLMContext,
    ) -> JsonObjectType:
        """Get the current state of exposed entities."""
        if llm_context.assistant is None:
            # Note this doesn't happen in practice since this tool won't be
            # exposed if no assistant is configured.
            return {"success": False, "error": "No assistant configured"}

        exposed_entities = _get_exposed_entities(hass, llm_context.assistant)
        if not exposed_entities["entities"]:
            return {"success": False, "error": NO_ENTITIES_PROMPT}
        prompt = [
            "Live Context: An overview of the areas and the devices in this smart home:",
            yaml_util.dump(list(exposed_entities["entities"].values())),
        ]
        return {
            "success": True,
            "result": "\n".join(prompt),
        }
