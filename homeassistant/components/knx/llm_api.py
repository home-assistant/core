"""Expose KNX tools (telegram store, ETS project, DPTs, bus) to LLMs.

The tool logic lives in the shared ``*.mcp`` subpackages of ``knx-telegram-store``,
``xknxproject`` and ``xknx``; this module only adapts those functions into
Home Assistant :class:`llm.Tool` objects and wires them to the running KNX module.
Each tool's parameter schema (and its per-parameter descriptions) is derived from
the library input dataclasses' ``dataclasses.field`` metadata, so the descriptions
stay single-sourced in the libraries.
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import MISSING, asdict, dataclass, fields, is_dataclass
from datetime import date, time
from enum import Enum
import types
from typing import (
    TYPE_CHECKING,
    Any,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    override,
)

from knx_telegram_store import KnxTelegramStoreException, TelegramStore, mcp as kts_mcp
import voluptuous as vol
from xknx import mcp as xknx_mcp
from xknx.exceptions import XKNXException
from xknxproject import mcp as xknxproject_mcp
from xknxproject.models import KNXProject as KNXProjectModel

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN

if TYPE_CHECKING:
    from .knx_module import KNXModule

LLM_API_ID = DOMAIN
LLM_API_NAME = "KNX"
API_PROMPT = (
    "Tools to inspect a KNX installation: stored bus telegrams, the loaded ETS "
    "project (group addresses, devices, communication objects, functions, "
    "topology, locations), KNX data point types, and live bus "
    'reads and writes. Address formats: group addresses like "1/2/3", individual '
    'device addresses like "1.1.5", DPTs like "9.001".'
)


type _ToolFunc = Callable[["KNXModule", dict[str, Any]], Awaitable[Any]]


def _reject_fractional(value: Any) -> Any:
    """Reject fractional floats so they are not silently truncated.

    ``vol.Coerce(int)`` calls ``int(value)``, which turns a float like ``5.5``
    into ``5`` instead of raising. That silently discards data, and in an
    ``int | float`` union (e.g. a KNX group value) it makes the int validator
    swallow every float before the float validator is ever tried. Only let
    floats through that are exactly representable as int (``5.0``).
    """
    if isinstance(value, float) and not value.is_integer():
        raise vol.Invalid("value has a fractional part; not a valid int")
    return value


# ``vol.Coerce(int)`` has to be the validator that does the conversion:
# ``voluptuous_openapi.convert`` cannot type a bare callable and would advertise
# the parameter to the LLM as a string.
_INT = vol.All(_reject_fractional, vol.Coerce(int))


def _union_member_order(annotation: Any) -> int:
    """Sort key placing exact-type union members before coercing ones.

    ``vol.Any`` takes the first member that validates. ``str`` and ``bool`` are
    plain isinstance checks while the int/float members coerce, so in source
    order a ``bool | int | float | str`` group value turns the string ``"5"``
    into the int ``5`` - writing a number where a DPT 16.000 text was meant.
    """
    return 0 if annotation in (str, bool) else 1


def _validator(annotation: Any) -> Any:
    """Map a dataclass field annotation to a voluptuous validator."""
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        non_none = [arg for arg in get_args(annotation) if arg is not type(None)]
        allows_none = len(non_none) != len(get_args(annotation))
        inner = (
            _validator(non_none[0])
            if len(non_none) == 1
            else vol.Any(
                *(_validator(arg) for arg in sorted(non_none, key=_union_member_order))
            )
        )
        return vol.Maybe(inner) if allows_none else inner
    if annotation is str:
        return str
    if annotation is bool:
        return bool
    if annotation is int:
        return _INT
    if annotation is float:
        return vol.Coerce(float)
    if origin is list:
        inner = get_args(annotation) or (str,)
        return [_validator(inner[0])]
    # Any, or an unrecognized type: pass through.
    return object


# The library ``_paginate`` helpers treat a negative limit as "no limit", which
# would return a whole ETS project or telegram history in a single tool result,
# and a negative offset slices from the end. The dataclasses don't express
# bounds, so they are applied here, by the field names the libraries share.
_MAX_RESULT_ITEMS = 1000
_FIELD_BOUNDS = {
    "limit": vol.Range(min=1, max=_MAX_RESULT_ITEMS),
    "offset": vol.Range(min=0),
    "delta_before_ms": vol.Range(min=0),
    "delta_after_ms": vol.Range(min=0),
}
_PAGINATION_MARKERS: dict[Any, Any] = {
    vol.Optional(
        "limit", description="Maximum number of results to return.", default=100
    ): vol.All(_INT, _FIELD_BOUNDS["limit"]),
    vol.Optional(
        "offset", description="Number of results to skip.", default=0
    ): vol.All(_INT, _FIELD_BOUNDS["offset"]),
}


def _schema_from_dataclass(input_type: type) -> vol.Schema:
    """Build a voluptuous schema from a library ``*.mcp`` input dataclass.

    Field descriptions come from ``dataclasses.field`` metadata; a field with a
    default becomes optional (with that default), otherwise it is required.
    """
    hints = get_type_hints(input_type)
    schema: dict[vol.Marker, Any] = {}
    for field in fields(input_type):
        description = field.metadata.get("description")
        if field.default is not MISSING:
            marker: vol.Marker = vol.Optional(
                field.name, description=description, default=field.default
            )
        elif field.default_factory is not MISSING:
            marker = vol.Optional(
                field.name, description=description, default=field.default_factory
            )
        else:
            marker = vol.Required(field.name, description=description)
        validator = _validator(hints[field.name])
        if (bounds := _FIELD_BOUNDS.get(field.name)) is not None:
            validator = vol.All(validator, bounds)
        schema[marker] = validator
    return vol.Schema(schema)


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

    def __init__(
        self,
        knx: KNXModule,
        name: str,
        description: str,
        parameters: vol.Schema,
        func: _ToolFunc,
    ) -> None:
        """Initialize the tool."""
        self.name = name
        self.description = description
        self.parameters = parameters
        self._knx = knx
        self._func = func

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Validate arguments, run the library function and serialize the result."""
        args = self.parameters(tool_input.tool_args)
        try:
            result = await self._func(self._knx, args)
        except (KnxTelegramStoreException, ValueError, XKNXException) as err:
            # ``ValueError`` covers an unknown DPT name passed to the xknx DPT
            # tools - the likeliest way for a model to get an argument wrong.
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="llm_tool_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return _serialize(result)


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


