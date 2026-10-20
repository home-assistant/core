"""Velbus config panel websocket API."""

import asyncio
from collections.abc import Awaitable, Callable
from functools import wraps
import html
from importlib.metadata import version
import inspect
from typing import TYPE_CHECKING, Any, Final, cast, overload

import probatio
import velbus_frontend as velbus_panel
from velbusaio.channels import Channel
from velbusaio.exceptions import VelbusConfigError
from velbusaio.panel_schema import get_module_instance_data, get_module_type_schema

from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.frontend import async_panel_exists
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.util.hass_dict import HassKey

from .config import is_advanced_mode_enabled, require_advanced_mode
from .const import CONF_CHANNEL, CONF_CONFIG_ENTRY, DOMAIN
from .data import VelbusConfigEntry

if TYPE_CHECKING:
    from velbusaio.controller import Velbus
    from velbusaio.module import Module

FRONTEND_PACKAGE: Final = "velbus-frontend"
URL_BASE: Final = "/velbus_static"
DATA_STATIC_REGISTERED: Final = "static_registered"
DATA_STATIC_LOCK: Final = "static_lock"
DATA_ACTION_LOCKS: Final = "action_locks"
DATA_WS_REGISTERED: Final = "ws_registered"
DATA_BUILD_ID: Final = "build_id"
DATA_PANEL: HassKey[dict[str, Any]] = HassKey(f"{DOMAIN}_panel")

_ADDRESS = probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=254))
_RELAY_CHANNEL = probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=32))
_SOURCE_CHANNEL = probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=8))
_SLOT = probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=255))
_TIME_BYTE = probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=255))

type VelbusWebSocketHandler = Callable[
    [
        HomeAssistant,
        VelbusConfigEntry,
        Velbus,
        websocket_api.ActiveConnection,
        dict[str, Any],
    ],
    None,
]
type VelbusAsyncWebSocketHandler = Callable[
    [
        HomeAssistant,
        VelbusConfigEntry,
        Velbus,
        websocket_api.ActiveConnection,
        dict[str, Any],
    ],
    Awaitable[None],
]


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register Velbus websocket commands once."""
    panel_data = hass.data.setdefault(DATA_PANEL, {})
    if panel_data.get(DATA_WS_REGISTERED):
        return

    websocket_api.async_register_command(hass, ws_get_base_data)
    websocket_api.async_register_command(hass, ws_list_modules)
    websocket_api.async_register_command(hass, ws_get_module_schema)
    websocket_api.async_register_command(hass, ws_get_module)
    websocket_api.async_register_command(hass, ws_set_module_config)
    websocket_api.async_register_command(hass, ws_get_channel_actions)
    websocket_api.async_register_command(hass, ws_set_channel_action)
    websocket_api.async_register_command(hass, ws_clear_channel_action)
    panel_data[DATA_WS_REGISTERED] = True


def _any_advanced_mode_enabled(
    hass: HomeAssistant,
    *,
    unloading_entry_id: str | None = None,
    setting_up_entry_id: str | None = None,
) -> bool:
    """Return whether any Velbus entry has advanced mode enabled."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == unloading_entry_id:
            continue
        # The entry currently being set up is still SETUP_IN_PROGRESS. Other
        # in-progress entries must not keep the panel registered if their
        # setup later fails before the cleanup path runs.
        entry_is_loading = (
            setting_up_entry_id is not None
            and entry.entry_id == setting_up_entry_id
            and entry.state is ConfigEntryState.SETUP_IN_PROGRESS
        )
        if entry.state is not ConfigEntryState.LOADED and not entry_is_loading:
            continue
        if is_advanced_mode_enabled(entry):
            return True
    return False


