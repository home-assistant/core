"""Websocekt API handlers for the hassio integration."""

import logging
from numbers import Number
import re
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from . import HassioAPIError
from .config import HassioUpdateParametersDict
from .const import (
    ATTR_DATA,
    ATTR_ENDPOINT,
    ATTR_METHOD,
    ATTR_SESSION_DATA_USER_ID,
    ATTR_SLUG,
    ATTR_TIMEOUT,
    ATTR_VERSION,
    ATTR_WS_EVENT,
    DATA_COMPONENT,
    DATA_CONFIG_STORE,
    EVENT_SUPERVISOR_EVENT,
    WS_ID,
    WS_TYPE,
    WS_TYPE_API,
    WS_TYPE_EVENT,
    WS_TYPE_SUBSCRIBE,
)
from .coordinator import get_supervisor_info
from .update_helper import update_addon, update_core

SCHEMA_WEBSOCKET_EVENT = vol.Schema(
    {vol.Required(ATTR_WS_EVENT): cv.string},
    extra=vol.ALLOW_EXTRA,
)

# Endpoints needed for ingress can't require admin because addons can set `panel_admin: false`
# fmt: off
WS_NO_ADMIN_ENDPOINTS = re.compile(
    r"^(?:"
    r"|/ingress/(session|validate_session)"
    r"|/addons/[^/]+/info"
    r")$"
)
# fmt: on

_LOGGER: logging.Logger = logging.getLogger(__package__)


@callback
def async_load_websocket_api(hass: HomeAssistant) -> None:
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, websocket_supervisor_event)
    websocket_api.async_register_command(hass, websocket_supervisor_api)
    websocket_api.async_register_command(hass, websocket_subscribe)
    websocket_api.async_register_command(hass, websocket_update_addon)
    websocket_api.async_register_command(hass, websocket_update_core)
    websocket_api.async_register_command(hass, websocket_update_config_info)
    websocket_api.async_register_command(hass, websocket_update_config_update)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required(WS_TYPE): WS_TYPE_SUBSCRIBE})
def websocket_subscribe(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Subscribe to supervisor events."""

    @callback
    def forward_messages(data: dict[str, str]) -> None:
        """Forward events to websocket."""
        connection.send_message(websocket_api.event_message(msg[WS_ID], data))

    connection.subscriptions[msg[WS_ID]] = async_dispatcher_connect(
        hass, EVENT_SUPERVISOR_EVENT, forward_messages
    )
    connection.send_message(websocket_api.result_message(msg[WS_ID]))


@callback
@websocket_api.websocket_command(
    {
        vol.Required(WS_TYPE): WS_TYPE_EVENT,
        vol.Required(ATTR_DATA): SCHEMA_WEBSOCKET_EVENT,
    }
)
def websocket_supervisor_event(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Publish events from the Supervisor."""
    connection.send_result(msg[WS_ID])
    async_dispatcher_send(hass, EVENT_SUPERVISOR_EVENT, msg[ATTR_DATA])


@websocket_api.websocket_command(
    {
        vol.Required(WS_TYPE): WS_TYPE_API,
        vol.Required(ATTR_ENDPOINT): cv.string,
        vol.Required(ATTR_METHOD): cv.string,
        vol.Optional(ATTR_DATA): dict,
        vol.Optional(ATTR_TIMEOUT): vol.Any(Number, None),
    }
)
@websocket_api.async_response
async def websocket_supervisor_api(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Websocket handler to call Supervisor API."""
    if not connection.user.is_admin and not WS_NO_ADMIN_ENDPOINTS.match(
        msg[ATTR_ENDPOINT]
    ):
        raise Unauthorized
    supervisor = hass.data[DATA_COMPONENT]

    command = msg[ATTR_ENDPOINT]
    payload = msg.get(ATTR_DATA, {})

    if command == "/ingress/session":
        # Send user ID on session creation, so the supervisor can correlate session tokens with users
        # for every request that is authenticated with the given ingress session token.
        payload[ATTR_SESSION_DATA_USER_ID] = connection.user.id

    try:
        result = await supervisor.send_command(
            command,
            method=msg[ATTR_METHOD],
            timeout=msg.get(ATTR_TIMEOUT, 10),
            payload=payload,
            source="core.websocket_api",
        )
    except HassioAPIError as err:
        _LOGGER.error("Failed to to call %s - %s", msg[ATTR_ENDPOINT], err)
        connection.send_error(
            msg[WS_ID], code=websocket_api.ERR_UNKNOWN_ERROR, message=str(err)
        )
    else:
        connection.send_result(msg[WS_ID], result.get(ATTR_DATA, {}))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(WS_TYPE): "hassio/update/addon",
        vol.Required("addon"): str,
        vol.Required("backup"): bool,
    }
)
@websocket_api.async_response
async def websocket_update_addon(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Websocket handler to update an addon."""
    addon_name: str | None = None
    addon_version: str | None = None
    addons: list = (get_supervisor_info(hass) or {}).get("addons", [])
    for addon in addons:
        if addon[ATTR_SLUG] == msg["addon"]:
            addon_name = addon[ATTR_NAME]
            addon_version = addon[ATTR_VERSION]
            break
    await update_addon(hass, msg["addon"], msg["backup"], addon_name, addon_version)
    connection.send_result(msg[WS_ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(WS_TYPE): "hassio/update/core",
        vol.Required("backup"): bool,
    }
)
@websocket_api.async_response
async def websocket_update_core(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Websocket handler to update Home Assistant Core."""
    await update_core(hass, None, msg["backup"])
    connection.send_result(msg[WS_ID])


@callback
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "hassio/update/config/info"})
def websocket_update_config_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send the stored backup config."""
    connection.send_result(
        msg["id"], hass.data[DATA_CONFIG_STORE].data.update_config.to_dict()
    )


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "hassio/update/config/update",
        vol.Optional("add_on_backup_before_update"): bool,
        vol.Optional("add_on_backup_retain_copies"): vol.All(int, vol.Range(min=1)),
        vol.Optional("core_backup_before_update"): bool,
    }
)
def websocket_update_config_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update the stored backup config."""
    changes = dict(msg)
    changes.pop("id")
    changes.pop("type")
    hass.data[DATA_CONFIG_STORE].update(
        update_config=cast(HassioUpdateParametersDict, changes)
    )
    connection.send_result(msg["id"])
