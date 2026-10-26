"""Websocekt API handlers for the hassio integration."""

import logging
from numbers import Number
import re
from typing import Any

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import CreateSessionOptions
import probatio

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

from .config_entry import async_get_hassio_entry, async_get_update_options
from .const import (
    ATTR_DATA,
    ATTR_ENDPOINT,
    ATTR_METHOD,
    ATTR_PARAMS,
    ATTR_SESSION,
    ATTR_SESSION_DATA_USER_ID,
    ATTR_SLUG,
    ATTR_TIMEOUT,
    ATTR_VERSION,
    ATTR_WS_EVENT,
    DATA_COMPONENT,
    EVENT_SUPERVISOR_EVENT,
    WS_ID,
    WS_TYPE,
    WS_TYPE_API,
    WS_TYPE_EVENT,
    WS_TYPE_INGRESS_INFO,
    WS_TYPE_INGRESS_SESSION,
    WS_TYPE_INGRESS_VALIDATE_SESSION,
    WS_TYPE_SUBSCRIBE,
)
from .coordinator import get_addons_list
from .exceptions import HassioNotReadyError
from .handler import HassioAPIError, get_supervisor_client
from .update_helper import update_addon, update_core

SCHEMA_WEBSOCKET_EVENT = probatio.Schema(
    {probatio.Required(ATTR_WS_EVENT): cv.string},
    extra=probatio.ALLOW_EXTRA,
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
def async_load_websocket_api(hass: HomeAssistant) -> None:
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, websocket_supervisor_event)
    websocket_api.async_register_command(hass, websocket_supervisor_api)
    websocket_api.async_register_command(hass, websocket_ingress_info)
    websocket_api.async_register_command(hass, websocket_ingress_session)
    websocket_api.async_register_command(hass, websocket_ingress_validate_session)
    websocket_api.async_register_command(hass, websocket_subscribe)
    websocket_api.async_register_command(hass, websocket_update_addon)
    websocket_api.async_register_command(hass, websocket_update_core)
    websocket_api.async_register_command(hass, websocket_update_config_info)
    websocket_api.async_register_command(hass, websocket_update_config_update)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required(WS_TYPE): WS_TYPE_SUBSCRIBE})
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
        probatio.Required(WS_TYPE): WS_TYPE_EVENT,
        probatio.Required(ATTR_DATA): SCHEMA_WEBSOCKET_EVENT,
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
        probatio.Required(WS_TYPE): WS_TYPE_API,
        probatio.Required(ATTR_ENDPOINT): cv.string,
        probatio.Required(ATTR_METHOD): cv.string,
        probatio.Optional(ATTR_DATA): dict,
        probatio.Optional(ATTR_PARAMS): dict,
        probatio.Optional(ATTR_TIMEOUT): probatio.Any(Number, None),
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
        # The frontend renews the ingress session when validation fails
        log = _LOGGER.debug if command == "/ingress/validate_session" else _LOGGER.error
        log("Failed to call %s - %s", command, err)
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


async def _async_check_ingress_access(
    hass: HomeAssistant, connection: ActiveConnection, slug: str
) -> None:
    """Raise Unauthorized if the user may not open the add-on's ingress panel."""
    if connection.user.is_admin:
        return
    panels = await get_supervisor_client(hass).ingress.panels()
    if (panel := panels.get(slug)) is None or panel.admin:
        raise Unauthorized


@websocket_api.websocket_command(
    {
        probatio.Required(WS_TYPE): WS_TYPE_INGRESS_INFO,
        probatio.Required(ATTR_SLUG): cv.string,
    }
)
@websocket_api.async_response
async def websocket_ingress_info(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the add-on details the ingress panel needs."""
    slug = msg[ATTR_SLUG]
    try:
        await _async_check_ingress_access(hass, connection, slug)
        addon = await get_supervisor_client(hass).addons.addon_info(slug)
    except SupervisorError as err:
        connection.send_error(
            msg[WS_ID], code=websocket_api.ERR_UNKNOWN_ERROR, message=str(err)
        )
        return
    connection.send_result(
        msg[WS_ID],
        {
            ATTR_NAME: addon.name,
            ATTR_SLUG: addon.slug,
            ATTR_VERSION: addon.version,
            "state": addon.state,
            "ingress_url": addon.ingress_url,
        },
    )


@websocket_api.websocket_command(
    {
        probatio.Required(WS_TYPE): WS_TYPE_INGRESS_SESSION,
        probatio.Required(ATTR_SLUG): cv.string,
    }
)
@websocket_api.async_response
async def websocket_ingress_session(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create an ingress session for the add-on."""
    client = get_supervisor_client(hass)
    try:
        await _async_check_ingress_access(hass, connection, msg[ATTR_SLUG])
        # Supervisor resolves the user's role from the ID and forwards the
        # identity to the add-on
        session = await client.ingress.create_session(
            CreateSessionOptions(user_id=connection.user.id)
        )
    except SupervisorError as err:
        connection.send_error(
            msg[WS_ID], code=websocket_api.ERR_UNKNOWN_ERROR, message=str(err)
        )
        return
    connection.send_result(msg[WS_ID], {ATTR_SESSION: session})


@websocket_api.websocket_command(
    {
        probatio.Required(WS_TYPE): WS_TYPE_INGRESS_VALIDATE_SESSION,
        probatio.Required(ATTR_SESSION): cv.string,
    }
)
@websocket_api.async_response
async def websocket_ingress_validate_session(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Validate and extend an ingress session."""
    try:
        await get_supervisor_client(hass).ingress.validate_session(msg[ATTR_SESSION])
    except SupervisorError as err:
        connection.send_error(
            msg[WS_ID], code=websocket_api.ERR_UNKNOWN_ERROR, message=str(err)
        )
        return
    connection.send_result(msg[WS_ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required(WS_TYPE): "hassio/update/addon",
        probatio.Required("addon"): str,
        probatio.Required("backup"): bool,
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
        probatio.Required(WS_TYPE): "hassio/update/core",
        probatio.Required("backup"): bool,
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
@websocket_api.websocket_command(
    {probatio.Required("type"): "hassio/update/config/info"}
)
def websocket_update_config_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send the stored backup config."""
    connection.send_result(msg["id"], async_get_update_options(hass))


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "hassio/update/config/update",
        probatio.Optional("add_on_backup_before_update"): bool,
        probatio.Optional("add_on_backup_retain_copies"): probatio.All(
            int, probatio.Range(min=1)
        ),
        probatio.Optional("core_backup_before_update"): bool,
    }
)
def websocket_update_config_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update the stored backup config."""
    entry = async_get_hassio_entry(hass)
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
            **entry.options,
            **async_get_update_options(hass, entry),
            **changes,
        },
    )
    connection.send_result(msg["id"])
