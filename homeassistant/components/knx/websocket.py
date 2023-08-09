"""KNX Websocket API."""
from __future__ import annotations

from typing import TYPE_CHECKING, Final

import knx_frontend as knx_panel
import voluptuous as vol
from xknxproject.exceptions import XknxProjectException

from homeassistant.components import panel_custom, websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
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
        hass.http.register_static_path(
            URL_BASE,
            path=knx_panel.locate_dir(),
            cache_headers=knx_panel.is_prod_build,
        )
        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=DOMAIN,
            webcomponent_name=knx_panel.webcomponent_name,
            sidebar_title=DOMAIN.upper(),
            sidebar_icon="mdi:bus-electric",
            module_url=f"{URL_BASE}/{knx_panel.entrypoint_js}",
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
    recent_telegrams = [*knx.telegrams.recent_telegrams]
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
            telegram,
        )

    connection.subscriptions[msg["id"]] = knx.telegrams.async_listen_telegram(
        action=forward_telegram,
        name="KNX GroupMonitor subscription",
    )
    connection.send_result(msg["id"])
