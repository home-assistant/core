"""LLM tools for the scene integration."""

from typing import Any, override

import probatio

from homeassistant.components.homeassistant.scene import HomeAssistantScene
from homeassistant.components.llm import LLMTools
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    category_registry as cr,
    config_validation as cv,
    entity_registry as er,
    label_registry as lr,
)
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.llm import (
    LLM_API_HOME_ASSISTANT,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.util.json import JsonObjectType, JsonValueType, json_loads_object

from .const import DATA_COMPONENT, DOMAIN

_LIMIT = 50


class ListScenesTool(Tool):
    """LLM Tool to list the scenes."""

    name = "scene__list_scenes"
    title = "List scenes"
    description = (
        "List the scenes, sorted by name, with when they were last activated, "
        "their area, category and labels. "
        f"Returns at most {_LIMIT} scenes per call."
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
                    "Number of scenes to skip. Use the next_offset of the previous "
                    "result."
                ),
                default=0,
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=0)),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return a page of the scenes."""
        offset: int = self.parameters(tool_input.tool_args)["offset"]
        states = sorted(
            hass.states.async_all(DOMAIN),
            key=lambda state: (state.name.casefold(), state.entity_id),
        )

        ent_reg = er.async_get(hass)
        area_reg = ar.async_get(hass)
        cat_reg = cr.async_get(hass)
        lab_reg = lr.async_get(hass)

        scenes: list[JsonValueType] = []
        for state in states[offset : offset + _LIMIT]:
            # The state of a scene is the time it was last activated
            scene: JsonObjectType = {
                "entity_id": state.entity_id,
                "name": state.name,
                "last_activated": None
                if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
                else state.state,
            }
            if state.state == STATE_UNAVAILABLE:
                scene["available"] = False
            if entry := ent_reg.async_get(state.entity_id):
                if (area_id := er.async_get_effective_area_id(hass, entry)) and (
                    area := area_reg.async_get_area(area_id)
                ):
                    scene["area"] = area.name
                if (category_id := entry.categories.get(DOMAIN)) and (
                    category := cat_reg.async_get_category(
                        scope=DOMAIN, category_id=category_id
                    )
                ):
                    scene["category"] = category.name
                if labels := sorted(
                    label.name
                    for label_id in entry.labels
                    if (label := lab_reg.async_get_label(label_id))
                ):
                    scene["labels"] = list[JsonValueType](labels)
            scenes.append(scene)

        result: JsonObjectType = {"scenes": scenes, "total": len(states)}
        if (next_offset := offset + _LIMIT) < len(states):
            result["next_offset"] = next_offset
        return ToolResult(data=result)


class GetConfigTool(Tool):
    """LLM Tool to get the configuration of a scene."""

    name = "scene__get_config"
    title = "Get scene configuration"
    description = (
        "Get the configuration of a scene: the state and attributes it sets on "
        "each entity. Only scenes made in Home Assistant have a configuration, "
        "not scenes that come from an integration. Use scene__list_scenes or "
        "search__search to find the entity_id."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "entity_id", description="The entity_id of the scene."
            ): cv.entity_domain(DOMAIN),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return the configuration of the scene."""
        entity_id: str = self.parameters(tool_input.tool_args)["entity_id"]
        if (component := hass.data.get(DATA_COMPONENT)) is None or (
            entity := component.get_entity(entity_id)
        ) is None:
            raise HomeAssistantError(f"Scene '{entity_id}' not found.")
        if not isinstance(entity, HomeAssistantScene):
            raise HomeAssistantError(
                f"Scene '{entity_id}' comes from an integration and has no "
                "configuration in Home Assistant."
            )

        scene_config = entity.scene_config
        config: dict[str, Any] = {"name": scene_config.name}
        if scene_config.id is not None:
            config["id"] = scene_config.id
        if scene_config.icon is not None:
            config["icon"] = scene_config.icon
        config["entities"] = {
            # An attribute named state must not hide the state the scene sets
            scene_entity_id: {**state.attributes, "state": state.state}
            for scene_entity_id, state in scene_config.states.items()
        }
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
    """Return the scene LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    return LLMTools(tools=[ListScenesTool(), GetConfigTool()])
