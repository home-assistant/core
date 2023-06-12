"""KNX Websocket API."""
from __future__ import annotations

from typing import TYPE_CHECKING, Final

from knx_frontend import entrypoint_js, is_dev_build, locate_dir
import voluptuous as vol
from xknx.telegram import TelegramDirection
from xknxproject.exceptions import XknxProjectException

from homeassistant.components import panel_custom, websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, KNXBusMonitorMessage
from .telegrams import TelegramDict

if TYPE_CHECKING:
    from . import KNXModule


URL_BASE: Final = "/knx_static"


async def register_panel(hass: HomeAssistant) -> None:
    """Register the KNX Panel and Websocket API."""
    websocket_api.async_register_command(hass, ws_info)
    websocket_api.async_register_command(hass, ws_project_file_process)
    websocket_api.async_register_command(hass, ws_project_file_remove)
    websocket_api.async_register_command(hass, ws_group_monitor_info)
    websocket_api.async_register_command(hass, ws_subscribe_telegram)

    if DOMAIN not in hass.data.get("frontend_panels", {}):
        path = locate_dir()
        hass.http.register_static_path(
            URL_BASE,
            path,
            cache_headers=not is_dev_build,
        )
        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=DOMAIN,
            webcomponent_name="knx-frontend",
            sidebar_title=DOMAIN.upper(),
            sidebar_icon="mdi:bus-electric",
            module_url=f"{URL_BASE}/{entrypoint_js()}",
            embed_iframe=True,
            require_admin=True,
        )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "knx/info",
    }
)
@callback
def ws_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Handle get info command."""
    knx: KNXModule = hass.data[DOMAIN]

    _project_info = None
    if project_info := knx.project.info:
        _project_info = {
            "name": project_info["name"],
            "last_modified": project_info["last_modified"],
            "tool_version": project_info["tool_version"],
        }

    connection.send_result(
        msg["id"],
        {
            "version": knx.xknx.version,
            "connected": knx.xknx.connection_manager.connected.is_set(),
            "current_address": str(knx.xknx.current_address),
            "project": _project_info,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "knx/project_file_process",
        vol.Required("file_id"): str,
        vol.Required("password"): str,
    }
)
@websocket_api.async_response
async def ws_project_file_process(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Handle get info command."""
    knx: KNXModule = hass.data[DOMAIN]
    try:
        await knx.project.process_project_file(
            file_id=msg["file_id"],
            password=msg["password"],
        )
    except (ValueError, XknxProjectException) as err:
        # ValueError could raise from file_upload integration
        connection.send_error(
            msg["id"], websocket_api.const.ERR_HOME_ASSISTANT_ERROR, str(err)
        )
        return

    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "knx/project_file_remove",
    }
)
@websocket_api.async_response
async def ws_project_file_remove(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Handle get info command."""
    knx: KNXModule = hass.data[DOMAIN]
    await knx.project.remove_project_file()
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "knx/group_monitor_info",
    }
)
@callback
def ws_group_monitor_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Handle get info command of group monitor."""
    knx: KNXModule = hass.data[DOMAIN]
    recent_telegrams = [
        _telegram_dict_to_group_monitor(telegram)
        for telegram in knx.telegrams.recent_telegrams
    ]
    connection.send_result(
        msg["id"],
        {
            "project_loaded": knx.project.loaded,
            "recent_telegrams": recent_telegrams,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "knx/subscribe_telegrams",
    }
)
@callback
def ws_subscribe_telegram(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Subscribe to incoming and outgoing KNX telegrams."""
    knx: KNXModule = hass.data[DOMAIN]

    @callback
    def forward_telegram(telegram: TelegramDict) -> None:
        """Forward telegram to websocket subscription."""
        connection.send_event(
            msg["id"],
            _telegram_dict_to_group_monitor(telegram),
        )

    connection.subscriptions[msg["id"]] = knx.telegrams.async_listen_telegram(
        action=forward_telegram,
        name="KNX GroupMonitor subscription",
    )
    connection.send_result(msg["id"])


def _telegram_dict_to_group_monitor(telegram: TelegramDict) -> KNXBusMonitorMessage:
    """Convert a TelegramDict to a KNXBusMonitorMessage object."""
    direction = (
        "group_monitor_incoming"
        if telegram["direction"] == TelegramDirection.INCOMING.value
        else "group_monitor_outgoing"
    )

    _payload = telegram["payload"]
    if isinstance(_payload, tuple):
        payload = f"0x{bytes(_payload).hex()}"
    elif isinstance(_payload, int):
        payload = f"{_payload:d}"
    else:
        payload = ""

    timestamp = telegram["timestamp"].strftime("%H:%M:%S.%f")[:-3]

    if (value := telegram["value"]) is not None:
        unit = telegram["unit"]
        value = f"{value}{' ' + unit if unit else ''}"

    return KNXBusMonitorMessage(
        destination_address=telegram["destination"],
        destination_text=telegram["destination_name"],
        direction=direction,
        payload=payload,
        source_address=telegram["source"],
        source_text=telegram["source_name"],
        timestamp=timestamp,
        type=telegram["telegramtype"],
        value=value,
    )
