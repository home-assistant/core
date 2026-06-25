"""Websocekt API handlers for the hassio integration."""

import logging
from numbers import Number
import re
from typing import Any

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

from .const import (
    ATTR_DATA,
    ATTR_ENDPOINT,
    ATTR_METHOD,
    ATTR_PARAMS,
    ATTR_SESSION_DATA_USER_ID,
    ATTR_SLUG,
    ATTR_TIMEOUT,
    ATTR_VERSION,
    ATTR_WS_EVENT,
    DATA_COMPONENT,
    DEFAULT_UPDATE_OPTIONS,
    DOMAIN,
    EVENT_SUPERVISOR_EVENT,
    OPTION_ADD_ON_BACKUP_BEFORE_UPDATE,
    OPTION_ADD_ON_BACKUP_RETAIN_COPIES,
    OPTION_CORE_BACKUP_BEFORE_UPDATE,
    WS_ID,
    WS_TYPE,
    WS_TYPE_API,
    WS_TYPE_EVENT,
    WS_TYPE_SUBSCRIBE,
)
from .coordinator import get_addons_list
from .exceptions import HassioNotReadyError
from .handler import HassioAPIError
from .update_helper import update_addon, update_core

SCHEMA_WEBSOCKET_EVENT = vol.Schema(
    {vol.Required(ATTR_WS_EVENT): cv.string},
    extra=vol.ALLOW_EXTRA,
)

# Endpoints needed for ingress can't require admin because
# add-ons can set `panel_admin: false`
RE_ADDONS_INFO_ENDPOINT = r"/addons/[^/]+/info"
WS_ADDONS_INFO_ENDPOINT = re.compile(r"^" + RE_ADDONS_INFO_ENDPOINT + r"$")
WS_NO_ADMIN_ENDPOINTS = re.compile(
    r"^(?:"
    r"/ingress/(session|validate_session)"
    f"|{RE_ADDONS_INFO_ENDPOINT}"
    r")$"
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


@callback
def _async_get_hassio_entry(hass: HomeAssistant):
    """Return the active hassio config entry if it exists."""
    entries = hass.config_entries.async_entries(
        DOMAIN, include_ignore=False, include_disabled=False
    )
    return entries[0] if entries else None


@callback
def _async_get_update_options(hass: HomeAssistant) -> dict[str, bool | int]:
    """Return hassio update config with defaults."""
    if (entry := _async_get_hassio_entry(hass)) is None:
        return dict(DEFAULT_UPDATE_OPTIONS)

    return {
        OPTION_ADD_ON_BACKUP_BEFORE_UPDATE: entry.options.get(
            OPTION_ADD_ON_BACKUP_BEFORE_UPDATE,
            DEFAULT_UPDATE_OPTIONS[OPTION_ADD_ON_BACKUP_BEFORE_UPDATE],
        ),
        OPTION_ADD_ON_BACKUP_RETAIN_COPIES: entry.options.get(
            OPTION_ADD_ON_BACKUP_RETAIN_COPIES,
            DEFAULT_UPDATE_OPTIONS[OPTION_ADD_ON_BACKUP_RETAIN_COPIES],
        ),
        OPTION_CORE_BACKUP_BEFORE_UPDATE: entry.options.get(
            OPTION_CORE_BACKUP_BEFORE_UPDATE,
            DEFAULT_UPDATE_OPTIONS[OPTION_CORE_BACKUP_BEFORE_UPDATE],
        ),
    }


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
@websocket_api.ws_require_user(only_supervisor=True)
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
        vol.Optional(ATTR_PARAMS): dict,
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
        # Send user ID on session creation, so the supervisor can
        # correlate session tokens with users for every request that
        # is authenticated with the given ingress session token.
        payload[ATTR_SESSION_DATA_USER_ID] = connection.user.id

    try:
        result = await supervisor.send_command(
            command,
            method=msg[ATTR_METHOD],
            timeout=msg.get(ATTR_TIMEOUT, 10),
            payload=payload,
            source="core.websocket_api",
            params=msg.get(ATTR_PARAMS),
        )
    except HassioAPIError as err:
        _LOGGER.error("Failed to to call %s - %s", msg[ATTR_ENDPOINT], err)
        connection.send_error(
            msg[WS_ID], code=websocket_api.ERR_UNKNOWN_ERROR, message=str(err)
        )
    else:
        data = result.get(ATTR_DATA, {})
        # Remove options from add-on info for non-admin users, as options can contain
        # sensitive information and the frontend does not require it for ingress.
        if not connection.user.is_admin and WS_ADDONS_INFO_ENDPOINT.match(command):
            data.pop("options", None)
        connection.send_result(msg[WS_ID], data)


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
    try:
        addons_list: list[dict[str, Any]] = get_addons_list(hass)
    except HassioNotReadyError:
        _LOGGER.error(
            "Update command received for app %s but apps list is not available",
            msg["addon"],
        )
        connection.send_error(
            msg[WS_ID],
            code=websocket_api.ERR_UNKNOWN_ERROR,
            message="Apps list is not available",
        )
        return

    for addon in addons_list:
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
    connection.send_result(msg["id"], _async_get_update_options(hass))


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
    entry = _async_get_hassio_entry(hass)
    if entry is None:
        connection.send_error(
            msg["id"],
            code=websocket_api.ERR_UNKNOWN_ERROR,
            message="Hassio config entry is not available",
        )
        return

    changes = dict(msg)
    changes.pop("id")
    changes.pop("type")
    hass.config_entries.async_update_entry(
        entry,
        options={
            **_async_get_update_options(hass),
            **changes,
        },
    )
    connection.send_result(msg["id"])
