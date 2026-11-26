"""LLM tools for the script integration."""

from datetime import datetime
from operator import attrgetter
from typing import TYPE_CHECKING, override

import probatio

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    category_registry as cr,
    config_validation as cv,
    entity_registry as er,
    label_registry as lr,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.llm import (
    LLM_API_ASSIST,
    LLM_API_HOME_ASSISTANT,
    ActionTool,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.util.json import JsonObjectType, JsonValueType, json_loads_object

from .const import ATTR_LAST_TRIGGERED, DOMAIN

if TYPE_CHECKING:
    from .entity import BaseScriptEntity

_LIMIT = 50


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

        self.name = f"{DOMAIN}__{script_name}"
        # The script is named by the user, so its name is already in their
        # language.
        if state := hass.states.get(script_entity_id):
            self.title = state.name

        if entity_entry and (
            aliases := er.async_get_entity_aliases(hass, entity_entry)
        ):
            alias_text = "Aliases: " + str(sorted(aliases))
            self.description = (
                f"{self.description}. {alias_text}" if self.description else alias_text
            )


class ListScriptsTool(Tool):
    """LLM Tool to list the scripts."""

    name = "script__list_scripts"
    title = "List scripts"
    description = (
        "List the scripts, sorted by name, with their state, when they were last "
        "triggered, their description, area, category and labels. A script that is on is running now, and "
        "one that is unavailable has an error in its configuration. Returns at "
        f"most {_LIMIT} scripts per call."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "offset",
                description=(
                    "Number of scripts to skip. Use the next_offset of the "
                    "previous result."
                ),
                default=0,
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=0)),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return a page of the scripts."""
        offset: int = self.parameters(tool_input.tool_args)["offset"]
        states = sorted(
            hass.states.async_all(DOMAIN),
            key=lambda state: (state.name.casefold(), state.entity_id),
        )
        component: EntityComponent[BaseScriptEntity] | None = hass.data.get(DOMAIN)
        ent_reg = er.async_get(hass)
        area_reg = ar.async_get(hass)
        cat_reg = cr.async_get(hass)
        lab_reg = lr.async_get(hass)

        scripts: list[JsonValueType] = []
        for state in states[offset : offset + _LIMIT]:
            last_triggered = state.attributes.get(ATTR_LAST_TRIGGERED)
            script: JsonObjectType = {
                "entity_id": state.entity_id,
                "name": state.name,
                "state": state.state,
                "last_triggered": last_triggered.isoformat()
                if isinstance(last_triggered, datetime)
                else None,
            }
            if (
                component is not None
                and (entity := component.get_entity(state.entity_id)) is not None
                and entity.raw_config
                and (description := entity.raw_config.get("description"))
                not in (None, "")
            ):
                # The raw configuration is not validated, so it may hold a number
                script["description"] = str(description)
            if entry := ent_reg.async_get(state.entity_id):
                if (area_id := er.async_get_effective_area_id(hass, entry)) and (
                    area := area_reg.async_get_area(area_id)
                ):
                    script["area"] = area.name
                if (category_id := entry.categories.get(DOMAIN)) and (
                    category := cat_reg.async_get_category(
                        scope=DOMAIN, category_id=category_id
                    )
                ):
                    script["category"] = category.name
                if labels := sorted(
                    label.name
                    for label_id in entry.labels
                    if (label := lab_reg.async_get_label(label_id))
                ):
                    script["labels"] = list[JsonValueType](labels)
            scripts.append(script)

        result: JsonObjectType = {"scripts": scripts, "total": len(states)}
        if (next_offset := offset + _LIMIT) < len(states):
            result["next_offset"] = next_offset
        return ToolResult(data=result)


class GetConfigTool(Tool):
    """LLM Tool to get the configuration of a script."""

    name = "script__get_config"
    title = "Get script configuration"
    description = (
        "Get the configuration of a script: its fields and sequence of actions, or "
        "the blueprint it uses with its inputs. Use script__list_scripts or "
        "search__search to find the entity_id."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "entity_id", description="The entity_id of the script."
            ): cv.entity_domain(DOMAIN),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return the configuration of the script."""
        entity_id: str = self.parameters(tool_input.tool_args)["entity_id"]
        component: EntityComponent[BaseScriptEntity] | None = hass.data.get(DOMAIN)
        if (
            component is None
            or (entity := component.get_entity(entity_id)) is None
            or (config := entity.raw_blueprint_inputs or entity.raw_config) is None
        ):
            raise HomeAssistantError(f"Script '{entity_id}' not found.")
        return ToolResult(
            data={
                "entity_id": entity_id,
                "config": json_loads_object(json_dumps(config)),
            }
        )


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the script list tool, or a tool for each exposed script for Assist."""
    if api_id == LLM_API_HOME_ASSISTANT:
        return LLMTools(tools=[ListScriptsTool(), GetConfigTool()])
    if api_id != LLM_API_ASSIST:
        return None

    tools: list[Tool] = [
        ScriptTool(hass, state.entity_id)
        for state in sorted(hass.states.async_all(DOMAIN), key=attrgetter("name"))
        if async_should_expose(hass, llm_context.assistant, state.entity_id)
    ]
    if not tools:
        return None
    return LLMTools(tools=tools)
