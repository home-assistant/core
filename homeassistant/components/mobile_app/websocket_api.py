"""Websocket API for mobile_app."""
import voluptuous as vol

from homeassistant.components.websocket_api import (ActiveConnection,
                                                    async_register_command,
                                                    async_response,
                                                    error_message,
                                                    result_message,
                                                    websocket_command,
                                                    ws_require_user)
from homeassistant.components.websocket_api.const import (ERR_INVALID_FORMAT,
                                                          ERR_UNAUTHORIZED)
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import (CONF_USER_ID, DATA_CONFIG_ENTRIES, DOMAIN)

from .helpers import delete_webhook, safe_registration


def register_websocket_handlers(hass: HomeAssistantType) -> bool:
    """Register the websocket handlers."""
    async_register_command(hass, websocket_get_user_registrations)

    async_register_command(hass, websocket_delete_registration)

    return True


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

    for config_entry in hass.config_entries.async_entries(domain=DOMAIN):
        registration = config_entry.data
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

    config_entry = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][webhook_id]

    if config_entry.data[CONF_USER_ID] != user.id and not user.is_admin:
        return error_message(
            msg['id'], ERR_UNAUTHORIZED, 'User is not registration owner')

    try:
        await delete_webhook(hass, config_entry)
    except HomeAssistantError:
        return error_message(
            msg['id'], 'internal_error', 'Error deleting registration')

    connection.send_message(result_message(msg['id'], 'ok'))
