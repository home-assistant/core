"""Offer API to configure Home Assistant auth."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.auth.models import User
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

WS_TYPE_LIST = "config/auth/list"
SCHEMA_WS_LIST = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_LIST}
)

WS_TYPE_DELETE = "config/auth/delete"
SCHEMA_WS_DELETE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_DELETE, vol.Required("user_id"): str}
)


async def async_setup(hass: HomeAssistant) -> bool:
    """Enable the Home Assistant views."""
    websocket_api.async_register_command(
        hass, WS_TYPE_LIST, websocket_list, SCHEMA_WS_LIST
    )
    websocket_api.async_register_command(
        hass, WS_TYPE_DELETE, websocket_delete, SCHEMA_WS_DELETE
    )
    websocket_api.async_register_command(hass, websocket_create)
    websocket_api.async_register_command(hass, websocket_update)
    return True


@websocket_api.require_admin
@websocket_api.async_response
async def websocket_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return a list of users."""
    result = [_user_info(u) for u in await hass.auth.async_get_users()]

    connection.send_message(websocket_api.result_message(msg["id"], result))


@websocket_api.require_admin
@websocket_api.async_response
async def websocket_delete(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete a user."""
    if msg["user_id"] == connection.user.id:
        connection.send_message(
            websocket_api.error_message(
                msg["id"], "no_delete_self", "Unable to delete your own account"
            )
        )
        return

    if not (user := await hass.auth.async_get_user(msg["user_id"])):
        connection.send_message(
            websocket_api.error_message(msg["id"], "not_found", "User not found")
        )
        return

    await hass.auth.async_remove_user(user)

    connection.send_message(websocket_api.result_message(msg["id"]))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/auth/create",
        vol.Required("name"): str,
        vol.Optional("group_ids"): [str],
        vol.Optional("local_only"): bool,
    }
)
@websocket_api.async_response
async def websocket_create(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create a user."""
    user = await hass.auth.async_create_user(
        msg["name"], group_ids=msg.get("group_ids"), local_only=msg.get("local_only")
    )

    connection.send_message(
        websocket_api.result_message(msg["id"], {"user": _user_info(user)})
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/auth/update",
        vol.Required("user_id"): str,
        vol.Optional("name"): str,
        vol.Optional("is_active"): bool,
        vol.Optional("group_ids"): [str],
        vol.Optional("local_only"): bool,
    }
)
@websocket_api.async_response
async def websocket_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update a user."""
    if not (user := await hass.auth.async_get_user(msg.pop("user_id"))):
        connection.send_message(
            websocket_api.error_message(
                msg["id"], websocket_api.const.ERR_NOT_FOUND, "User not found"
            )
        )
        return

    if user.system_generated:
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                "cannot_modify_system_generated",
                "Unable to update system generated users.",
            )
        )
        return

    if user.is_owner and msg.get("is_active") is False:
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                "cannot_deactivate_owner",
                "Unable to deactivate owner.",
            )
        )
        return

    msg.pop("type")
    msg_id = msg.pop("id")

    await hass.auth.async_update_user(user, **msg)

    connection.send_message(
        websocket_api.result_message(msg_id, {"user": _user_info(user)})
    )


def _user_info(user: User) -> dict[str, Any]:
    """Format a user."""

    ha_username = next(
        (
            cred.data.get("username")
            for cred in user.credentials
            if cred.auth_provider_type == "homeassistant"
        ),
        None,
    )

    return {
        "id": user.id,
        "username": ha_username,
        "name": user.name,
        "is_owner": user.is_owner,
        "is_active": user.is_active,
        "local_only": user.local_only,
        "system_generated": user.system_generated,
        "group_ids": [group.id for group in user.groups],
        "credentials": [{"type": c.auth_provider_type} for c in user.credentials],
    }
