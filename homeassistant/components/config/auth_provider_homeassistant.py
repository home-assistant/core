"""Offer API to configure the Home Assistant auth provider."""
import voluptuous as vol

from homeassistant.auth.providers import homeassistant as auth_ha
from homeassistant.core import callback
from homeassistant.components import websocket_api


WS_TYPE_CREATE = 'config/auth_provider/homeassistant/create'
SCHEMA_WS_CREATE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_CREATE,
    vol.Required('user_id'): str,
    vol.Required('username'): str,
    vol.Required('password'): str,
})

WS_TYPE_DELETE = 'config/auth_provider/homeassistant/delete'
SCHEMA_WS_DELETE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_DELETE,
    vol.Required('username'): str,
})

WS_TYPE_CHANGE_PASSWORD = 'config/auth_provider/homeassistant/change_password'
SCHEMA_WS_CHANGE_PASSWORD = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_CHANGE_PASSWORD,
    vol.Required('current_password'): str,
    vol.Required('new_password'): str
})


async def async_setup(hass):
    """Enable the Home Assistant views."""
    hass.components.websocket_api.async_register_command(
        WS_TYPE_CREATE, websocket_create,
        SCHEMA_WS_CREATE
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_DELETE, websocket_delete,
        SCHEMA_WS_DELETE
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_CHANGE_PASSWORD, websocket_change_password,
        SCHEMA_WS_CHANGE_PASSWORD
    )
    return True


def _get_provider(hass):
    """Get homeassistant auth provider."""
    for prv in hass.auth.auth_providers:
        if prv.type == 'homeassistant':
            return prv

    raise RuntimeError('Provider not found')


@callback
@websocket_api.require_owner
def websocket_create(hass, connection, msg):
    """Create credentials and attach to a user."""
    async def create_creds():
        """Create credentials."""
        provider = _get_provider(hass)
        await provider.async_initialize()

        user = await hass.auth.async_get_user(msg['user_id'])

        if user is None:
            connection.send_message_outside(websocket_api.error_message(
                msg['id'], 'not_found', 'User not found'))
            return

        if user.system_generated:
            connection.send_message_outside(websocket_api.error_message(
                msg['id'], 'system_generated',
                'Cannot add credentials to a system generated user.'))
            return

        try:
            await hass.async_add_executor_job(
                provider.data.add_auth, msg['username'], msg['password'])
        except auth_ha.InvalidUser:
            connection.send_message_outside(websocket_api.error_message(
                msg['id'], 'username_exists', 'Username already exists'))
            return

        credentials = await provider.async_get_or_create_credentials({
            'username': msg['username']
        })
        await hass.auth.async_link_user(user, credentials)

        await provider.data.async_save()
        connection.to_write.put_nowait(websocket_api.result_message(msg['id']))

    hass.async_add_job(create_creds())


@callback
@websocket_api.require_owner
def websocket_delete(hass, connection, msg):
    """Delete username and related credential."""
    async def delete_creds():
        """Delete user credentials."""
        provider = _get_provider(hass)
        await provider.async_initialize()

        credentials = await provider.async_get_or_create_credentials({
            'username': msg['username']
        })

        # if not new, an existing credential exists.
        # Removing the credential will also remove the auth.
        if not credentials.is_new:
            await hass.auth.async_remove_credentials(credentials)

            connection.to_write.put_nowait(
                websocket_api.result_message(msg['id']))
            return

        try:
            provider.data.async_remove_auth(msg['username'])
            await provider.data.async_save()
        except auth_ha.InvalidUser:
            connection.to_write.put_nowait(websocket_api.error_message(
                msg['id'], 'auth_not_found', 'Given username was not found.'))
            return

        connection.to_write.put_nowait(
            websocket_api.result_message(msg['id']))

    hass.async_add_job(delete_creds())


@callback
def websocket_change_password(hass, connection, msg):
    """Change user password."""
    async def change_password():
        """Change user password."""
        user = connection.request.get('hass_user')
        if user is None:
            connection.send_message_outside(websocket_api.error_message(
                msg['id'], 'user_not_found', 'User not found'))
            return

        provider = _get_provider(hass)
        await provider.async_initialize()

        username = None
        for credential in user.credentials:
            if credential.auth_provider_type == provider.type:
                username = credential.data['username']
                break

        if username is None:
            connection.send_message_outside(websocket_api.error_message(
                msg['id'], 'credentials_not_found', 'Credentials not found'))
            return

        try:
            await provider.async_validate_login(
                username, msg['current_password'])
        except auth_ha.InvalidAuth:
            connection.send_message_outside(websocket_api.error_message(
                msg['id'], 'invalid_password', 'Invalid password'))
            return

        await hass.async_add_executor_job(
            provider.data.change_password, username, msg['new_password'])
        await provider.data.async_save()

        connection.send_message_outside(
            websocket_api.result_message(msg['id']))

    hass.async_add_job(change_password())
