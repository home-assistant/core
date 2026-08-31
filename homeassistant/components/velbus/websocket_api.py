"""Velbus config panel websocket API."""

from collections.abc import Awaitable, Callable
from functools import wraps
import inspect
from typing import TYPE_CHECKING, Any, Final, cast, overload

import velbus_frontend as velbus_panel
from velbusaio.channels import Channel
from velbusaio.exceptions import VelbusConfigError
from velbusaio.panel_schema import get_module_instance_data, get_module_type_schema
import voluptuous as vol

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

URL_BASE: Final = "/velbus_static"
DATA_STATIC_REGISTERED: Final = "static_registered"
DATA_WS_REGISTERED: Final = "ws_registered"
DATA_BUILD_ID: Final = "build_id"
DATA_PANEL: HassKey[dict[str, Any]] = HassKey(f"{DOMAIN}_panel")

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
    hass: HomeAssistant, *, unloading_entry_id: str | None = None
) -> bool:
    """Return whether any Velbus entry has advanced mode enabled."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == unloading_entry_id:
            continue
        # Include SETUP_IN_PROGRESS so the panel can register during setup,
        # before the entry state becomes LOADED.
        if entry.state not in (
            ConfigEntryState.LOADED,
            ConfigEntryState.SETUP_IN_PROGRESS,
        ):
            continue
        if is_advanced_mode_enabled(entry):
            return True
    return False


async def async_update_panel(
    hass: HomeAssistant, *, unloading_entry_id: str | None = None
) -> None:
    """Register or remove the Velbus config panel based on advanced mode."""
    if not _any_advanced_mode_enabled(hass, unloading_entry_id=unloading_entry_id):
        frontend.async_remove_panel(hass, DOMAIN, warn_if_unknown=False)
        return

    panel_data = hass.data.setdefault(DATA_PANEL, {})
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

    build_id = await hass.async_add_executor_job(velbus_panel.get_build_id)
    module_url = f"{URL_BASE}/{velbus_panel.entrypoint_js}?v={build_id}"
    if async_panel_exists(hass, DOMAIN):
        if panel_data.get(DATA_BUILD_ID) == build_id:
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
    panel_data[DATA_BUILD_ID] = build_id


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


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "velbus/config_panel/get_base_data",
        vol.Required(CONF_CONFIG_ENTRY): str,
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
        vol.Required("type"): "velbus/config_panel/modules",
        vol.Required(CONF_CONFIG_ENTRY): str,
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
    for module in controller.get_modules().values():
        address = module.get_addresses()[0]
        channels = {
            str(channel_num): {"name": channel.get_name()}
            for channel_num, channel in module.get_channels().items()
        }
        modules.append(
            {
                "address": address,
                "name": module.get_name(),
                "type_id": module.get_type(),
                "type_name": module.get_type_name(),
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
        vol.Required("type"): "velbus/config_panel/module/schema",
        vol.Required(CONF_CONFIG_ENTRY): str,
        vol.Required("type_id"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
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
    connection.send_result(msg["id"], schema)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "velbus/config_panel/module/get",
        vol.Required(CONF_CONFIG_ENTRY): str,
        vol.Required(CONF_ADDRESS): vol.All(vol.Coerce(int), vol.Range(min=1, max=254)),
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
    data = await get_module_instance_data(module)
    data["device_id"] = _device_id_for_module(hass, entry, msg[CONF_ADDRESS])
    data["schema"] = await hass.async_add_executor_job(
        get_module_type_schema, module.get_type()
    )
    connection.send_result(msg["id"], data)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "velbus/config_panel/module/config/set",
        vol.Required(CONF_CONFIG_ENTRY): str,
        vol.Required(CONF_ADDRESS): vol.All(vol.Coerce(int), vol.Range(min=1, max=254)),
        # Specs include editable channels above 32 (e.g. temperature name 33/34).
        vol.Required(CONF_CHANNEL): vol.All(vol.Coerce(int), vol.Range(min=1, max=64)),
        vol.Required("key"): str,
        vol.Required("value"): vol.Any(str, bool, int, float),
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
        await param.set_value(msg["value"])
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
        vol.Required("type"): "velbus/config_panel/module/actions/get",
        vol.Required(CONF_CONFIG_ENTRY): str,
        vol.Required(CONF_ADDRESS): vol.All(vol.Coerce(int), vol.Range(min=1, max=254)),
        vol.Required(CONF_CHANNEL): vol.All(vol.Coerce(int), vol.Range(min=1, max=32)),
        vol.Optional("refresh", default=False): bool,
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

    if module.get_action_table(channel) is None:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_HOME_ASSISTANT_ERROR,
            "This relay does not support action-table programming",
        )
        return

    slots = await module.get_channel_actions(
        channel, refresh=msg["refresh"], include_empty=True
    )
    connection.send_result(
        msg["id"],
        {"slots": [slot.to_dict() for slot in slots]},
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "velbus/config_panel/module/actions/set",
        vol.Required(CONF_CONFIG_ENTRY): str,
        vol.Required(CONF_ADDRESS): vol.All(vol.Coerce(int), vol.Range(min=1, max=254)),
        vol.Required(CONF_CHANNEL): vol.All(vol.Coerce(int), vol.Range(min=1, max=32)),
        vol.Required("source_address"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=254)
        ),
        vol.Required("action"): vol.Any(str, int),
        vol.Optional("source_channel"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=32)
        ),
        vol.Optional("slot"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        vol.Optional("time1", default=0xFF): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        ),
        vol.Optional("time2", default=0xFF): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        ),
        vol.Optional("time3", default=0xFF): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        ),
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
        vol.Required("type"): "velbus/config_panel/module/actions/clear",
        vol.Required(CONF_CONFIG_ENTRY): str,
        vol.Required(CONF_ADDRESS): vol.All(vol.Coerce(int), vol.Range(min=1, max=254)),
        vol.Required(CONF_CHANNEL): vol.All(vol.Coerce(int), vol.Range(min=1, max=32)),
        vol.Optional("slot"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        vol.Optional("source_address"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=254)
        ),
        vol.Optional("source_channel"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=32)
        ),
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

    try:
        if msg.get("slot") is not None:
            cleared = [await relay.clear_action(msg["slot"])]
        elif msg.get("source_address") is not None:
            cleared = await relay.clear_actions_for_source(
                msg["source_address"],
                source_channel=msg.get("source_channel"),
            )
        else:
            connection.send_error(
                msg["id"],
                websocket_api.const.ERR_INVALID_FORMAT,
                "Provide slot or source_address",
            )
            return
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