def _store_func(lib_func: Callable, input_type: type | None = None) -> _ToolFunc:
    async def _call(knx: KNXModule, args: dict[str, Any]) -> Any:
        store = _require_store(knx)
        if input_type is None:
            return await lib_func(store)
        return await lib_func(store, input_type(**args))

    return _call


def _project_func(
    lib_func: Callable,
    input_type: type | None = None,
    positional: tuple[str, ...] = (),
) -> _ToolFunc:
    async def _call(knx: KNXModule, args: dict[str, Any]) -> Any:
        project = await _require_project(knx)
        if positional:
            return await lib_func(project, *(args[name] for name in positional))
        if input_type is None:
            return await lib_func(project)
        return await lib_func(project, input_type(**args))

    return _call


def _dpt_func(
    lib_func: Callable,
    input_type: type | None = None,
    positional: tuple[str, ...] = (),
) -> _ToolFunc:
    async def _call(knx: KNXModule, args: dict[str, Any]) -> Any:
        if positional:
            return await lib_func(*(args[name] for name in positional))
        if input_type is None:
            return await lib_func()
        return await lib_func(input_type(**args))

    return _call


def _last_values_func() -> _ToolFunc:
    """Page through the last values, which knx-telegram-store returns in full.

    ``get_last_values`` yields one entry per group address ever seen on the
    bus - thousands on a real installation - and takes no limit, so the window
    is applied here. Drop this once the library paginates it itself.
    """

    async def _call(knx: KNXModule, args: dict[str, Any]) -> Any:
        limit = args.pop("limit")
        offset = args.pop("offset")
        telegrams = await kts_mcp.get_last_values(
            _require_store(knx), kts_mcp.LastValuesInput(**args)
        )
        window = telegrams[offset : offset + limit]
        limit_reached = offset + limit < len(telegrams)
        return {
            "telegrams": window,
            "total_count": len(telegrams),
            "offset": offset,
            "next_offset": offset + len(window) if limit_reached else None,
            "limit_reached": limit_reached,
        }

    return _call


