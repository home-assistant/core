"""Expose KNX tools (telegram store, ETS project, DPTs, bus) to LLMs.

The tool logic lives in the shared ``*.mcp`` subpackages of ``knx-telegram-store``,
``xknxproject`` and ``xknx``; this module only adapts those functions into
Home Assistant :class:`llm.Tool` objects and wires them to the running KNX module.
Each tool's parameter schema (and its per-parameter descriptions) is derived from
the library input dataclasses' ``dataclasses.field`` metadata, so the descriptions
stay single-sourced in the libraries.
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass, field as dc_field, fields, is_dataclass
from datetime import date, time
from enum import Enum
from typing import TYPE_CHECKING, Any, NamedTuple, cast, override

from knx_telegram_store import KnxTelegramStoreException, TelegramStore, mcp as kts_mcp
import probatio
from probatio.dataclass_schema import constructed_mapping
from xknx import mcp as xknx_mcp
from xknx.exceptions import XKNXException
from xknxproject import mcp as xknxproject_mcp
from xknxproject.models import KNXProject as KNXProjectModel

from homeassistant.const import CONF_ENTITY_ID, CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN, SUPPORTED_PLATFORMS_UI
from .device import async_create_ui_device, async_remove_ui_entities_of_device
from .storage.config_store import ConfigStoreException
from .storage.const import CONF_DATA
from .storage.entity_store_validation import (
    EntityStoreValidationException,
    validate_entity_data,
)
from .storage.entity_suggestions import async_get_entity_suggestions
from .storage.entity_suggestions.const import SuggestionFilter
from .storage.serialize import get_serialized_schema

if TYPE_CHECKING:
    from .knx_module import KNXModule

LLM_API_ID = DOMAIN
LLM_API_NAME = "KNX"
API_PROMPT = (
    "Tools to inspect a KNX installation: stored bus telegrams, the loaded ETS "
    "project (group addresses, devices and their channels, communication "
    "objects, functions, topology), KNX data point types, and live bus "
    'reads and writes. Address formats: group addresses like "1/2/3", individual '
    'device addresses like "1.1.5", DPTs like "9.001".\n'
    "Tools to create KNX entities in Home Assistant: start from "
    "list_entity_suggestions and pass a suggestion id to create_entity, or look "
    "up the options of a platform with get_entity_schema and the group addresses "
    "in the ETS project. Use validate_entity to check a configuration without "
    "creating anything. Entities can be grouped in a device made by create_device. "
    "Entities created this way are listed by list_entities; update_entity "
    "replaces the configuration get_entity_config returns."
)


type _ToolFunc = Callable[[KNXModule, Any], Awaitable[Any]]


class _ToolSpec(NamedTuple):
    """One KNX tool: what it is called, what it does and how it behaves."""

    name: str
    title: str
    description: str
    parameters: probatio.Schema
    func: _ToolFunc
    annotations: llm.ToolAnnotations


# Forwarded by the MCP server as the tool hints, so they have to be stated: the
# defaults describe the least safe case and would advertise every read as a
# destructive write. The two bus reads transmit a telegram but change no state;
# writing does, and some DPTs (step, trigger, scene) are not idempotent.
_READ_ONLY = llm.ToolAnnotations(
    read_only=True, destructive=False, idempotent=True, open_world=False
)
_BUS_PROBE = llm.ToolAnnotations(
    read_only=False, destructive=False, idempotent=True, open_world=True
)
_BUS_WRITE = llm.ToolAnnotations(
    read_only=False, destructive=True, idempotent=False, open_world=True
)
# Adds to the Home Assistant configuration; nothing existing is changed and
# nothing is sent to the bus.
_CONFIG_ADD = llm.ToolAnnotations(
    read_only=False, destructive=False, idempotent=False, open_world=False
)
# Replaces or removes Home Assistant configuration. Replacing with the same
# configuration again changes nothing; removing again fails.
_CONFIG_REPLACE = llm.ToolAnnotations(
    read_only=False, destructive=True, idempotent=True, open_world=False
)
_CONFIG_REMOVE = llm.ToolAnnotations(
    read_only=False, destructive=True, idempotent=False, open_world=False
)

# The library ``_paginate`` helpers treat a negative limit as "no limit", which
# would return a whole ETS project or telegram history in a single tool result,
# and a negative offset slices from the end. The dataclasses don't express
# bounds, so they are applied here, by the field names the libraries share.
_MAX_RESULT_ITEMS = 1000
_FIELD_BOUNDS: dict[str, Any] = {
    "limit": probatio.Range(min=1, max=_MAX_RESULT_ITEMS),
    "offset": probatio.Range(min=0),
    "delta_before_ms": probatio.Range(min=0),
    "delta_after_ms": probatio.Range(min=0),
}
_PAGINATION_MARKERS: dict[Any, Any] = {
    probatio.Optional(
        "limit", description="Maximum number of results to return.", default=100
    ): probatio.All(int, _FIELD_BOUNDS["limit"]),
    probatio.Optional(
        "offset", description="Number of results to skip.", default=0
    ): probatio.All(int, _FIELD_BOUNDS["offset"]),
}


def _field_description(input_type: type, name: str) -> str | None:
    """The description a library input dataclass documents a field with."""
    return next(
        field.metadata.get("description")
        for field in fields(input_type)
        if field.name == name
    )


def _apply_field_descriptions(schema: probatio.Schema, input_type: type) -> None:
    """Carry the dataclass field descriptions over to the schema's key markers.

    The libraries keep their parameter descriptions in ``dataclasses.field``
    metadata rather than in probatio's ``Annotated``/``Key``, so
    ``DataclassSchema`` cannot pick them up itself.
    """
    mapping = constructed_mapping(schema)
    assert mapping is not None  # a DataclassSchema always constructs
    for marker in mapping.schema:
        if (description := _field_description(input_type, str(marker))) is not None:
            marker.description = description


def _schema_from_dataclass(input_type: type) -> probatio.Schema:
    """Build a tool parameter schema from a library ``*.mcp`` input dataclass.

    ``DataclassSchema`` maps each annotation to a validator and constructs the
    input instance, so a validated call arrives at the library already typed.
    """
    bounds = {
        field.name: _FIELD_BOUNDS[field.name]
        for field in fields(input_type)
        if field.name in _FIELD_BOUNDS
    }
    schema: probatio.Schema = probatio.DataclassSchema(input_type, bounds)
    _apply_field_descriptions(schema, input_type)
    return schema


def _paginate(items: list[Any], args: Mapping[str, Any], key: str) -> dict[str, Any]:
    """Window a library result that the library itself returns in full."""
    offset: int = args["offset"]
    limit: int = args["limit"]
    window = items[offset : offset + limit]
    limit_reached = offset + limit < len(items)
    return {
        key: window,
        "total_count": len(items),
        "offset": offset,
        "next_offset": offset + len(window) if limit_reached else None,
        "limit_reached": limit_reached,
    }


def _json_safe(value: Any) -> Any:
    """Recursively convert a library result into JSON-encodable primitives.

    ``asdict`` recurses into nested dataclasses but leaves leaf objects as they
    are, and the MCP server encodes tool results with a plain ``json.dumps``.
    A telegram carrying a decoded DPT 10/11/19 value is the case that bites:
    its value is an xknx ``KNXTime``/``KNXDate``/``KNXDateTime`` holding a
    ``KNXDay`` enum, which would raise ``TypeError`` at request time.
    """
    if is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Enum):
        return _json_safe(value.value)
    # ``datetime`` is a ``date`` subclass, so this covers all three.
    if isinstance(value, (date, time)):
        return value.isoformat()
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def _serialize(result: Any) -> JsonObjectType:
    """Serialize a library result (dataclass, list or mapping) to a JSON object."""
    if is_dataclass(result) and not isinstance(result, type):
        return cast(JsonObjectType, _json_safe(result))
    if isinstance(result, list):
        return {"items": [_json_safe(item) for item in result]}
    if isinstance(result, dict):
        return cast(JsonObjectType, _json_safe(result))
    # A library function returning a bare scalar (or None): wrap it so the
    # tool's return value always satisfies the JsonObjectType contract.
    return {"result": _json_safe(result)}


class KNXTool(llm.Tool):
    """A KNX LLM tool wrapping a library ``*.mcp`` function."""

    def __init__(self, knx: KNXModule, spec: _ToolSpec) -> None:
        """Initialize the tool."""
        self.name = spec.name
        self.title = spec.title
        self.description = spec.description
        self.parameters = spec.parameters
        self.annotations = spec.annotations
        self.integration = DOMAIN
        self._knx = knx
        self._func = spec.func

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        """Validate arguments, run the library function and serialize the result."""
        args = self.parameters(tool_input.tool_args)
        try:
            result = await self._func(self._knx, args)
        except (
            ConfigStoreException,
            KnxTelegramStoreException,
            ValueError,
            XKNXException,
        ) as err:
            # ``ValueError`` covers an unknown DPT name passed to the xknx DPT
            # tools - the likeliest way for a model to get an argument wrong.
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="llm_tool_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return llm.ToolResult(data=_serialize(result))


def _require_store(knx: KNXModule) -> TelegramStore:
    """The telegram store, or raise if it is not configured/available."""
    store = knx.telegrams.store
    if store is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="llm_telegram_store_unavailable",
        )
    return store


async def _require_project(knx: KNXModule) -> KNXProjectModel:
    """The full parsed ETS project, or raise if none is loaded."""
    project = await knx.project.get_knxproject()
    if project is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="llm_no_project_loaded",
        )
    return project


def _store_func(lib_func: Callable, *, takes_input: bool = True) -> _ToolFunc:
    async def _call(knx: KNXModule, args: Any) -> Any:
        store = _require_store(knx)
        if takes_input:
            return await lib_func(store, args)
        return await lib_func(store)

    return _call


def _project_func(
    lib_func: Callable,
    *,
    takes_input: bool = True,
    positional: tuple[str, ...] = (),
) -> _ToolFunc:
    async def _call(knx: KNXModule, args: Any) -> Any:
        project = await _require_project(knx)
        if positional:
            return await lib_func(project, *(args[name] for name in positional))
        if takes_input:
            return await lib_func(project, args)
        return await lib_func(project)

    return _call


def _dpt_func(
    lib_func: Callable,
    *,
    takes_input: bool = True,
    positional: tuple[str, ...] = (),
) -> _ToolFunc:
    async def _call(knx: KNXModule, args: Any) -> Any:
        if positional:
            return await lib_func(*(args[name] for name in positional))
        if takes_input:
            return await lib_func(args)
        return await lib_func()

    return _call


def _address_order(address: str) -> tuple[int, ...] | tuple[()]:
    """Sort key putting "1/1/2" before "1/1/10" rather than after it.

    Any address style splits on "/"; anything unparsable sorts first, which
    only has to be stable for paging to hold.
    """
    try:
        return tuple(int(part) for part in address.split("/"))
    except ValueError:
        return ()


def _last_values_func() -> _ToolFunc:
    """Page through the last values, which knx-telegram-store returns in full.

    ``get_last_values`` yields one entry per group address ever seen on the bus
    - thousands on a real installation - and takes no limit. The backend query
    carries no ``ORDER BY`` either, so the rows are sorted by destination to
    keep paging stable. Drop this once the library paginates itself.
    """

    async def _call(knx: KNXModule, args: Mapping[str, Any]) -> Any:
        telegrams = await kts_mcp.get_last_values(
            _require_store(knx),
            kts_mcp.LastValuesInput(destinations=args["destinations"]),
        )
        telegrams.sort(key=lambda telegram: _address_order(telegram.destination))
        return _paginate(telegrams, args, "telegrams")

    return _call


def _topology_func() -> _ToolFunc:
    """Page through the topology by line, which xknxproject returns in full.

    Areas are the wrong unit to page on: KNX allows at most 16 of them, so a
    page of 100 never binds and every call returns the whole topology with all
    lines and device addresses embedded - half a megabyte on a fully populated
    installation. Lines are capped at 256 per project and 255 device addresses
    each, so paging on them actually splits the result. Each line carries its
    area, so the grouping survives the flattening.
    """

    async def _call(knx: KNXModule, args: Mapping[str, Any]) -> Any:
        result = await xknxproject_mcp.get_topology(await _require_project(knx))
        lines = [
            {"area": area.name, "area_description": area.description, **asdict(line)}
            for area in result.areas
            for line in area.lines
        ]
        return _paginate(lines, args, "lines")

    return _call


def _similar_channels_func() -> _ToolFunc:
    """Page through the similar channels, which xknxproject returns in full.

    Every output of every actuator of a kind matches at once, each with its
    group objects aligned against the reference. The channels are the unit to
    page on; the aligned group objects are cut down to the channels of the page
    and the reference, so a page stays self-contained.
    """

    async def _call(knx: KNXModule, args: Mapping[str, Any]) -> Any:
        result = await xknxproject_mcp.find_similar_channels(
            await _require_project(knx),
            xknxproject_mcp.FindSimilarChannelsInput(
                device_address=args["device_address"],
                channel_identifier=args["channel_identifier"],
                match_functional_blocks=args["match_functional_blocks"],
                match_module_definition=args["match_module_definition"],
            ),
        )
        page = _paginate(result.channels, args, "channels")
        shown = {
            (channel.device_address, channel.identifier) for channel in page["channels"]
        } | {(args["device_address"], args["channel_identifier"])}
        aligned = [
            {
                "key": group.key,
                "function_text": group.function_text,
                "entries": entries,
            }
            for group in result.aligned_group_objects
            if (
                entries := [
                    entry
                    for entry in group.entries
                    if (entry.device_address, entry.channel_identifier) in shown
                ]
            )
        ]
        return {
            "found": result.found,
            "reference": result.reference,
            **page,
            "aligned_group_objects": aligned,
        }

    return _call


def _xknx_func(lib_func: Callable, *, takes_input: bool = True) -> _ToolFunc:
    async def _call(knx: KNXModule, args: Any) -> Any:
        if takes_input:
            return await lib_func(knx.xknx, args)
        return await lib_func(knx.xknx)

    return _call


def _suggestions_func() -> _ToolFunc:
    """Page through the entity suggestions, which are generated in full."""

    async def _call(knx: KNXModule, args: Mapping[str, Any]) -> Any:
        result = await async_get_entity_suggestions(
            knx.hass,
            knx,
            SuggestionFilter(
                platform=args["platform"],
                group_id=args["group_id"],
                include_configured=args["include_configured"],
            ),
        )
        return {
            **_paginate(result["suggestions"], args, "suggestions"),
            "providers": result["providers"],
        }

    return _call


async def _entity_schema(knx: KNXModule, args: Mapping[str, Any]) -> Any:
    """The options of the `knx` part of an entity configuration."""
    return {"schema": get_serialized_schema(args[CONF_PLATFORM])}


async def _entity_store_data(knx: KNXModule, args: Mapping[str, Any]) -> dict[str, Any]:
    """Assemble entity store data from tool arguments.

    A suggestion provides the platform and the `knx` options; arguments given
    next to it take precedence, so a suggestion can be adjusted on the way.
    """
    platform: str | None = args.get(CONF_PLATFORM)
    entity: dict[str, Any] = dict(args.get("entity", {}))
    knx_options: dict[str, Any] = {}
    if (suggestion_id := args.get("suggestion_id")) is not None:
        result = await async_get_entity_suggestions(knx.hass, knx)
        suggestion = next(
            (item for item in result["suggestions"] if item["id"] == suggestion_id),
            None,
        )
        if suggestion is None:
            raise ValueError(f"Entity suggestion not found: {suggestion_id}")
        if platform is None:
            platform = suggestion["platform_options"][0]
        if platform not in suggestion["suggestions"]:
            raise ValueError(
                f"Entity suggestion {suggestion_id} is not available for {platform}; "
                f"use one of {', '.join(suggestion['platform_options'])}"
            )
        knx_options = dict(suggestion["suggestions"][platform]["knx"])
        if not entity.get("name") and entity.get("device_info") is None:
            entity["name"] = suggestion["suggested_name"]
    elif platform is None:
        raise ValueError("One of `platform` or `suggestion_id` is required")
    return {
        CONF_PLATFORM: platform,
        CONF_DATA: {"entity": entity, "knx": knx_options | args.get("knx", {})},
    }


def _entity_func(*, create: bool) -> _ToolFunc:
    """Validate an entity configuration, and create the entity if asked to.

    An invalid configuration is a result, not an error: it tells which option
    is wrong and why, which is what a model needs to correct it.
    """

    async def _call(knx: KNXModule, args: Mapping[str, Any]) -> Any:
        try:
            validated = validate_entity_data(await _entity_store_data(knx, args))
        except EntityStoreValidationException as err:
            return err.validation_error
        entity_id: str | None = None
        if create:
            entity_id = await knx.config_store.create_entity(
                validated[CONF_PLATFORM], validated[CONF_DATA]
            )
        return {"success": True, "entity_id": entity_id}

    return _call


async def _create_device(knx: KNXModule, args: Mapping[str, Any]) -> Any:
    """Create a device and tell how entities refer to it."""
    device = async_create_ui_device(
        knx.hass, knx.entry, args["name"], args.get("area_id")
    )
    return {
        "device_id": device.id,
        "device_info": next(
            identifier for domain, identifier in device.identifiers if domain == DOMAIN
        ),
        "name": device.name,
        "area_id": device.area_id,
    }


async def _list_entities(knx: KNXModule, args: Mapping[str, Any]) -> Any:
    """The entities created from the UI or by create_entity, with their addresses."""
    group_addresses: dict[tuple[str, str], list[str]] = {}
    for group_address, users in knx.get_group_address_entities().items():
        for user in users:
            group_addresses.setdefault(
                (user["platform"], user["unique_id"]), []
            ).append(group_address)
    entities = [
        {
            CONF_ENTITY_ID: entry.entity_id,
            CONF_PLATFORM: entry.domain,
            "name": entry.name or entry.original_name,
            "device_id": entry.device_id,
            "disabled": entry.disabled,
            "group_addresses": sorted(
                group_addresses.get((entry.domain, entry.unique_id), []),
                key=_address_order,
            ),
        }
        for entry in sorted(
            knx.config_store.get_entity_entries(), key=lambda entry: entry.entity_id
        )
        if args[CONF_PLATFORM] in (None, entry.domain)
    ]
    return _paginate(entities, args, "entities")


async def _get_entity_config(knx: KNXModule, args: Mapping[str, Any]) -> Any:
    """The stored configuration of an entity."""
    return knx.config_store.get_entity_config(args[CONF_ENTITY_ID])


async def _update_entity(knx: KNXModule, args: Mapping[str, Any]) -> Any:
    """Replace the configuration of an entity.

    As for a new entity, an invalid configuration is a result, not an error.
    """
    entity_id: str = args[CONF_ENTITY_ID]
    platform = knx.config_store.get_entity_config(entity_id)[CONF_PLATFORM]
    try:
        validated = validate_entity_data(
            {
                CONF_PLATFORM: platform,
                CONF_DATA: {"entity": args["entity"], "knx": args["knx"]},
            }
        )
    except EntityStoreValidationException as err:
        return err.validation_error
    await knx.config_store.update_entity(
        validated[CONF_PLATFORM], entity_id, validated[CONF_DATA]
    )
    return {"success": True, CONF_ENTITY_ID: entity_id}


async def _delete_entity(knx: KNXModule, args: Mapping[str, Any]) -> Any:
    """Delete an entity and its configuration."""
    await knx.config_store.delete_entity(args[CONF_ENTITY_ID])
    return {"success": True}


async def _delete_device(knx: KNXModule, args: Mapping[str, Any]) -> Any:
    """Delete a device and its entities, as removing it in the UI does."""
    device_id: str = args["device_id"]
    device_registry = dr.async_get(knx.hass)
    device = device_registry.async_get(device_id, include_composite_devices=False)
    if device is None or device.config_entry_id != knx.entry.entry_id:
        raise ValueError(f"KNX device not found: {device_id}")
    if not await async_remove_ui_entities_of_device(knx.hass, knx, device):
        raise ValueError(
            f"Device {device_id} can not be removed: it is the KNX interface or "
            "has entities configured in YAML"
        )
    if device_registry.async_get(device_id):
        device_registry.async_remove_device(device_id)
    return {"success": True}


_PLATFORM_VALIDATOR = probatio.In(sorted(SUPPORTED_PLATFORMS_UI))
_ENTITY_MARKERS: dict[Any, Any] = {
    probatio.Optional(
        CONF_PLATFORM,
        description=(
            "Entity platform. Required unless a suggestion is given, which "
            "defaults to the first of its platform options."
        ),
    ): _PLATFORM_VALIDATOR,
    probatio.Optional(
        "suggestion_id",
        description=(
            "Id of a suggestion from list_entity_suggestions to take the platform "
            "and `knx` options from."
        ),
    ): str,
    probatio.Optional(
        "entity",
        description=(
            "Common entity options: `name`, `device_info` (from create_device; "
            "an entity without a name is the main entity of its device) and "
            '`entity_category` ("config" or "diagnostic"). A name or a device is '
            "required; a suggestion without either uses its suggested name."
        ),
    ): dict,
    probatio.Optional(
        "knx",
        description=(
            "Platform options as described by get_entity_schema. A group address "
            'option is an object like {"write": "1/2/3", "state": "1/2/4", '
            '"passive": [], "dpt": "9.001"} - `dpt` only where the schema lists '
            "DPTs to choose from. Options given next to a suggestion replace "
            "those of the suggestion."
        ),
    ): dict,
}


def _tool_specs() -> list[_ToolSpec]:
    return [
        _ToolSpec(
            "query_telegrams",
            "Search telegram history",
            "Search stored KNX telegrams by time range, source/destination address, "
            "type, direction and DPT, with optional context windows around matches.",
            _schema_from_dataclass(kts_mcp.QueryTelegramsInput),
            _store_func(kts_mcp.query_telegrams),
            _READ_ONLY,
        ),
        _ToolSpec(
            "get_last_values",
            "Last value per group address",
            "Most recent telegram for each group address, optionally filtered to given "
            "destinations.",
            probatio.Schema(
                {
                    probatio.Optional(
                        "destinations",
                        description=_field_description(
                            kts_mcp.LastValuesInput, "destinations"
                        ),
                        default=list,
                    ): [str],
                    **_PAGINATION_MARKERS,
                }
            ),
            _last_values_func(),
            _READ_ONLY,
        ),
        _ToolSpec(
            "get_store_stats",
            "Telegram store statistics",
            "Telegram count, covered time range, on-disk size, backend and retention.",
            probatio.Schema({}),
            _store_func(kts_mcp.get_store_stats, takes_input=False),
            _READ_ONLY,
        ),
        _ToolSpec(
            "get_store_capabilities",
            "Telegram store capabilities",
            "What the telegram-store backend supports (time range, pagination, size, …).",
            probatio.Schema({}),
            _store_func(kts_mcp.get_store_capabilities, takes_input=False),
            _READ_ONLY,
        ),
        _ToolSpec(
            "count_telegrams",
            "Count stored telegrams",
            "Total number of stored telegrams.",
            probatio.Schema({}),
            _store_func(kts_mcp.count_telegrams, takes_input=False),
            _READ_ONLY,
        ),
        _ToolSpec(
            "get_project_info",
            "ETS project overview",
            "Loaded ETS project metadata and top-level entity counts.",
            probatio.Schema({}),
            _project_func(xknxproject_mcp.get_project_info, takes_input=False),
            _READ_ONLY,
        ),
        _ToolSpec(
            "list_group_addresses",
            "List group addresses",
            "List project group addresses. Text matches address/name/description.",
            _schema_from_dataclass(xknxproject_mcp.GroupAddressFilter),
            _project_func(xknxproject_mcp.list_group_addresses),
            _READ_ONLY,
        ),
        _ToolSpec(
            "describe_group_address",
            "Describe a group address",
            "Resolve one group address to its communication objects and devices.",
            probatio.Schema(
                {
                    probatio.Required(
                        "address", description='Group address to resolve, e.g. "1/2/3".'
                    ): str
                }
            ),
            _project_func(
                xknxproject_mcp.describe_group_address, positional=("address",)
            ),
            _READ_ONLY,
        ),
        _ToolSpec(
            "list_devices",
            "List devices",
            "List project devices. Text matches individual address/name/manufacturer.",
            _schema_from_dataclass(xknxproject_mcp.DeviceFilter),
            _project_func(xknxproject_mcp.list_devices),
            _READ_ONLY,
        ),
        _ToolSpec(
            "list_communication_objects",
            "List communication objects",
            "List communication objects, optionally scoped to a device and/or a linked "
            "group address.",
            _schema_from_dataclass(xknxproject_mcp.CommunicationObjectFilter),
            _project_func(xknxproject_mcp.list_communication_objects),
            _READ_ONLY,
        ),
        _ToolSpec(
            "list_channels",
            "List device channels",
            "List device channels (e.g. one output of an actuator) with their "
            "functional blocks. Devices whose application defines no channels "
            "have none.",
            _schema_from_dataclass(xknxproject_mcp.ChannelFilter),
            _project_func(xknxproject_mcp.list_channels),
            _READ_ONLY,
        ),
        _ToolSpec(
            "describe_channel",
            "Describe a device channel",
            "Resolve one channel of a device to its communication objects and "
            "their group addresses.",
            probatio.Schema(
                {
                    probatio.Required(
                        "device_address",
                        description='Individual address of the device, e.g. "1.1.5".',
                    ): str,
                    probatio.Required(
                        "channel_identifier",
                        description=(
                            'Channel identifier from list_channels, e.g. "CH-1".'
                        ),
                    ): str,
                }
            ),
            _project_func(
                xknxproject_mcp.describe_channel,
                positional=("device_address", "channel_identifier"),
            ),
            _READ_ONLY,
        ),
        _ToolSpec(
            "find_similar_channels",
            "Find similar channels",
            "Find channels sharing a functional block or module definition with a "
            "reference channel, and align their group objects so the group "
            "addresses of the same role can be read off per channel.",
            probatio.Schema(
                {
                    **{
                        probatio.Required(
                            name,
                            description=_field_description(
                                xknxproject_mcp.FindSimilarChannelsInput, name
                            ),
                        ): str
                        for name in ("device_address", "channel_identifier")
                    },
                    **{
                        probatio.Optional(
                            name,
                            description=_field_description(
                                xknxproject_mcp.FindSimilarChannelsInput, name
                            ),
                            default=True,
                        ): bool
                        for name in (
                            "match_functional_blocks",
                            "match_module_definition",
                        )
                    },
                    **_PAGINATION_MARKERS,
                }
            ),
            _similar_channels_func(),
            _READ_ONLY,
        ),
        _ToolSpec(
            "get_topology",
            "Bus topology",
            "Bus topology, one entry per line: the line's area, medium type and "
            "device addresses.",
            probatio.Schema(dict(_PAGINATION_MARKERS)),
            _topology_func(),
            _READ_ONLY,
        ),
        _ToolSpec(
            "list_functions",
            "List functions",
            "List project functions/functional blocks. Text matches identifier/name/type.",
            _schema_from_dataclass(xknxproject_mcp.FunctionFilter),
            _project_func(xknxproject_mcp.list_functions),
            _READ_ONLY,
        ),
        _ToolSpec(
            "describe_function",
            "Describe a function",
            "Resolve one function/functional block by identifier to its group address "
            "references and roles.",
            probatio.Schema(
                {
                    probatio.Required(
                        "identifier",
                        description="Function/functional-block identifier to resolve.",
                    ): str
                }
            ),
            _project_func(
                xknxproject_mcp.describe_function, positional=("identifier",)
            ),
            _READ_ONLY,
        ),
        _ToolSpec(
            "list_entity_suggestions",
            "List entity suggestions",
            "Entities that could be created, derived from the ETS project "
            "(functional blocks of device channels, building functions) and from "
            "entities already configured for similar channels. Each suggestion "
            "has a ready-made configuration per platform it can be created as.",
            probatio.Schema(
                {
                    probatio.Optional(
                        CONF_PLATFORM,
                        description=_field_description(SuggestionFilter, "platform"),
                        default=None,
                    ): probatio.Any(None, _PLATFORM_VALIDATOR),
                    probatio.Optional(
                        "group_id",
                        description=_field_description(SuggestionFilter, "group_id"),
                        default=None,
                    ): probatio.Any(None, str),
                    # Unlike the panel, which marks them, a model asks for
                    # suggestions to find out what is still missing.
                    probatio.Optional(
                        "include_configured",
                        description=_field_description(
                            SuggestionFilter, "include_configured"
                        ),
                        default=False,
                    ): bool,
                    **_PAGINATION_MARKERS,
                }
            ),
            _suggestions_func(),
            _READ_ONLY,
        ),
        _ToolSpec(
            "get_entity_schema",
            "Entity options of a platform",
            "The options of the `knx` part of an entity configuration of a platform: "
            "their names, whether they are required, defaults, and for group "
            "address options which of write/state/passive addresses and which "
            "DPTs they accept.",
            probatio.Schema(
                {
                    probatio.Required(
                        CONF_PLATFORM, description='Entity platform, e.g. "light".'
                    ): _PLATFORM_VALIDATOR
                }
            ),
            _entity_schema,
            _READ_ONLY,
        ),
        _ToolSpec(
            "validate_entity",
            "Validate an entity configuration",
            "Check an entity configuration without creating the entity. Reports "
            "the options that are invalid and why.",
            probatio.Schema(dict(_ENTITY_MARKERS)),
            _entity_func(create=False),
            _READ_ONLY,
        ),
        _ToolSpec(
            "create_entity",
            "Create an entity",
            "Create a KNX entity in Home Assistant from a suggestion, from a "
            "configuration, or from a suggestion adjusted by a configuration. "
            "Returns the entity id, or the invalid options if the configuration "
            "is not valid.",
            probatio.Schema(dict(_ENTITY_MARKERS)),
            _entity_func(create=True),
            _CONFIG_ADD,
        ),
        _ToolSpec(
            "create_device",
            "Create a device",
            "Create a Home Assistant device to group KNX entities in, optionally "
            "in an area. Returns the `device_info` to use in the entity options.",
            probatio.Schema(
                {
                    probatio.Required("name", description="Name of the device."): str,
                    probatio.Optional(
                        "area_id",
                        description="Id of the Home Assistant area of the device.",
                    ): str,
                }
            ),
            _create_device,
            _CONFIG_ADD,
        ),
        _ToolSpec(
            "list_entities",
            "List configured entities",
            "KNX entities created from the UI or by create_entity, with the "
            "group addresses they use and the device they belong to. Entities "
            "configured in YAML are not included.",
            probatio.Schema(
                {
                    probatio.Optional(
                        CONF_PLATFORM,
                        description='Only entities of this platform, e.g. "light".',
                        default=None,
                    ): probatio.Any(None, _PLATFORM_VALIDATOR),
                    **_PAGINATION_MARKERS,
                }
            ),
            _list_entities,
            _READ_ONLY,
        ),
        _ToolSpec(
            "get_entity_config",
            "Entity configuration",
            "The stored configuration of an entity from list_entities: its "
            "platform and the `entity` and `knx` options.",
            probatio.Schema(
                {
                    probatio.Required(
                        CONF_ENTITY_ID,
                        description='Entity id, e.g. "light.kitchen".',
                    ): str
                }
            ),
            _get_entity_config,
            _READ_ONLY,
        ),
        _ToolSpec(
            "update_entity",
            "Update an entity",
            "Replace the configuration of an entity from list_entities. Options "
            "left out are reset to their defaults, so start from "
            "get_entity_config. The platform can not be changed. Returns the "
            "invalid options if the configuration is not valid.",
            probatio.Schema(
                {
                    probatio.Required(
                        CONF_ENTITY_ID,
                        description='Entity id, e.g. "light.kitchen".',
                    ): str,
                    probatio.Required(
                        "entity",
                        description=(
                            "Common entity options: `name`, `device_info` and "
                            "`entity_category`."
                        ),
                    ): dict,
                    probatio.Required(
                        "knx",
                        description=(
                            "Platform options as described by get_entity_schema."
                        ),
                    ): dict,
                }
            ),
            _update_entity,
            _CONFIG_REPLACE,
        ),
        _ToolSpec(
            "delete_entity",
            "Delete an entity",
            "Delete an entity from list_entities together with its configuration.",
            probatio.Schema(
                {
                    probatio.Required(
                        CONF_ENTITY_ID,
                        description='Entity id, e.g. "light.kitchen".',
                    ): str
                }
            ),
            _delete_entity,
            _CONFIG_REMOVE,
        ),
        _ToolSpec(
            "delete_device",
            "Delete a device",
            "Delete a device made by create_device or in the UI, together with "
            "all entities assigned to it.",
            probatio.Schema(
                {
                    probatio.Required(
                        "device_id",
                        description=(
                            "Device id as returned by create_device or list_entities."
                        ),
                    ): str
                }
            ),
            _delete_device,
            _CONFIG_REMOVE,
        ),
        _ToolSpec(
            "list_dpts",
            "List data point types",
            "List known KNX data point types. Main restricts to a DPT main number; text "
            "matches the DPT number/value type/unit.",
            _schema_from_dataclass(xknx_mcp.DptFilter),
            _dpt_func(xknx_mcp.list_dpts),
            _READ_ONLY,
        ),
        _ToolSpec(
            "describe_dpt",
            "Describe a data point type",
            "Resolve a DPT number or value type name to its definition (value type, "
            "unit, numeric bounds).",
            probatio.Schema(
                {
                    probatio.Required(
                        "dpt",
                        description='DPT number ("9.001") or value type name ("temperature").',
                    ): str
                }
            ),
            _dpt_func(xknx_mcp.describe_dpt, positional=("dpt",)),
            _READ_ONLY,
        ),
        _ToolSpec(
            "encode_value",
            "Encode a value to a payload",
            "Encode a native value using a specific DPT into its raw payload bytes.",
            _schema_from_dataclass(xknx_mcp.EncodeDptPayloadInput),
            _dpt_func(xknx_mcp.encode_dpt_payload),
            _READ_ONLY,
        ),
        _ToolSpec(
            "decode_payload",
            "Decode a payload to a value",
            "Decode raw payload bytes (or an integer) using a specific DPT.",
            _schema_from_dataclass(xknx_mcp.DecodeDptPayloadInput),
            _dpt_func(xknx_mcp.decode_dpt_payload),
            _READ_ONLY,
        ),
        _ToolSpec(
            "get_connection_status",
            "Bus connection status",
            "KNX bus connection state, connection type and local individual address.",
            probatio.Schema({}),
            _xknx_func(xknx_mcp.get_connection_status, takes_input=False),
            _READ_ONLY,
        ),
        _ToolSpec(
            "read_group_value",
            "Read a group address from the bus",
            "Read a group address live from the bus (sends a GroupValueRead and waits).",
            _schema_from_dataclass(xknx_mcp.GroupValueReadInput),
            _xknx_func(xknx_mcp.read_group_value),
            _BUS_PROBE,
        ),
        _ToolSpec(
            "send_group_value_read",
            "Send a read request to the bus",
            "Queue a GroupValueRead telegram to trigger a response on the bus.",
            _schema_from_dataclass(xknx_mcp.GroupAddressInput),
            _xknx_func(xknx_mcp.send_group_value_read),
            _BUS_PROBE,
        ),
        _ToolSpec(
            "send_group_value_write",
            "Write a value to the bus",
            "Write a value to a group address (queues a GroupValueWrite).",
            _schema_from_dataclass(xknx_mcp.GroupValueWriteInput),
            _xknx_func(xknx_mcp.send_group_value_write),
            _BUS_WRITE,
        ),
    ]


def _build_tools(knx: KNXModule) -> list[llm.Tool]:
    """Build the KNX LLM tools for the given module."""
    return [KNXTool(knx, spec) for spec in _tool_specs()]


@dataclass(kw_only=True)
class KNXLLMAPI(llm.API):
    """LLM API exposing the KNX tools."""

    knx: KNXModule
    _tools: list[llm.Tool] = dc_field(init=False)

    def __post_init__(self) -> None:
        """Build the tools once.

        Nothing about them depends on the request, and compiling the schemas on
        every conversation turn and every MCP call is wasted work.
        """
        self._tools = _build_tools(self.knx)

    @override
    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the instance of the API."""
        return llm.APIInstance(
            api=self,
            api_prompt=API_PROMPT,
            llm_context=llm_context,
            tools=self._tools,
        )


@callback
def async_register_llm_api(hass: HomeAssistant, knx: KNXModule) -> CALLBACK_TYPE:
    """Register the KNX LLM API and return a callback to unregister it."""
    return llm.async_register_api(
        hass,
        KNXLLMAPI(
            hass=hass,
            id=LLM_API_ID,
            name=LLM_API_NAME,
            knx=knx,
        ),
    )
