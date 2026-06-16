"""LLM tools for the script integration."""

from typing import Any

import voluptuous as vol

from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_SERVICE,
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_SERVICE_REMOVED,
)
from homeassistant.core import Event, HomeAssistant, callback, split_entity_id
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    entity_registry as er,
    floor_registry as fr,
    intent,
    llm,
    selector,
    service,
)
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN

ACTION_PARAMETERS_CACHE: HassKey[
    dict[str, dict[str, tuple[str | None, vol.Schema]]]
] = HassKey("llm_action_parameters_cache")


async def async_setup_tools(hass: HomeAssistant) -> None:
    """Set up the script LLM tools."""
    llm.async_register_tool_provider(
        hass, _script_tools, apis={llm.LLM_API_ASSIST: None}
    )


@callback
def _script_tools(hass: HomeAssistant, llm_context: llm.LLMContext) -> llm.LLMTools:
    """Return the script tools for the exposed scripts."""
    if llm_context.assistant is None:
        return llm.LLMTools(tools=[])

    exposed = llm.async_get_exposed_entities(
        hass, llm_context.assistant, include_state=False
    )
    return llm.LLMTools(
        tools=[
            ScriptTool(hass, script_entity_id) for script_entity_id in exposed[DOMAIN]
        ]
    )


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

        if domain == DOMAIN:
            entity_registry = er.async_get(hass)
            if (
                entity_id := entity_registry.async_get_entity_id(domain, domain, action)
            ) is not None and (
                entity_entry := entity_registry.async_get(entity_id)
            ) is not None:
                aliases = er.async_get_entity_aliases(hass, entity_entry)
                if aliases:
                    if description:
                        description = description + ". Aliases: " + str(sorted(aliases))
                    else:
                        description = "Aliases: " + str(sorted(aliases))

        parameters_cache.setdefault(domain, {})[action] = (description, parameters)

    return description, parameters


class ActionTool(llm.Tool):
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

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
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

        super().__init__(hass, DOMAIN, action)

        self.name = script_name
        if self.name[0].isdigit():
            self.name = "_" + self.name
