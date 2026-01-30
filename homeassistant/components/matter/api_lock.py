"""WebSocket API for Matter lock user management."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
import logging
from typing import Any, Concatenate

from matter_server.client.models.node import MatterNode
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback

from .adapter import MatterAdapter
from .api_base import (
    DEVICE_ID,
    ID,
    TYPE,
    async_get_matter_adapter,
    async_get_node,
    async_handle_failed_command,
)
from .const import (
    ATTR_CREDENTIAL_RULE,
    ATTR_PIN_CODE,
    ATTR_USER_INDEX,
    ATTR_USER_NAME,
    ATTR_USER_STATUS,
    ATTR_USER_TYPE,
    ATTR_USER_UNIQUE_ID,
    CLEAR_ALL_INDEX,
    CREDENTIAL_RULE_REVERSE_MAP,
    ERR_CREDENTIAL_NOT_SUPPORTED,
    ERR_INVALID_PIN_CODE,
    ERR_LOCK_NOT_FOUND,
    ERR_NO_AVAILABLE_CREDENTIAL_SLOTS,
    ERR_NO_AVAILABLE_SLOTS,
    ERR_USER_NOT_FOUND,
    ERR_USR_NOT_SUPPORTED,
    USER_TYPE_REVERSE_MAP,
)
from .helpers_lock import (
    CredentialSlotError,
    InvalidPinCodeError,
    LockEndpointNotFoundError,
    NoAvailableUserSlotsError,
    PinCredentialNotSupportedError,
    UserSlotEmptyError,
    UsrFeatureNotSupportedError,
    clear_lock_user as helpers_clear_lock_user,
    get_lock_info as helpers_get_lock_info,
    get_lock_users as helpers_get_lock_users,
    set_lock_user as helpers_set_lock_user,
)

_LOGGER = logging.getLogger(__name__)


def async_handle_lock_errors[**_P](
    func: Callable[
        Concatenate[HomeAssistant, ActiveConnection, dict[str, Any], _P],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    Concatenate[HomeAssistant, ActiveConnection, dict[str, Any], _P],
    Coroutine[Any, Any, None],
]:
    """Decorate function to handle lock-specific errors."""

    @wraps(func)
    async def async_handle_lock_errors_func(
        hass: HomeAssistant,
        connection: ActiveConnection,
        msg: dict[str, Any],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        """Handle lock-specific errors."""
        try:
            await func(hass, connection, msg, *args, **kwargs)
        except LockEndpointNotFoundError:
            connection.send_error(
                msg[ID], ERR_LOCK_NOT_FOUND, "No lock endpoint found on this device"
            )
        except UsrFeatureNotSupportedError:
            connection.send_error(
                msg[ID],
                ERR_USR_NOT_SUPPORTED,
                "Lock does not support user/credential management",
            )
        except NoAvailableUserSlotsError:
            connection.send_error(
                msg[ID],
                ERR_NO_AVAILABLE_SLOTS,
                "No available user slots on the lock",
            )
        except UserSlotEmptyError as err:
            connection.send_error(msg[ID], ERR_USER_NOT_FOUND, str(err))
        except InvalidPinCodeError as err:
            connection.send_error(msg[ID], ERR_INVALID_PIN_CODE, str(err))
        except PinCredentialNotSupportedError:
            connection.send_error(
                msg[ID],
                ERR_CREDENTIAL_NOT_SUPPORTED,
                "Lock does not support PIN credentials",
            )
        except CredentialSlotError:
            connection.send_error(
                msg[ID],
                ERR_NO_AVAILABLE_CREDENTIAL_SLOTS,
                "No available credential slots on the lock",
            )

    return async_handle_lock_errors_func


@callback
def async_register_lock_api(hass: HomeAssistant) -> None:
    """Register lock user management API endpoints."""
    websocket_api.async_register_command(hass, websocket_get_lock_info)
    websocket_api.async_register_command(hass, websocket_set_lock_user)
    websocket_api.async_register_command(hass, websocket_get_lock_users)
    websocket_api.async_register_command(hass, websocket_clear_lock_user)


# --- Lock information ---


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/get_lock_info",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_handle_lock_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_get_lock_info(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Get lock capabilities and configuration info."""
    result = await helpers_get_lock_info(matter.matter_client, node)
    connection.send_result(msg[ID], result)


# --- User CRUD operations ---


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/set_user",
        vol.Required(DEVICE_ID): str,
        vol.Optional(ATTR_USER_INDEX): vol.Any(
            vol.All(vol.Coerce(int), vol.Range(min=1)), None
        ),
        vol.Optional(ATTR_USER_NAME): vol.Any(str, None),
        vol.Optional(ATTR_USER_UNIQUE_ID): vol.Any(vol.Coerce(int), None),
        vol.Optional(ATTR_USER_STATUS, default="occupied_enabled"): vol.In(
            ["occupied_enabled", "occupied_disabled"]
        ),
        vol.Optional(ATTR_USER_TYPE, default="unrestricted_user"): vol.In(
            USER_TYPE_REVERSE_MAP.keys()
        ),
        vol.Optional(ATTR_CREDENTIAL_RULE, default="single"): vol.In(
            CREDENTIAL_RULE_REVERSE_MAP.keys()
        ),
        vol.Optional(ATTR_PIN_CODE): vol.Any(str, None),
    }
)
@websocket_api.async_response
@async_handle_lock_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_set_lock_user(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Add or update a user on the lock with optional PIN credential."""
    result = await helpers_set_lock_user(
        matter.matter_client,
        node,
        user_index=msg.get(ATTR_USER_INDEX),
        user_name=msg.get(ATTR_USER_NAME),
        user_unique_id=msg.get(ATTR_USER_UNIQUE_ID),
        user_status=msg.get(ATTR_USER_STATUS, "occupied_enabled"),
        user_type=msg.get(ATTR_USER_TYPE, "unrestricted_user"),
        credential_rule=msg.get(ATTR_CREDENTIAL_RULE, "single"),
        pin_code=msg.get(ATTR_PIN_CODE),
        pin_code_present=ATTR_PIN_CODE in msg,
    )
    connection.send_result(msg[ID], result)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/get_users",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_handle_lock_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_get_lock_users(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Get all users from the lock."""
    result = await helpers_get_lock_users(matter.matter_client, node)
    connection.send_result(msg[ID], result)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/clear_user",
        vol.Required(DEVICE_ID): str,
        vol.Required(ATTR_USER_INDEX): vol.All(
            vol.Coerce(int), vol.Any(vol.Range(min=1), CLEAR_ALL_INDEX)
        ),
    }
)
@websocket_api.async_response
@async_handle_lock_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_clear_lock_user(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Clear a user from the lock, cleaning up credentials first."""
    await helpers_clear_lock_user(matter.matter_client, node, msg[ATTR_USER_INDEX])
    connection.send_result(msg[ID])
