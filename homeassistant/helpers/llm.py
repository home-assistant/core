"""Module to coordinate llm tools."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field as dc_field
from typing import Any, override

import slugify as unicode_slug
import voluptuous as vol
from voluptuous_openapi import UNSUPPORTED, convert

from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_SERVICE,
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_SERVICE_REMOVED,
)
from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import JsonObjectType
from homeassistant.util.ulid import ulid_now

from . import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    floor_registry as fr,
    intent,
    selector,
    service,
)
from .deprecation import deprecated_function
from .singleton import singleton

ACTION_PARAMETERS_CACHE: HassKey[
    dict[str, dict[str, tuple[str | None, vol.Schema]]]
] = HassKey("llm_action_parameters_cache")

APIS_CACHE: HassKey[dict[str, API]] = HassKey("llm_apis")


LLM_API_ASSIST = "assist"

DATE_TIME_PROMPT = (
    'Current time is {{ now().strftime("%H:%M:%S") }}. '
    'Today\'s date is {{ now().strftime("%Y-%m-%d") }}.\n'
)

DEFAULT_INSTRUCTIONS_PROMPT = """You are a voice assistant for Home Assistant.
Answer questions about the world truthfully.
Answer in plain text. Keep it simple and to the point.
"""


@deprecated_function("an empty string", breaks_in_ha_version="2027.2")
@callback
def async_render_no_api_prompt(hass: HomeAssistant) -> str:
    """Return the prompt to be used when no API is configured.

    No longer used since Home Assistant 2024.7.
    """
    return ""


@singleton(APIS_CACHE)
@callback
def _async_get_apis(hass: HomeAssistant) -> dict[str, API]:
    """Return the registry of LLM APIs.

    APIs are registered by their owning integration; the Assist API is
    registered by the ``llm`` integration during setup.
    """
    return {}


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
    """Integration that is handling the LLM request."""

    context: Context | None
    """Context of the LLM request."""

    language: str | None
    """Language of the LLM request."""

    assistant: str
    """Assistant domain that is handling the LLM request."""

    device_id: str | None
    """Device that is making the request."""


@dataclass(slots=True)
class ToolInput:
    """Tool input to be processed."""

    tool_name: str
    tool_args: dict[str, Any]
    # Using lambda for default to allow patching in tests
    id: str = dc_field(default_factory=lambda: ulid_now())  # pylint: disable=unnecessary-lambda
    external: bool = False


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

    @override
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
        from homeassistant.components.conversation import (  # noqa: PLC0415
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

    @override
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
            text_input=None,
            context=llm_context.context,
            language=llm_context.language,
            assistant=llm_context.assistant,
            device_id=llm_context.device_id,
        )
        return IntentResponseDict(intent_response)


class IntentResponseDict(dict):
    """Dictionary to represent an intent response resulting from a tool call."""

    def __init__(self, intent_response: Any) -> None:
        """Initialize the dictionary."""
        if not isinstance(intent_response, intent.IntentResponse):
            super().__init__(intent_response)
            return

        result = intent_response.as_dict()
        del result["language"]
        del result["card"]
        super().__init__(result)
        self.original = intent_response


class NamespacedTool(Tool):
    """A tool that wraps another tool, prepending a namespace.

    This is used to support tools from multiple API. This tool dispatches
    the original tool with the original non-namespaced name.
    """

    def __init__(self, namespace: str, tool: Tool) -> None:
        """Init the class."""
        self.namespace = namespace
        self.name = f"{namespace}__{tool.name}"
        self.description = tool.description
        self.parameters = tool.parameters
        self.tool = tool

    @override
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

    @override
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


def selector_serializer(schema: Any) -> Any:  # noqa: C901
    """Convert selectors into OpenAPI schema."""
    if schema is cv.string or schema is intent.non_empty_string:
        return {"type": "string"}
    if schema is cv.boolean:
        return {"type": "boolean"}

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

    if isinstance(schema, selector.LocationSelector):
        return convert(schema.DATA_SCHEMA)

    if isinstance(schema, selector.MediaSelector):
        item_schema = convert(schema.DATA_SCHEMA)
        # Media selector allows multiple when configured
        if schema.config.get("multiple"):
            return {
                "type": "array",
                "items": item_schema,
            }
        return item_schema

    if isinstance(schema, selector.NumberSelector):
        result = {"type": "number"}
        if "min" in schema.config:
            result["minimum"] = schema.config["min"]
        if "max" in schema.config:
            result["maximum"] = schema.config["max"]
        return result

    if isinstance(schema, selector.ObjectSelector):
        result = {"type": "object"}
        if fields := schema.config.get("fields"):
            properties = {}
            required = []
            for field, field_schema in fields.items():
                properties[field] = convert(
                    selector.selector(field_schema["selector"]),
                    custom_serializer=selector_serializer,
                )
                if field_schema.get("required"):
                    required.append(field)
            result["properties"] = properties

            if required:
                result["required"] = required
        else:
            result["additionalProperties"] = True
        if schema.config.get("multiple"):
            result = {
                "type": "array",
                "items": result,
            }
        return result

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
        return convert(cv.TARGET_FIELDS)

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
        self.name = f"{domain}__{action}"
        # Note: _get_cached_action_parameters only works for services which
        # add their description directly to the service description cache.
        # This is not the case for most services, but it is for scripts.
        # If we want to use `ActionTool` for services other than scripts, we
        # need to add a coroutine function to fetch the non-cached description
        # and schema.
        self.description, self.parameters = _get_cached_action_parameters(
            hass, domain, action
        )

    @override
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