async def async_update_panel(
    hass: HomeAssistant,
    *,
    unloading_entry_id: str | None = None,
    setting_up_entry_id: str | None = None,
) -> None:
    """Register or remove the Velbus config panel based on advanced mode."""
    if not _any_advanced_mode_enabled(
        hass,
        unloading_entry_id=unloading_entry_id,
        setting_up_entry_id=setting_up_entry_id,
    ):
        frontend.async_remove_panel(hass, DOMAIN, warn_if_unknown=False)
        return

    panel_data = hass.data.setdefault(DATA_PANEL, {})
    static_lock: asyncio.Lock = panel_data.setdefault(DATA_STATIC_LOCK, asyncio.Lock())
    async with static_lock:
        if not panel_data.get(DATA_STATIC_REGISTERED):
            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(
                        URL_BASE,
                        path=velbus_panel.locate_dir(),
                        cache_headers=velbus_panel.is_prod_build,
                    )
                ]
            )
            panel_data[DATA_STATIC_REGISTERED] = True

    panel_version = await hass.async_add_executor_job(version, FRONTEND_PACKAGE)
    module_url = f"{URL_BASE}/{velbus_panel.entrypoint_js}?v={panel_version}"
    if async_panel_exists(hass, DOMAIN):
        if panel_data.get(DATA_BUILD_ID) == panel_version:
            return
        frontend.async_remove_panel(hass, DOMAIN, warn_if_unknown=False)

    await panel_custom.async_register_panel(
        hass=hass,
        frontend_url_path=DOMAIN,
        config_panel_domain=DOMAIN,
        webcomponent_name=velbus_panel.webcomponent_name,
        module_url=module_url,
        embed_iframe=True,
        require_admin=True,
    )
    panel_data[DATA_BUILD_ID] = panel_version


def _get_entry(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> VelbusConfigEntry | None:
    entry_id = msg.get(CONF_CONFIG_ENTRY)
    if entry_id is None:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_INVALID_FORMAT, "Missing config_entry"
        )
        return None
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_NOT_FOUND,
            f"Config entry '{entry_id}' not found",
        )
        return None
    if entry.state is not ConfigEntryState.LOADED:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_HOME_ASSISTANT_ERROR,
            "Velbus config entry is not loaded",
        )
        return None
    return entry


@overload
def provide_velbus(
    func: VelbusAsyncWebSocketHandler,
) -> websocket_api.const.AsyncWebSocketCommandHandler: ...
@overload
def provide_velbus(
    func: VelbusWebSocketHandler,
) -> websocket_api.const.WebSocketCommandHandler: ...


def provide_velbus(
    func: VelbusAsyncWebSocketHandler | VelbusWebSocketHandler,
) -> (
    websocket_api.const.AsyncWebSocketCommandHandler
    | websocket_api.const.WebSocketCommandHandler
):
    """Websocket decorator to provide a Velbus config entry and controller."""

    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def with_velbus(
            hass: HomeAssistant,
            connection: websocket_api.ActiveConnection,
            msg: dict[str, Any],
        ) -> None:
            entry = _get_entry(hass, connection, msg)
            if entry is None:
                return
            await func(hass, entry, entry.runtime_data.controller, connection, msg)

    else:

        @wraps(func)
        def with_velbus(
            hass: HomeAssistant,
            connection: websocket_api.ActiveConnection,
            msg: dict[str, Any],
        ) -> None:
            entry = _get_entry(hass, connection, msg)
            if entry is None:
                return
            func(hass, entry, entry.runtime_data.controller, connection, msg)

    return with_velbus


def _device_id_for_module(
    hass: HomeAssistant, entry: VelbusConfigEntry, address: int
) -> str | None:
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, str(address)), entry.entry_id
    )
    if device is None:
        return None
    return device.id


def _get_module(controller: Velbus, address: int) -> Module:
    module = controller.get_module(address)
    if module is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="module_not_found",
            translation_placeholders={"address": str(address)},
        )
    return module


def _get_relay_channel(controller: Velbus, address: int, channel: int) -> Channel:
    module = _get_module(controller, address)
    relay = module.get_channels().get(channel)
    if relay is None or not hasattr(relay, "get_action_table"):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="relay_channel_not_found",
            translation_placeholders={
                "address": str(address),
                "channel": str(channel),
            },
        )
    return cast(Channel, relay)


def _escape_panel_text(value: str) -> str:
    """Escape text rendered in the Velbus config panel (legacy ha-select innerHTML)."""
    return html.escape(value, quote=True)


def _escape_channel_names(channels: dict[str, Any]) -> dict[str, Any]:
    """Escape channel display names in a channels mapping."""
    escaped: dict[str, Any] = {}
    for channel_id, channel_info in channels.items():
        if not isinstance(channel_info, dict):
            escaped[channel_id] = channel_info
            continue
        entry = dict(channel_info)
        name = entry.get("name")
        if isinstance(name, str):
            entry["name"] = _escape_panel_text(name)
        escaped[channel_id] = entry
    return escaped


