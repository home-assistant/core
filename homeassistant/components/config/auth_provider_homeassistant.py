"""Offer API to configure the Home Assistant auth provider."""
import voluptuous as vol

from homeassistant.auth.providers import homeassistant as auth_ha
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import decorators


async def async_setup(hass):
    """Enable the Home Assistant views."""
    hass.components.websocket_api.async_register_command(websocket_create)
    hass.components.websocket_api.async_register_command(websocket_delete)
    hass.components.websocket_api.async_register_command(websocket_change_password)
    return True


def _get_provider(hass):
    """Get homeassistant auth provider."""
    for prv in hass.auth.auth_providers:
        if prv.type == "homeassistant":
            return prv

    raise RuntimeError("Provider not found")


@decorators.websocket_command(
    {
        vol.Required("type"): "config/auth_provider/homeassistant/create",
        vol.Required("user_id"): str,
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_create(hass, connection, msg):
    """Create credentials and attach to a user."""
    provider = _get_provider(hass)
    await provider.async_initialize()

    user = await hass.auth.async_get_user(msg["user_id"])

    if user is None:
        connection.send_message(
            websocket_api.error_message(msg["id"], "not_found", "User not found")
        )
        return

    if user.system_generated:
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                "system_generated",
                "Cannot add credentials to a system generated user.",
            )
        )
        return

    try:
        await hass.async_add_executor_job(
            provider.data.add_auth, msg["username"], msg["password"]
        )
    except auth_ha.InvalidUser:
        connection.send_message(
            websocket_api.error_message(
                msg["id"], "username_exists", "Username already exists"
            )
        )
        return

    credentials = await provider.async_get_or_create_credentials(
        {"username": msg["username"]}
    )
    await hass.auth.async_link_user(user, credentials)

    await provider.data.async_save()
    connection.send_message(websocket_api.result_message(msg["id"]))


@decorators.websocket_command(
    {
        vol.Required("type"): "config/auth_provider/homeassistant/delete",
        vol.Required("username"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_delete(hass, connection, msg):
    """Delete username and related credential."""
    provider = _get_provider(hass)
    await provider.async_initialize()

    credentials = await provider.async_get_or_create_credentials(
        {"username": msg["username"]}
    )

    # if not new, an existing credential exists.
    # Removing the credential will also remove the auth.
    if not credentials.is_new:
        await hass.auth.async_remove_credentials(credentials)

        connection.send_message(websocket_api.result_message(msg["id"]))
        return

    try:
        provider.data.async_remove_auth(msg["username"])
        await provider.data.async_save()
    except auth_ha.InvalidUser:
        connection.send_message(
            websocket_api.error_message(
                msg["id"], "auth_not_found", "Given username was not found."
            )
        )
        return

    connection.send_message(websocket_api.result_message(msg["id"]))


@decorators.websocket_command(
    {
        vol.Required("type"): "config/auth_provider/homeassistant/change_password",
        vol.Required("current_password"): str,
        vol.Required("new_password"): str,
    }
)
@websocket_api.async_response
async def websocket_change_password(hass, connection, msg):
    """Change current user password."""
    user = connection.user
    if user is None:
        connection.send_message(
            websocket_api.error_message(msg["id"], "user_not_found", "User not found")
        )
        return

    provider = _get_provider(hass)
    await provider.async_initialize()

    username = None
    for credential in user.credentials:
        if credential.auth_provider_type == provider.type:
            username = credential.data["username"]
            break

    if username is None:
        connection.send_message(
            websocket_api.error_message(
                msg["id"], "credentials_not_found", "Credentials not found"
            )
        )
        return

    try:
        await provider.async_validate_login(username, msg["current_password"])
    except auth_ha.InvalidAuth:
        connection.send_message(
            websocket_api.error_message(
                msg["id"], "invalid_password", "Invalid password"
            )
        )
        return

    await hass.async_add_executor_job(
        provider.data.change_password, username, msg["new_password"]
    )
    await provider.data.async_save()

    connection.send_message(websocket_api.result_message(msg["id"]))