def _xknx_func(lib_func: Callable, input_type: type | None = None) -> _ToolFunc:
    async def _call(knx: KNXModule, args: dict[str, Any]) -> Any:
        if input_type is None:
            return await lib_func(knx.xknx)
        return await lib_func(knx.xknx, input_type(**args))

    return _call


def _tool_specs() -> list[tuple[str, str, vol.Schema, _ToolFunc]]:
    return [
        (
            "query_telegrams",
            "Search stored KNX telegrams by time range, source/destination address, "
            "type, direction and DPT, with optional context windows around matches.",
            _schema_from_dataclass(kts_mcp.QueryTelegramsInput),
            _store_func(kts_mcp.query_telegrams, kts_mcp.QueryTelegramsInput),
        ),
        (
            "get_last_values",
            "Most recent telegram for each group address, optionally filtered to given "
            "destinations.",
            _schema_from_dataclass(kts_mcp.LastValuesInput).extend(_PAGINATION_MARKERS),
            _last_values_func(),
        ),
        (
            "get_store_stats",
            "Telegram count, covered time range, on-disk size, backend and retention.",
            vol.Schema({}),
            _store_func(kts_mcp.get_store_stats),
        ),
        (
            "get_store_capabilities",
            "What the telegram-store backend supports (time range, pagination, size, …).",
            vol.Schema({}),
            _store_func(kts_mcp.get_store_capabilities),
        ),
        (
            "count_telegrams",
            "Total number of stored telegrams.",
            vol.Schema({}),
            _store_func(kts_mcp.count_telegrams),
        ),
        (
            "get_project_info",
            "Loaded ETS project metadata and top-level entity counts.",
            vol.Schema({}),
            _project_func(xknxproject_mcp.get_project_info),
        ),
        (
            "list_group_addresses",
            "List project group addresses. Text matches address/name/description.",
            _schema_from_dataclass(xknxproject_mcp.GroupAddressFilter),
            _project_func(
                xknxproject_mcp.list_group_addresses, xknxproject_mcp.GroupAddressFilter
            ),
        ),
        (
            "describe_group_address",
            "Resolve one group address to its communication objects and devices.",
            vol.Schema(
                {
                    vol.Required(
                        "address", description='Group address to resolve, e.g. "1/2/3".'
                    ): str
                }
            ),
            _project_func(
                xknxproject_mcp.describe_group_address, positional=("address",)
            ),
        ),
        (
            "list_devices",
            "List project devices. Text matches individual address/name/manufacturer.",
            _schema_from_dataclass(xknxproject_mcp.DeviceFilter),
            _project_func(xknxproject_mcp.list_devices, xknxproject_mcp.DeviceFilter),
        ),
        (
            "list_communication_objects",
            "List communication objects, optionally scoped to a device and/or a linked "
            "group address.",
            _schema_from_dataclass(xknxproject_mcp.CommunicationObjectFilter),
            _project_func(
                xknxproject_mcp.list_communication_objects,
                xknxproject_mcp.CommunicationObjectFilter,
            ),
        ),
        (
            "get_topology",
            "Bus topology: areas, their lines and device addresses.",
            vol.Schema({}),
            _project_func(xknxproject_mcp.get_topology),
        ),
        (
            "list_locations",
            "Building/location tree (spaces, nested, with devices and functions).",
            vol.Schema({}),
            _project_func(xknxproject_mcp.list_locations),
        ),
        (
            "list_functions",
            "List project functions/functional blocks. Text matches identifier/name/type.",
            _schema_from_dataclass(xknxproject_mcp.FunctionFilter),
            _project_func(
                xknxproject_mcp.list_functions, xknxproject_mcp.FunctionFilter
            ),
        ),
        (
            "describe_function",
            "Resolve one function/functional block by identifier to its group address "
            "references and roles.",
            vol.Schema(
                {
                    vol.Required(
                        "identifier",
                        description="Function/functional-block identifier to resolve.",
                    ): str
                }
            ),
            _project_func(
                xknxproject_mcp.describe_function, positional=("identifier",)
            ),
        ),
        (
            "list_dpts",
            "List known KNX data point types. Main restricts to a DPT main number; text "
            "matches the DPT number/value type/unit.",
            _schema_from_dataclass(xknx_mcp.DptFilter),
            _dpt_func(xknx_mcp.list_dpts, xknx_mcp.DptFilter),
        ),
        (
            "describe_dpt",
            "Resolve a DPT number or value type name to its definition (value type, "
            "unit, numeric bounds).",
            vol.Schema(
                {
                    vol.Required(
                        "dpt",
                        description='DPT number ("9.001") or value type name ("temperature").',
                    ): str
                }
            ),
            _dpt_func(xknx_mcp.describe_dpt, positional=("dpt",)),
        ),
        (
            "encode_value",
            "Encode a native value using a specific DPT into its raw payload bytes.",
            _schema_from_dataclass(xknx_mcp.EncodeDptPayloadInput),
            _dpt_func(xknx_mcp.encode_dpt_payload, xknx_mcp.EncodeDptPayloadInput),
        ),
        (
            "decode_payload",
            "Decode raw payload bytes (or an integer) using a specific DPT.",
            _schema_from_dataclass(xknx_mcp.DecodeDptPayloadInput),
            _dpt_func(xknx_mcp.decode_dpt_payload, xknx_mcp.DecodeDptPayloadInput),
        ),
        (
            "get_connection_status",
            "KNX bus connection state, connection type and local individual address.",
            vol.Schema({}),
            _xknx_func(xknx_mcp.get_connection_status),
        ),
        (
            "read_group_value",
            "Read a group address live from the bus (sends a GroupValueRead and waits).",
            _schema_from_dataclass(xknx_mcp.GroupValueReadInput),
            _xknx_func(xknx_mcp.read_group_value, xknx_mcp.GroupValueReadInput),
        ),
        (
            "send_group_value_read",
            "Queue a GroupValueRead telegram to trigger a response on the bus.",
            _schema_from_dataclass(xknx_mcp.GroupAddressInput),
            _xknx_func(xknx_mcp.send_group_value_read, xknx_mcp.GroupAddressInput),
        ),
        (
            "send_group_value_write",
            "Write a value to a group address (queues a GroupValueWrite).",
            _schema_from_dataclass(xknx_mcp.GroupValueWriteInput),
            _xknx_func(xknx_mcp.send_group_value_write, xknx_mcp.GroupValueWriteInput),
        ),
    ]


def _build_tools(knx: KNXModule) -> list[llm.Tool]:
    """Build the KNX LLM tools for the given module."""
    return [
        KNXTool(knx, name, description, parameters, func)
        for name, description, parameters, func in _tool_specs()
    ]


@dataclass(kw_only=True)
class KNXLLMAPI(llm.API):
    """LLM API exposing the KNX tools."""

    knx: KNXModule

    @override
    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the instance of the API."""
        return llm.APIInstance(
            api=self,
            api_prompt=API_PROMPT,
            llm_context=llm_context,
            tools=_build_tools(self.knx),
        )


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