def _escape_module_type_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Escape VLP-supplied labels in a module type schema."""
    escaped = dict(schema)
    type_name = escaped.get("type_name")
    if isinstance(type_name, str):
        escaped["type_name"] = _escape_panel_text(type_name)

    sections = escaped.get("sections")
    if not isinstance(sections, list):
        return escaped

    new_sections: list[Any] = []
    for section in sections:
        if not isinstance(section, dict):
            new_sections.append(section)
            continue
        section_copy = dict(section)
        channels = section_copy.get("channels")
        if isinstance(channels, list):
            new_channels: list[Any] = []
            for entry in channels:
                if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                    new_channels.append(
                        {**entry, "name": _escape_panel_text(entry["name"])}
                    )
                else:
                    new_channels.append(entry)
            section_copy["channels"] = new_channels
        properties = section_copy.get("properties")
        if isinstance(properties, list):
            section_copy["properties"] = [
                (
                    {**prop, "name": _escape_panel_text(prop["name"])}
                    if isinstance(prop, dict) and isinstance(prop.get("name"), str)
                    else prop
                )
                for prop in properties
            ]
        new_sections.append(section_copy)
    escaped["sections"] = new_sections
    return escaped


def _escape_module_instance_data(data: dict[str, Any]) -> dict[str, Any]:
    """Escape device-supplied labels in live module panel data."""
    escaped = dict(data)
    for key in ("name", "type_name"):
        value = escaped.get(key)
        if isinstance(value, str):
            escaped[key] = _escape_panel_text(value)
    channels = escaped.get("channels")
    if isinstance(channels, dict):
        escaped["channels"] = _escape_channel_names(channels)
    return escaped


def _coerce_config_value(param: Any, value: Any) -> Any:
    """Return a value coerced to the parameter kind.

    Values pass through when ``kind`` is not a string, so callers with
    incomplete parameter objects keep their existing behavior.
    """
    kind = getattr(param, "kind", None)
    if not isinstance(kind, str):
        return value

    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        raise ValueError(f"Invalid boolean value for '{param.key}': {value!r}")

    if kind == "number":
        try:
            number = float(value)
        except (TypeError, ValueError) as err:
            raise ValueError(f"Invalid number for '{param.key}': {value!r}") from err
        min_value = getattr(param, "min_value", None)
        max_value = getattr(param, "max_value", None)
        if isinstance(min_value, (int, float)) and not isinstance(min_value, bool):
            if number < min_value:
                raise ValueError(f"{param.key} below minimum {min_value}")
        if isinstance(max_value, (int, float)) and not isinstance(max_value, bool):
            if number > max_value:
                raise ValueError(f"{param.key} above maximum {max_value}")
        return number

    if kind == "select":
        selected = str(value)
        options = getattr(param, "options", None)
        if isinstance(options, list) and selected not in options:
            raise ValueError(f"{param.key} must be one of {options}, got {selected!r}")
        return selected

    if kind == "text":
        text = str(value)
        max_length = getattr(param, "max_length", None)
        if isinstance(max_length, int) and not isinstance(max_length, bool):
            if len(text) > max_length:
                raise ValueError(f"{param.key} exceeds max length {max_length}")
        return text

    raise ValueError(f"Unknown config kind {kind!r}")


def _action_table_lock(
    hass: HomeAssistant, entry_id: str, address: int, channel: int
) -> asyncio.Lock:
    """Return the lock that serializes action-table writes for one channel."""
    panel_data = hass.data.setdefault(DATA_PANEL, {})
    locks: dict[tuple[str, int, int], asyncio.Lock] = panel_data.setdefault(
        DATA_ACTION_LOCKS, {}
    )
    return locks.setdefault((entry_id, address, channel), asyncio.Lock())


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "velbus/config_panel/get_base_data",
        probatio.Required(CONF_CONFIG_ENTRY): str,
    }
)
@provide_velbus
@callback
def ws_get_base_data(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    controller: Velbus,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return base panel data."""
    connection.send_result(
        msg["id"],
        {
            "config_entry_id": entry.entry_id,
            "advanced_mode": is_advanced_mode_enabled(entry),
            "title": entry.title,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "velbus/config_panel/modules",
        probatio.Required(CONF_CONFIG_ENTRY): str,
    }
)
@provide_velbus
@callback
def ws_list_modules(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    controller: Velbus,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List modules for the config panel."""
    modules = []
    seen_modules: set[int] = set()
    for module in controller.get_modules().values():
        # The controller maps every occupied address to the same module object.
        module_id = id(module)
        if module_id in seen_modules:
            continue
        seen_modules.add(module_id)
        address = module.get_addresses()[0]
        channels = {
            str(channel_num): {"name": _escape_panel_text(channel.get_name())}
            for channel_num, channel in module.get_channels().items()
        }
        modules.append(
            {
                "address": address,
                "name": _escape_panel_text(module.get_name()),
                "type_id": module.get_type(),
                "type_name": _escape_panel_text(module.get_type_name()),
                "serial": module.get_serial(),
                "device_id": _device_id_for_module(hass, entry, address),
                "channels": channels,
            }
        )
    modules.sort(key=lambda item: item["address"])
    connection.send_result(msg["id"], {"modules": modules})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "velbus/config_panel/module/schema",
        probatio.Required(CONF_CONFIG_ENTRY): str,
        probatio.Required("type_id"): probatio.All(
            probatio.Coerce(int), probatio.Range(min=0, max=255)
        ),
    }
)
@websocket_api.async_response
@provide_velbus
async def ws_get_module_schema(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    controller: Velbus,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the schema for a module type."""
    schema = await hass.async_add_executor_job(get_module_type_schema, msg["type_id"])
    connection.send_result(msg["id"], _escape_module_type_schema(schema))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "velbus/config_panel/module/get",
        probatio.Required(CONF_CONFIG_ENTRY): str,
        probatio.Required(CONF_ADDRESS): _ADDRESS,
    }
)
@websocket_api.async_response
@provide_velbus
async def ws_get_module(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    controller: Velbus,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return live data for one module."""
    module = controller.get_module(msg[CONF_ADDRESS])
    if module is None:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_NOT_FOUND,
            f"Module {msg[CONF_ADDRESS]} not found",
        )
        return
    data = _escape_module_instance_data(await get_module_instance_data(module))
    data["device_id"] = _device_id_for_module(hass, entry, module.get_addresses()[0])
    data["schema"] = _escape_module_type_schema(
        await hass.async_add_executor_job(get_module_type_schema, module.get_type())
    )
    connection.send_result(msg["id"], data)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "velbus/config_panel/module/config/set",
        probatio.Required(CONF_CONFIG_ENTRY): str,
        probatio.Required(CONF_ADDRESS): _ADDRESS,
        # Specs include editable channels above 32 (e.g. temperature name 33/34).
        probatio.Required(CONF_CHANNEL): probatio.All(
            probatio.Coerce(int), probatio.Range(min=1, max=64)
        ),
        probatio.Required("key"): str,
        probatio.Required("value"): probatio.Any(str, bool, int, float),
    }
)
@websocket_api.async_response
@provide_velbus
async def ws_set_module_config(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    controller: Velbus,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Write a module or channel configuration parameter."""
    require_advanced_mode(entry)
    module = controller.get_module(msg[CONF_ADDRESS])
    if module is None:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_NOT_FOUND,
            f"Module {msg[CONF_ADDRESS]} not found",
        )
        return

    channel = module.get_channels().get(msg[CONF_CHANNEL])
    if channel is None or not hasattr(channel, "get_config_parameters"):
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_NOT_FOUND,
            f"Channel {msg[CONF_CHANNEL]} not found",
        )
        return

    param = next(
        (item for item in channel.get_config_parameters() if item.key == msg["key"]),
        None,
    )
    if param is None:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_INVALID_FORMAT,
            f"Unknown config key '{msg['key']}'",
        )
        return

    try:
        value = _coerce_config_value(param, msg["value"])
    except ValueError as err:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_INVALID_FORMAT,
            str(err),
        )
        return

    try:
        await param.set_value(value)
    except (OSError, RuntimeError, ValueError, VelbusConfigError) as err:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_HOME_ASSISTANT_ERROR,
            str(err),
        )
        return

    connection.send_result(msg["id"], {"success": True})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "velbus/config_panel/module/actions/get",
        probatio.Required(CONF_CONFIG_ENTRY): str,
        probatio.Required(CONF_ADDRESS): _ADDRESS,
        probatio.Required(CONF_CHANNEL): _RELAY_CHANNEL,
        probatio.Optional("refresh", default=False): bool,
    }
)
@websocket_api.async_response
@provide_velbus
async def ws_get_channel_actions(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    controller: Velbus,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Read the action table for a relay channel."""
    channel = msg[CONF_CHANNEL]
    try:
        module = _get_module(controller, msg[CONF_ADDRESS])
        _get_relay_channel(controller, msg[CONF_ADDRESS], channel)
    except ServiceValidationError as err:
        connection.send_error(msg["id"], websocket_api.const.ERR_NOT_FOUND, str(err))
        return

    table = module.get_action_table(channel)
    if table is None:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_HOME_ASSISTANT_ERROR,
            "This relay does not support action-table programming",
        )
        return

    slots = await table.get_actions(refresh=msg["refresh"], include_empty=True)
    connection.send_result(
        msg["id"],
        {"slots": [slot.to_dict() for slot in slots]},
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "velbus/config_panel/module/actions/set",
        probatio.Required(CONF_CONFIG_ENTRY): str,
        probatio.Required(CONF_ADDRESS): _ADDRESS,
        probatio.Required(CONF_CHANNEL): _RELAY_CHANNEL,
        probatio.Required("source_address"): _ADDRESS,
        probatio.Required("action"): probatio.Any(str, int),
        probatio.Optional("source_channel"): _SOURCE_CHANNEL,
        probatio.Optional("slot"): _SLOT,
        probatio.Optional("time1", default=0xFF): _TIME_BYTE,
        probatio.Optional("time2", default=0xFF): _TIME_BYTE,
        probatio.Optional("time3", default=0xFF): _TIME_BYTE,
    }
)
@websocket_api.async_response
@provide_velbus
async def ws_set_channel_action(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    controller: Velbus,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Program an action slot on a relay channel."""
    require_advanced_mode(entry)
    try:
        relay = _get_relay_channel(controller, msg[CONF_ADDRESS], msg[CONF_CHANNEL])
    except ServiceValidationError as err:
        connection.send_error(msg["id"], websocket_api.const.ERR_NOT_FOUND, str(err))
        return

    lock = _action_table_lock(
        hass, entry.entry_id, msg[CONF_ADDRESS], msg[CONF_CHANNEL]
    )
    async with lock:
        try:
            slot = await relay.set_action(
                source_address=msg["source_address"],
                action=msg["action"],
                source_channel=msg.get("source_channel"),
                slot=msg.get("slot"),
                time1=msg["time1"],
                time2=msg["time2"],
                time3=msg["time3"],
            )
        except (OSError, RuntimeError, ValueError, VelbusConfigError) as err:
            connection.send_error(
                msg["id"],
                websocket_api.const.ERR_HOME_ASSISTANT_ERROR,
                str(err),
            )
            return

    connection.send_result(msg["id"], {"slot": slot.to_dict()})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "velbus/config_panel/module/actions/clear",
        probatio.Required(CONF_CONFIG_ENTRY): str,
        probatio.Required(CONF_ADDRESS): _ADDRESS,
        probatio.Required(CONF_CHANNEL): _RELAY_CHANNEL,
        probatio.Optional("slot"): _SLOT,
        probatio.Optional("source_address"): _ADDRESS,
        probatio.Optional("source_channel"): _SOURCE_CHANNEL,
    }
)
@websocket_api.async_response
@provide_velbus
async def ws_clear_channel_action(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    controller: Velbus,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Clear one or more action slots on a relay channel."""
    require_advanced_mode(entry)
    try:
        relay = _get_relay_channel(controller, msg[CONF_ADDRESS], msg[CONF_CHANNEL])
    except ServiceValidationError as err:
        connection.send_error(msg["id"], websocket_api.const.ERR_NOT_FOUND, str(err))
        return

    if msg.get("slot") is None and msg.get("source_address") is None:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_INVALID_FORMAT,
            "Provide slot or source_address",
        )
        return

    lock = _action_table_lock(
        hass, entry.entry_id, msg[CONF_ADDRESS], msg[CONF_CHANNEL]
    )
    async with lock:
        try:
            if msg.get("slot") is not None:
                cleared = [await relay.clear_action(msg["slot"])]
            else:
                cleared = await relay.clear_actions_for_source(
                    msg["source_address"],
                    source_channel=msg.get("source_channel"),
                )
        except (OSError, RuntimeError, ValueError, VelbusConfigError) as err:
            connection.send_error(
                msg["id"],
                websocket_api.const.ERR_HOME_ASSISTANT_ERROR,
                str(err),
            )
            return

    connection.send_result(
        msg["id"],
        {"slots": [slot.to_dict() for slot in cleared]},
    )
