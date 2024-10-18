"""Offer API to configure the Home Assistant auth provider."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.auth.providers import webauthn as auth_webauthn
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback


@callback
def async_setup(hass: HomeAssistant) -> bool:
    """Enable the Home Assistant views."""
    websocket_api.async_register_command(hass, websocket_list)
    websocket_api.async_register_command(hass, websocket_register)
    websocket_api.async_register_command(hass, websocket_delete)
    websocket_api.async_register_command(hass, websocket_register_verify)
    websocket_api.async_register_command(hass, websocket_rename)
    return True


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/auth_provider/passkey/list",
    }
)
@websocket_api.async_response
async def websocket_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create credentials and attach to a user."""
    provider = auth_webauthn.async_get_provider(hass)
    passkeys = await provider.async_list_passkeys(connection.user)

    connection.send_result(msg["id"], passkeys)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/auth_provider/passkey/register",
    }
)
@websocket_api.async_response
async def websocket_register(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create credentials and attach to a user."""
    provider = auth_webauthn.async_get_provider(hass)
    options = await provider.async_generate_registration_options(connection.user)

    connection.send_result(msg["id"], options)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/auth_provider/passkey/register_verify",
        vol.Required("credential"): object,
    },
)
@websocket_api.async_response
async def websocket_register_verify(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create credentials and attach to a user."""
    provider = auth_webauthn.async_get_provider(hass)
    try:
        result = await provider.async_add_auth(connection.user, msg["credential"])
        connection.send_result(
            msg["id"],
            {
                "result": result,
            },
        )
    except auth_webauthn.InvalidAuth as err:
        connection.send_error(msg["id"], "invalid_auth", str(err))
    except auth_webauthn.InvalidUser as err:
        connection.send_error(msg["id"], "invalid_user", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/auth_provider/passkey/rename",
        vol.Required("credential_id"): str,
        vol.Required("name"): str,
    },
)
@websocket_api.async_response
async def websocket_rename(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create credentials and attach to a user."""
    provider = auth_webauthn.async_get_provider(hass)
    try:
        await provider.async_update_passkey(
            connection.user, msg["credential_id"], msg["name"]
        )
        connection.send_result(msg["id"])
    except auth_webauthn.CredentialsNotFound as err:
        connection.send_error(msg["id"], "credential_not_found", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/auth_provider/passkey/delete",
        vol.Required("credential_id"): str,
    },
)
@websocket_api.async_response
async def websocket_delete(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create credentials and attach to a user."""
    provider = auth_webauthn.async_get_provider(hass)
    try:
        await provider.async_delete_passkey(connection.user, msg["credential_id"])
        connection.send_result(msg["id"])
    except auth_webauthn.CredentialsNotFound as err:
        connection.send_error(msg["id"], "credential_not_found", str(err))
