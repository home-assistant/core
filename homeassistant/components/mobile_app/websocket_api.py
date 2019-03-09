"""Websocket API for mobile_app."""
import voluptuous as vol

from homeassistant.components.cloud import async_delete_cloudhook
from homeassistant.components.websocket_api import (ActiveConnection,
                                                    async_register_command,
                                                    async_response,
                                                    error_message,
                                                    result_message,
                                                    websocket_command,
                                                    ws_require_user)
from homeassistant.components.websocket_api.const import (ERR_INVALID_FORMAT,
                                                          ERR_NOT_FOUND,
                                                          ERR_UNAUTHORIZED)
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import (CONF_CLOUDHOOK_URL, CONF_USER_ID, DATA_DELETED_IDS,
                    DATA_REGISTRATIONS, DATA_STORE, DOMAIN)

from .helpers import safe_registration, savable_state


def register_websocket_handlers(hass: HomeAssistantType) -> bool:
    """Register the websocket handlers."""
    async_register_command(hass, websocket_get_registration)

    async_register_command(hass, websocket_get_user_registrations)

    async_register_command(hass, websocket_delete_registration)

    return True


@ws_require_user()
@async_response
@websocket_command({
    vol.Required('type'): 'mobile_app/get_registration',
    vol.Required(CONF_WEBHOOK_ID): cv.string,
})
async def websocket_get_registration(
        hass: HomeAssistantType, connection: ActiveConnection,
        msg: dict) -> None:
    """Return the registration for the given webhook_id."""
    user = connection.user

    webhook_id = msg.get(CONF_WEBHOOK_ID)
    if webhook_id is None:
        connection.send_error(msg['id'], ERR_INVALID_FORMAT,
                              "Webhook ID not provided")
        return

    registration = hass.data[DOMAIN][DATA_REGISTRATIONS].get(webhook_id)

    if registration is None:
        connection.send_error(msg['id'], ERR_NOT_FOUND,
                              "Webhook ID not found in storage")
        return

    if registration[CONF_USER_ID] != user.id and not user.is_admin:
        return error_message(
            msg['id'], ERR_UNAUTHORIZED, 'User is not registration owner')

    connection.send_message(
        result_message(msg['id'], safe_registration(registration)))


@ws_require_user()
@async_response
@websocket_command({
    vol.Required('type'): 'mobile_app/get_user_registrations',
    vol.Optional(CONF_USER_ID): cv.string,
})
async def websocket_get_user_registrations(
        hass: HomeAssistantType, connection: ActiveConnection,
        msg: dict) -> None:
    """Return all registrations or just registrations for given user ID."""
    user_id = msg.get(CONF_USER_ID, connection.user.id)

    if user_id != connection.user.id and not connection.user.is_admin:
        # If user ID is provided and is not current user ID and current user
        # isn't an admin user
        connection.send_error(msg['id'], ERR_UNAUTHORIZED, "Unauthorized")
        return

    user_registrations = []

    for registration in hass.data[DOMAIN][DATA_REGISTRATIONS].values():
        if connection.user.is_admin or registration[CONF_USER_ID] is user_id:
            user_registrations.append(safe_registration(registration))

    connection.send_message(
        result_message(msg['id'], user_registrations))


@ws_require_user()
@async_response
@websocket_command({
    vol.Required('type'): 'mobile_app/delete_registration',
    vol.Required(CONF_WEBHOOK_ID): cv.string,
})
async def websocket_delete_registration(hass: HomeAssistantType,
                                        connection: ActiveConnection,
                                        msg: dict) -> None:
    """Delete the registration for the given webhook_id."""
    user = connection.user

    webhook_id = msg.get(CONF_WEBHOOK_ID)
    if webhook_id is None:
        connection.send_error(msg['id'], ERR_INVALID_FORMAT,
                              "Webhook ID not provided")
        return

    registration = hass.data[DOMAIN][DATA_REGISTRATIONS].get(webhook_id)

    if registration is None:
        connection.send_error(msg['id'], ERR_NOT_FOUND,
                              "Webhook ID not found in storage")
        return

    if registration[CONF_USER_ID] != user.id and not user.is_admin:
        return error_message(
            msg['id'], ERR_UNAUTHORIZED, 'User is not registration owner')

    del hass.data[DOMAIN][DATA_REGISTRATIONS][webhook_id]

    hass.data[DOMAIN][DATA_DELETED_IDS].append(webhook_id)

    store = hass.data[DOMAIN][DATA_STORE]

    try:
        await store.async_save(savable_state(hass))
    except HomeAssistantError:
        return error_message(
            msg['id'], 'internal_error', 'Error deleting registration')

    if (CONF_CLOUDHOOK_URL in registration and
            "cloud" in hass.config.components):
        await async_delete_cloudhook(hass, webhook_id)

    connection.send_message(result_message(msg['id'], 'ok'))
