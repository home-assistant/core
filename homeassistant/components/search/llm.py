"""LLM tools for the search integration."""

from collections.abc import Callable, Iterable, Iterator
from functools import partial
import heapq
from itertools import chain
from typing import override

import probatio

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.llm import LLMTools
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)
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
    "and set offset to its next_offset."
)

type _Item = tuple[str, str | None, Iterable[str], Iterable[str], Iterable[str]]
"""ID, display name, names, aliases and other fields of an item."""


def _rank(
    query: str, names: Iterable[str], aliases: Iterable[str], other: Iterable[str]
) -> int | None:
    """Return the rank of an item for the query, or None if it does not match.

    Rank 0 is an exact name match, rank 1 an exact alias match, rank 2 a
    partial name match and rank 3 a partial alias match or a match on another
    field. Each field is only read when it can still improve the rank.
    """
    rank = None
    for name in names:
        folded = name.casefold()
        if folded == query:
            return 0
        if query in folded:
            rank = 2
    for alias in aliases:
        folded = alias.casefold()
        if folded == query:
            return 1
        if rank is None and query in folded:
            rank = 3
    if rank is None and any(query in value.casefold() for value in other):
        rank = 3
    return rank


def _set(*values: str | None) -> Iterator[str]:
    """Yield the values that are set."""
    return (value for value in values if value)


def _entity_aliases(
    hass: HomeAssistant, ent_reg: er.EntityRegistry, entity_id: str
) -> Iterator[str]:
    """Yield the aliases of an entity."""
    if entry := ent_reg.async_get(entity_id):
        yield from er.async_get_entity_aliases(hass, entry)


def _entity_item(
    hass: HomeAssistant, ent_reg: er.EntityRegistry, state: State
) -> _Item:
    """Return the item for an entity."""
    return (
        state.entity_id,
        state.name,
        (state.name,),
        _entity_aliases(hass, ent_reg, state.entity_id),
        (state.entity_id,),
    )


def _entities(hass: HomeAssistant) -> Iterator[_Item]:
    """Yield the entities that are not automations, scripts or scenes."""
    ent_reg = er.async_get(hass)
    for state in hass.states.async_all():
        if state.domain not in _OWN_TYPE_DOMAINS:
            yield _entity_item(hass, ent_reg, state)


def _devices(hass: HomeAssistant) -> Iterator[_Item]:
    """Yield the enabled devices, including child devices."""
    dev_reg = dr.async_get(hass)
    for device in chain(dev_reg.devices, dev_reg.child_devices):
        if device.disabled:
            continue
        yield (
            device.id,
            device.name_by_user or device.name,
            _set(device.name_by_user, device.name),
            (),
            # Child devices have no model or manufacturer.
            _set(device.model, device.manufacturer)
            if isinstance(device, dr.DeviceEntry)
            else (),
        )


def _areas(hass: HomeAssistant) -> Iterator[_Item]:
    """Yield the areas."""
    for area in ar.async_get(hass).async_list_areas():
        yield area.id, area.name, (area.name,), area.aliases, ()


def _labels(hass: HomeAssistant) -> Iterator[_Item]:
    """Yield the labels."""
    for label in lr.async_get(hass).async_list_labels():
        yield label.label_id, label.name, (label.name,), (), ()


def _domain_entities(domain: str, hass: HomeAssistant) -> Iterator[_Item]:
    """Yield the entities of a domain."""
    ent_reg = er.async_get(hass)
    for state in hass.states.async_all(domain):
        yield _entity_item(hass, ent_reg, state)


_ITEMS: dict[str, Callable[[HomeAssistant], Iterator[_Item]]] = {
    "entity": _entities,
    "device": _devices,
    "area": _areas,
    "label": _labels,
    "automation": partial(_domain_entities, AUTOMATION_DOMAIN),
    "script": partial(_domain_entities, SCRIPT_DOMAIN),
    "scene": partial(_domain_entities, SCENE_DOMAIN),
}


def _search(
    items: Iterator[_Item], query: str, offset: int
) -> tuple[int, JsonObjectType]:
    """Return the number of matches and the matches after the offset.

    Only the best offset + limit matches are kept in memory.
    """
    total = 0

    def matches() -> Iterator[tuple[int, str, str, str | None]]:
        nonlocal total
        for item_id, name, names, aliases, other in items:
            if (rank := _rank(query, names, aliases, other)) is not None:
                total += 1
                yield rank, (name or "").casefold(), item_id, name

    best = heapq.nsmallest(offset + _LIMIT, matches())
    return total, {item_id: name for _, _, item_id, name in best[offset:]}


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
            ): probatio.All(str, probatio.NonEmpty()),
            probatio.Optional(
                "type", description="Return only results of this type."
            ): probatio.In(list(_ITEMS)),
            probatio.Optional(
                "offset",
                description=(
                    "Number of results to skip. Requires type. Use the "
                    "next_offset of the previous result."
                ),
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
            total, results = _search(_ITEMS[type_](hass), query, offset)
            if not total:
                continue
            group: JsonObjectType = {"total": total, "results": results}
            if (next_offset := offset + _LIMIT) < total:
                group["next_offset"] = next_offset
                has_more = True
            result[type_] = group

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
