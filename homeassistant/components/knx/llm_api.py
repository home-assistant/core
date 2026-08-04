"""Expose KNX tools (telegram store, ETS project, DPTs, bus) to LLMs.

The tool logic lives in the shared ``*.mcp`` subpackages of ``knx-telegram-store``,
``xknxproject`` and ``xknx``; this module only adapts those functions into
Home Assistant :class:`llm.Tool` objects and wires them to the running KNX module.
Each tool's parameter schema (and its per-parameter descriptions) is derived from
the library input dataclasses' ``dataclasses.field`` metadata, so the descriptions
stay single-sourced in the libraries.
"""

from collections.abc import Awaitable, Callable
from dataclasses import MISSING, asdict, dataclass, fields, is_dataclass
import types
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin, get_type_hints

from knx_telegram_store import KnxTelegramStoreException, mcp as kts_mcp
import voluptuous as vol
from xknx import mcp as xknx_mcp
from xknx.exceptions import XKNXException
from xknxproject import mcp as xknxproject_mcp

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


def _validator(annotation: Any) -> Any:
    """Map a dataclass field annotation to a voluptuous validator."""
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        non_none = [arg for arg in get_args(annotation) if arg is not type(None)]
        allows_none = len(non_none) != len(get_args(annotation))
        inner = (
            _validator(non_none[0])
            if len(non_none) == 1
            else vol.Any(*(_validator(arg) for arg in non_none))
        )
        return vol.Maybe(inner) if allows_none else inner
    if annotation is str:
        return str
    if annotation is bool:
        return bool
    if annotation is int:
        return vol.Coerce(int)
    if annotation is float:
        return vol.Coerce(float)
    if origin is list:
        inner = get_args(annotation) or (str,)
        return [_validator(inner[0])]
    # Any, or an unrecognized type: pass through.
    return object


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
        schema[marker] = _validator(hints[field.name])
    return vol.Schema(schema)


def _serialize(result: Any) -> JsonObjectType:
    """Serialize a library result (dataclass or list) to a JSON object."""
    if is_dataclass(result) and not isinstance(result, type):
        return asdict(result)
    if isinstance(result, list):
        return {
            "items": [
                asdict(item)
                if is_dataclass(item) and not isinstance(item, type)
                else item
                for item in result
            ]
        }
    return result


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
        except (KnxTelegramStoreException, XKNXException) as err:
            raise HomeAssistantError(str(err)) from err
        return _serialize(result)


def _require_store(knx: KNXModule) -> Any:
    """The telegram store, or raise if it is not configured/available."""
    store = knx.telegrams.store
    if store is None:
        raise HomeAssistantError(
            "The KNX telegram store is not configured or unavailable."
        )
    return store


async def _require_project(knx: KNXModule) -> Any:
    """The full parsed ETS project, or raise if none is loaded."""
    project = await knx.project.get_knxproject()
    if project is None:
        raise HomeAssistantError("No ETS project is loaded.")
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


def _xknx_func(lib_func: Callable, input_type: type | None = None) -> _ToolFunc:
    async def _call(knx: KNXModule, args: dict[str, Any]) -> Any:
        if input_type is None:
            return await lib_func(knx.xknx)
        return await lib_func(knx.xknx, input_type(**args))

    return _call


# name, description, parameter schema, callable. Read-only tools.
def _read_tool_specs() -> list[tuple[str, str, vol.Schema, _ToolFunc]]:
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
            _schema_from_dataclass(kts_mcp.LastValuesInput),
            _store_func(kts_mcp.get_last_values, kts_mcp.LastValuesInput),
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
    ]


def _bus_tool_specs() -> list[tuple[str, str, vol.Schema, _ToolFunc]]:
    return [
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
    specs = _read_tool_specs() + _bus_tool_specs()
    return [
        KNXTool(knx, name, description, parameters, func)
        for name, description, parameters, func in specs
    ]


@dataclass(kw_only=True)
class KNXLLMAPI(llm.API):
    """LLM API exposing the KNX tools."""

    knx: KNXModule

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
