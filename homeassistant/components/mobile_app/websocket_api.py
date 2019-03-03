"""Websocket API for mobile_app."""
from aiohttp.http_websocket import WSMessage

from homeassistant.components.cloud import async_delete_cloudhook
from homeassistant.components.websocket_api import (ActiveConnection,
                                                    async_register_command,
                                                    async_response,
                                                    error_message,
                                                    result_message,
                                                    ws_require_user)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import HomeAssistantType

from .const import (ATTR_DELETED_IDS, ATTR_REGISTRATIONS, ATTR_STORE,
                    CONF_USER_ID, CONF_WEBHOOK_ID, DOMAIN,
                    SCHEMA_WS_DELETE_REGISTRATION, SCHEMA_WS_GET_REGISTRATION,
                    WS_TYPE_DELETE_REGISTRATION, WS_TYPE_GET_REGISTRATION)

from .helpers import safe_device, savable_state


def register_websocket_handlers(hass: HomeAssistantType) -> bool:
    """Register the websocket handlers."""
    async_register_command(hass, WS_TYPE_GET_REGISTRATION,
                           websocket_get_registration,
                           SCHEMA_WS_GET_REGISTRATION)

    async_register_command(hass, WS_TYPE_DELETE_REGISTRATION,
                           websocket_delete_registration,
                           SCHEMA_WS_DELETE_REGISTRATION)

    return True


@ws_require_user()
@async_response
async def websocket_get_registration(
        hass: HomeAssistantType, connection: ActiveConnection,
        msg: WSMessage) -> None:
    """Return the registration for the given webhook_id."""
    user = connection.user

    webhook_id = msg[CONF_WEBHOOK_ID]

    device = hass.data[DOMAIN][ATTR_REGISTRATIONS][webhook_id]

    if device[CONF_USER_ID] is not user.id and user.is_admin is False:
        return error_message(
            msg['id'], 'access_denied', 'User is not registration owner')

    connection.send_message(
        result_message(msg['id'], safe_device(device)))


@ws_require_user()
@async_response
async def websocket_delete_registration(hass: HomeAssistantType,
                                        connection: ActiveConnection,
                                        msg: WSMessage) -> None:
    """Delete the registration for the given webhook_id."""
    user = connection.user

    webhook_id = msg[CONF_WEBHOOK_ID]

    device = hass.data[DOMAIN][ATTR_REGISTRATIONS][webhook_id]

    if device[CONF_USER_ID] is not user.id and user.is_admin is False:
        return error_message(
            msg['id'], 'access_denied', 'User is not registration owner')

    del hass.data[DOMAIN][ATTR_REGISTRATIONS][webhook_id]

    hass.data[DOMAIN][ATTR_DELETED_IDS].append(webhook_id)

    store = hass.data[DOMAIN][ATTR_STORE]

    try:
        await store.async_save(savable_state(hass))
    except HomeAssistantError:
        return error_message(
            msg['id'], 'internal_error', 'Error deleting device')

    await async_delete_cloudhook(hass, webhook_id)

    connection.send_message(result_message(msg['id'], 'ok'))
