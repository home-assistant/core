"""LLM tools for the search integration."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, override

import probatio

from homeassistant.components.automation import (
    DATA_COMPONENT as AUTOMATION_DATA_COMPONENT,
    DOMAIN as AUTOMATION_DOMAIN,
)
from homeassistant.components.llm import LLMTools
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.const import CONF_DESCRIPTION
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.llm import (
    LLM_API_HOME_ASSISTANT,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.util.json import JsonObjectType

from . import DOMAIN

_LIMIT = 5
_OWN_TYPE_DOMAINS = {AUTOMATION_DOMAIN, SCRIPT_DOMAIN, SCENE_DOMAIN}
_INSTRUCTIONS = (
    f"Each type shows at most {_LIMIT} results. To get the next results of one "
    "type, call this tool again with the same query, set type to that type, "
    f"and set offset to {_LIMIT}."
)


@dataclass(slots=True, frozen=True)
class _Item:
    """An item that can be found by a search."""

    id: str
    name: str | None
    names: Iterable[str | None]
    other: Iterable[str | None]


def _rank(item: _Item, query: str) -> int | None:
    """Return the rank of an item for the query, or None if it does not match.

    Rank 0 is an exact name match, rank 1 a partial name match and rank 2 a
    match on another field.
    """
    names = [name.casefold() for name in item.names if name]
    if query in names:
        return 0
    if any(query in name for name in names):
        return 1
    if any(query in value.casefold() for value in item.other if value):
        return 2
    return None


def _entities(hass: HomeAssistant) -> list[_Item]:
    """Return the entities that are not automations, scripts or scenes."""
    ent_reg = er.async_get(hass)
    items = []
    for state in hass.states.async_all():
        if split_entity_id(state.entity_id)[0] in _OWN_TYPE_DOMAINS:
            continue
        aliases: list[str] = []
        if entry := ent_reg.async_get(state.entity_id):
            aliases = er.async_get_entity_aliases(hass, entry)
        items.append(
            _Item(
                state.entity_id, state.name, [state.name], [state.entity_id, *aliases]
            )
        )
    return items


def _devices(hass: HomeAssistant) -> list[_Item]:
    """Return the enabled devices."""
    return [
        _Item(
            device.id,
            device.name_by_user or device.name,
            [device.name_by_user, device.name],
            [device.model, device.manufacturer],
        )
        for device in dr.async_get(hass).devices
        if not device.disabled
    ]


def _areas(hass: HomeAssistant) -> list[_Item]:
    """Return the areas."""
    return [
        _Item(area.id, area.name, [area.name], area.aliases)
        for area in ar.async_get(hass).async_list_areas()
    ]


def _labels(hass: HomeAssistant) -> list[_Item]:
    """Return the labels."""
    return [
        _Item(label.label_id, label.name, [label.name], [])
        for label in lr.async_get(hass).async_list_labels()
    ]


def _with_description(
    hass: HomeAssistant, domain: str, component: EntityComponent[Any] | None
) -> list[_Item]:
    """Return the entities of an automation or script domain.

    The description is matched as another field.
    """
    items = []
    for state in hass.states.async_all(domain):
        description = None
        if (
            component is not None
            and (entity := component.get_entity(state.entity_id)) is not None
            and entity.raw_config is not None
            and (value := entity.raw_config.get(CONF_DESCRIPTION)) is not None
        ):
            # YAML allows a description that is not a string, such as a number.
            description = str(value)
        items.append(
            _Item(
                state.entity_id,
                state.name,
                [state.name],
                [state.entity_id, description],
            )
        )
    return items


def _automations(hass: HomeAssistant) -> list[_Item]:
    """Return the automations."""
    return _with_description(
        hass, AUTOMATION_DOMAIN, hass.data.get(AUTOMATION_DATA_COMPONENT)
    )


def _scripts(hass: HomeAssistant) -> list[_Item]:
    """Return the scripts."""
    return _with_description(hass, SCRIPT_DOMAIN, hass.data.get(SCRIPT_DOMAIN))


def _scenes(hass: HomeAssistant) -> list[_Item]:
    """Return the scenes."""
    return [
        _Item(state.entity_id, state.name, [state.name], [state.entity_id])
        for state in hass.states.async_all(SCENE_DOMAIN)
    ]


_ITEMS: dict[str, Callable[[HomeAssistant], list[_Item]]] = {
    "entity": _entities,
    "device": _devices,
    "area": _areas,
    "label": _labels,
    "automation": _automations,
    "script": _scripts,
    "scene": _scenes,
}


class SearchTool(Tool):
    """LLM Tool to search Home Assistant by name."""

    name = "search__search"
    title = "Search Home Assistant"
    description = (
        "Search entities, devices, areas, labels, automations, scripts and scenes "
        "by name. Returns the ID and name of each match, grouped by type."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "query", description="Text to find, case-insensitive."
            ): probatio.All(str, probatio.Length(min=1)),
            probatio.Optional(
                "type", description="Return only results of this type."
            ): probatio.In(list(_ITEMS)),
            probatio.Optional(
                "offset",
                description="Number of results to skip. Requires type.",
                default=0,
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=0)),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Search Home Assistant."""
        args = self.parameters(tool_input.tool_args)
        query: str = args["query"].casefold()
        item_type: str | None = args.get("type")
        offset: int = args["offset"]

        if offset and item_type is None:
            return ToolResult(
                data={"error": "Set type to get more results of that type."},
                error=True,
            )

        result: JsonObjectType = {}
        has_more = False
        for type_ in [item_type] if item_type else _ITEMS:
            matches = sorted(
                (
                    (rank, (item.name or "").casefold(), item)
                    for item in _ITEMS[type_](hass)
                    if (rank := _rank(item, query)) is not None
                ),
                key=lambda match: match[:2],
            )
            if not matches:
                continue
            has_more = has_more or len(matches) > _LIMIT
            result[type_] = {
                "total": len(matches),
                "results": {
                    item.id: item.name
                    for _, _, item in matches[offset : offset + _LIMIT]
                },
            }

        if item_type is None and has_more:
            result["instructions"] = _INSTRUCTIONS
        return ToolResult(data=result)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the search LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    return LLMTools(tools=[SearchTool()])
