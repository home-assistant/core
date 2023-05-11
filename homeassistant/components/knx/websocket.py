"""KNX Websocket API."""
from __future__ import annotations

from collections.abc import Callable
from typing import Final

from knx_frontend import get_build_id, locate_dir
import voluptuous as vol
from xknx.dpt import DPTArray
from xknx.exceptions import XKNXException
from xknx.telegram import Telegram, TelegramDirection
from xknx.telegram.apci import GroupValueRead, GroupValueResponse, GroupValueWrite
from xknxproject.exceptions import XknxProjectException

from homeassistant.components import panel_custom, websocket_api
from homeassistant.core import HomeAssistant, callback
import homeassistant.util.dt as dt_util

from .const import (
    DOMAIN,
    AsyncMessageCallbackType,
    KNXBusMonitorMessage,
    MessageCallbackType,
)
from .project import KNXProject

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
        build_id = get_build_id()
        hass.http.register_static_path(
            URL_BASE, path, cache_headers=(build_id != "dev")
        )
        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=DOMAIN,
            webcomponent_name="knx-frontend",
            sidebar_title=DOMAIN.upper(),
            sidebar_icon="mdi:bus-electric",
            module_url=f"{URL_BASE}/entrypoint-{build_id}.js",
            embed_iframe=True,
            require_admin=True,
        )


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
    xknx = hass.data[DOMAIN].xknx

    _project_info = None
    if project_info := hass.data[DOMAIN].project.info:
        _project_info = {
            "name": project_info["name"],
            "last_modified": project_info["last_modified"],
            "tool_version": project_info["tool_version"],
        }

    connection.send_result(
        msg["id"],
        {
            "version": xknx.version,
            "connected": xknx.connection_manager.connected.is_set(),
            "current_address": str(xknx.current_address),
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
    knx_project = hass.data[DOMAIN].project
    try:
        await knx_project.process_project_file(
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
    knx_project = hass.data[DOMAIN].project
    await knx_project.remove_project_file()
    connection.send_result(msg["id"])


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
    project_loaded = hass.data[DOMAIN].project.loaded
    connection.send_result(
        msg["id"],
        {"project_loaded": bool(project_loaded)},
    )


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
    project: KNXProject = hass.data[DOMAIN].project

    async def forward_telegrams(telegram: Telegram) -> None:
        """Forward events to websocket."""
        payload: str
        dpt_payload = None
        if isinstance(telegram.payload, (GroupValueWrite, GroupValueResponse)):
            dpt_payload = telegram.payload.value
            if isinstance(dpt_payload, DPTArray):
                payload = f"0x{bytes(dpt_payload.value).hex()}"
            else:
                payload = f"{dpt_payload.value:d}"
        elif isinstance(telegram.payload, GroupValueRead):
            payload = ""
        else:
            return

        direction = (
            "group_monitor_incoming"
            if telegram.direction is TelegramDirection.INCOMING
            else "group_monitor_outgoing"
        )
        dst = str(telegram.destination_address)
        src = str(telegram.source_address)
        bus_message: KNXBusMonitorMessage = KNXBusMonitorMessage(
            destination_address=dst,
            destination_text=None,
            payload=payload,
            type=str(telegram.payload.__class__.__name__),
            value=None,
            source_address=src,
            source_text=None,
            direction=direction,
            timestamp=dt_util.as_local(dt_util.utcnow()).strftime("%H:%M:%S.%f")[:-3],
        )
        if project.loaded:
            if ga_infos := project.group_addresses.get(dst):
                bus_message["destination_text"] = ga_infos.name
                if dpt_payload is not None and ga_infos.transcoder is not None:
                    try:
                        value = ga_infos.transcoder.from_knx(dpt_payload)
                    except XKNXException:
                        bus_message["value"] = "Error decoding value"
                    else:
                        unit = (
                            f" {ga_infos.transcoder.unit}"
                            if ga_infos.transcoder.unit is not None
                            else ""
                        )
                        bus_message["value"] = f"{value}{unit}"
            if ia_infos := project.devices.get(src):
                bus_message[
                    "source_text"
                ] = f"{ia_infos['manufacturer_name']} {ia_infos['name']}"

        connection.send_event(
            msg["id"],
            bus_message,
        )

    connection.subscriptions[msg["id"]] = async_subscribe_telegrams(
        hass, forward_telegrams
    )

    connection.send_result(msg["id"])


def async_subscribe_telegrams(
    hass: HomeAssistant,
    telegram_callback: AsyncMessageCallbackType | MessageCallbackType,
) -> Callable[[], None]:
    """Subscribe to telegram received callback."""
    xknx = hass.data[DOMAIN].xknx

    unregister = xknx.telegram_queue.register_telegram_received_cb(
        telegram_callback, match_for_outgoing=True
    )

    def async_remove() -> None:
        """Remove callback."""
        xknx.telegram_queue.unregister_telegram_received_cb(unregister)

    return async_remove
