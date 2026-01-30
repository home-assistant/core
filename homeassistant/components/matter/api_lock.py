"""WebSocket API for Matter lock user management."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
import logging
from typing import Any, Concatenate

from chip.clusters import Objects as clusters
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
    ATTR_MAX_CREDENTIALS_PER_USER,
    ATTR_MAX_PIN_USERS,
    ATTR_MAX_RFID_USERS,
    ATTR_MAX_USERS,
    ATTR_SUPPORTS_USER_MGMT,
    ATTR_USER_INDEX,
    ATTR_USER_NAME,
    ATTR_USER_STATUS,
    ATTR_USER_TYPE,
    ATTR_USER_UNIQUE_ID,
    CRED_TYPE_FACE,
    CRED_TYPE_FINGERPRINT,
    CRED_TYPE_PIN,
    CRED_TYPE_RFID,
    CREDENTIAL_RULE_MAP,
    CREDENTIAL_RULE_REVERSE_MAP,
    CREDENTIAL_TYPE_MAP,
    ERR_LOCK_NOT_FOUND,
    ERR_NO_AVAILABLE_SLOTS,
    ERR_USER_ALREADY_EXISTS,
    ERR_USER_NOT_FOUND,
    ERR_USR_NOT_SUPPORTED,
    USER_STATUS_MAP,
    USER_STATUS_REVERSE_MAP,
    USER_TYPE_MAP,
    USER_TYPE_REVERSE_MAP,
)
from .helpers_lock import (
    DoorLockFeature,
    get_lock_endpoint_from_node,
    lock_supports_holiday_schedules,
    lock_supports_usr_feature,
    lock_supports_week_day_schedules,
    lock_supports_year_day_schedules,
)

_LOGGER = logging.getLogger(__name__)


class LockNotFound(Exception):
    """Exception raised when a lock endpoint is not found on a node."""


class UsrNotSupported(Exception):
    """Exception raised when lock does not support USR feature."""


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
        except LockNotFound:
            connection.send_error(
                msg[ID], ERR_LOCK_NOT_FOUND, "No lock endpoint found on this device"
            )
        except UsrNotSupported:
            connection.send_error(
                msg[ID],
                ERR_USR_NOT_SUPPORTED,
                "Lock does not support user/credential management",
            )

    return async_handle_lock_errors_func


def _get_supported_credential_types(feature_map: int) -> list[str]:
    """Get list of supported credential types from feature map."""
    types = []
    if feature_map & DoorLockFeature.kPinCredential:
        types.append(CRED_TYPE_PIN)
    if feature_map & DoorLockFeature.kRfidCredential:
        types.append(CRED_TYPE_RFID)
    if feature_map & DoorLockFeature.kFingerCredentials:
        types.append(CRED_TYPE_FINGERPRINT)
    if feature_map & DoorLockFeature.kFaceCredentials:
        types.append(CRED_TYPE_FACE)
    return types


def _get_attr(obj: Any, attr: str) -> Any:
    """Get attribute from object or dict.

    Matter SDK responses can be either dataclass objects or dicts depending on
    the SDK version and serialization context.
    """
    if isinstance(obj, dict):
        return obj.get(attr)
    return getattr(obj, attr, None)


def _format_user_response(user_data: Any) -> dict[str, Any] | None:
    """Format GetUser response to API response format.

    Returns None if the user slot is empty (no userStatus).
    """
    if user_data is None:
        return None

    user_status = _get_attr(user_data, "userStatus")
    if user_status is None:
        return None

    credentials = []
    creds = _get_attr(user_data, "credentials")
    if creds:
        for cred in creds:
            cred_type = _get_attr(cred, "credentialType")
            cred_index = _get_attr(cred, "credentialIndex")
            credentials.append(
                {
                    "type": CREDENTIAL_TYPE_MAP.get(cred_type, "unknown"),
                    "index": cred_index,
                }
            )

    return {
        ATTR_USER_INDEX: _get_attr(user_data, "userIndex"),
        ATTR_USER_NAME: _get_attr(user_data, "userName"),
        ATTR_USER_UNIQUE_ID: _get_attr(user_data, "userUniqueID"),
        ATTR_USER_STATUS: USER_STATUS_MAP.get(user_status, "unknown"),
        ATTR_USER_TYPE: USER_TYPE_MAP.get(_get_attr(user_data, "userType"), "unknown"),
        ATTR_CREDENTIAL_RULE: CREDENTIAL_RULE_MAP.get(
            _get_attr(user_data, "credentialRule"), "unknown"
        ),
        "credentials": credentials,
        "next_user_index": _get_attr(user_data, "nextUserIndex"),
    }


@callback
def async_register_lock_api(hass: HomeAssistant) -> None:
    """Register lock user management API endpoints."""
    websocket_api.async_register_command(hass, websocket_get_lock_info)
    websocket_api.async_register_command(hass, websocket_add_lock_user)
    websocket_api.async_register_command(hass, websocket_update_lock_user)
    websocket_api.async_register_command(hass, websocket_set_lock_user)
    websocket_api.async_register_command(hass, websocket_get_lock_user)
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
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    supports_usr = lock_supports_usr_feature(lock_endpoint)

    # Get feature map for credential type detection
    feature_map = (
        lock_endpoint.get_attribute_value(None, clusters.DoorLock.Attributes.FeatureMap)
        or 0
    )

    result: dict[str, Any] = {
        ATTR_SUPPORTS_USER_MGMT: supports_usr,
        "supported_credential_types": _get_supported_credential_types(feature_map),
    }

    # Only include capacity info if USR feature is supported
    if supports_usr:
        result[ATTR_MAX_USERS] = lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfTotalUsersSupported
        )
        result[ATTR_MAX_PIN_USERS] = lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfPINUsersSupported
        )
        result[ATTR_MAX_RFID_USERS] = lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfRFIDUsersSupported
        )
        result[ATTR_MAX_CREDENTIALS_PER_USER] = lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfCredentialsSupportedPerUser
        )
        result["min_pin_length"] = lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.MinPINCodeLength
        )
        result["max_pin_length"] = lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.MaxPINCodeLength
        )
        result["min_rfid_length"] = lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.MinRFIDCodeLength
        )
        result["max_rfid_length"] = lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.MaxRFIDCodeLength
        )

    # Schedule feature support and capacity (informational)
    result["supports_week_day_schedules"] = lock_supports_week_day_schedules(
        lock_endpoint
    )
    result["supports_year_day_schedules"] = lock_supports_year_day_schedules(
        lock_endpoint
    )
    result["supports_holiday_schedules"] = lock_supports_holiday_schedules(
        lock_endpoint
    )

    result["max_week_day_schedules_per_user"] = (
        lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfWeekDaySchedulesSupportedPerUser
        )
        if result["supports_week_day_schedules"]
        else 0
    )
    result["max_year_day_schedules_per_user"] = (
        lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfYearDaySchedulesSupportedPerUser
        )
        if result["supports_year_day_schedules"]
        else 0
    )
    result["max_holiday_schedules"] = (
        lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfHolidaySchedulesSupported
        )
        if result["supports_holiday_schedules"]
        else 0
    )

    connection.send_result(msg[ID], result)


# --- User CRUD operations ---


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/add_user",
        vol.Required(DEVICE_ID): str,
        vol.Required(ATTR_USER_INDEX): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(ATTR_USER_NAME): vol.Any(str, None),
        vol.Optional(ATTR_USER_UNIQUE_ID): vol.Any(vol.Coerce(int), None),
        vol.Optional(ATTR_USER_TYPE, default="unrestricted_user"): vol.In(
            USER_TYPE_REVERSE_MAP.keys()
        ),
        vol.Optional(ATTR_CREDENTIAL_RULE, default="single"): vol.In(
            CREDENTIAL_RULE_REVERSE_MAP.keys()
        ),
    }
)
@websocket_api.async_response
@async_handle_lock_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_add_lock_user(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Add a new user to the lock at a specific index."""
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    # Check if user slot is already occupied
    get_user_response = await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.GetUser(
            userIndex=msg[ATTR_USER_INDEX],
        ),
    )

    if _get_attr(get_user_response, "userStatus") is not None:
        connection.send_error(
            msg[ID],
            ERR_USER_ALREADY_EXISTS,
            f"User slot {msg[ATTR_USER_INDEX]} is already occupied",
        )
        return

    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.SetUser(
            operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
            userIndex=msg[ATTR_USER_INDEX],
            userName=msg.get(ATTR_USER_NAME),
            userUniqueID=msg.get(ATTR_USER_UNIQUE_ID),
            userStatus=clusters.DoorLock.Enums.UserStatusEnum.kOccupiedEnabled,
            userType=USER_TYPE_REVERSE_MAP.get(
                msg.get(ATTR_USER_TYPE, "unrestricted_user"), 0
            ),
            credentialRule=CREDENTIAL_RULE_REVERSE_MAP.get(
                msg.get(ATTR_CREDENTIAL_RULE, "single"), 0
            ),
        ),
        timed_request_timeout_ms=1000,
    )

    connection.send_result(msg[ID], {ATTR_USER_INDEX: msg[ATTR_USER_INDEX]})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/update_user",
        vol.Required(DEVICE_ID): str,
        vol.Required(ATTR_USER_INDEX): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(ATTR_USER_NAME): vol.Any(str, None),
        vol.Optional(ATTR_USER_UNIQUE_ID): vol.Any(vol.Coerce(int), None),
        vol.Optional(ATTR_USER_STATUS): vol.In(
            ["occupied_enabled", "occupied_disabled"]
        ),
        vol.Optional(ATTR_USER_TYPE): vol.In(USER_TYPE_REVERSE_MAP.keys()),
        vol.Optional(ATTR_CREDENTIAL_RULE): vol.In(CREDENTIAL_RULE_REVERSE_MAP.keys()),
    }
)
@websocket_api.async_response
@async_handle_lock_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_update_lock_user(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Update an existing user on the lock."""
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    get_user_response = await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.GetUser(
            userIndex=msg[ATTR_USER_INDEX],
        ),
    )

    if _get_attr(get_user_response, "userStatus") is None:
        connection.send_error(
            msg[ID],
            ERR_USER_NOT_FOUND,
            f"User slot {msg[ATTR_USER_INDEX]} is empty",
        )
        return

    # Preserve existing values for fields not specified in the update
    user_name = msg.get(ATTR_USER_NAME, _get_attr(get_user_response, "userName"))
    user_unique_id = msg.get(
        ATTR_USER_UNIQUE_ID, _get_attr(get_user_response, "userUniqueID")
    )

    user_status = _get_attr(get_user_response, "userStatus")
    if ATTR_USER_STATUS in msg:
        user_status = USER_STATUS_REVERSE_MAP.get(msg[ATTR_USER_STATUS], user_status)

    user_type = _get_attr(get_user_response, "userType")
    if ATTR_USER_TYPE in msg:
        user_type = USER_TYPE_REVERSE_MAP.get(msg[ATTR_USER_TYPE], user_type)

    credential_rule = _get_attr(get_user_response, "credentialRule")
    if ATTR_CREDENTIAL_RULE in msg:
        credential_rule = CREDENTIAL_RULE_REVERSE_MAP.get(
            msg[ATTR_CREDENTIAL_RULE], credential_rule
        )

    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.SetUser(
            operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kModify,
            userIndex=msg[ATTR_USER_INDEX],
            userName=user_name,
            userUniqueID=user_unique_id,
            userStatus=user_status,
            userType=user_type,
            credentialRule=credential_rule,
        ),
        timed_request_timeout_ms=1000,
    )

    connection.send_result(msg[ID], {ATTR_USER_INDEX: msg[ATTR_USER_INDEX]})


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
    """Add or update a user on the lock.

    If user_index is null, finds the first available slot and creates a new user.
    If user_index is provided, updates the existing user at that index.
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    user_index = msg.get(ATTR_USER_INDEX)

    if user_index is None:
        # Adding new user - find first available slot
        max_users = (
            lock_endpoint.get_attribute_value(
                None, clusters.DoorLock.Attributes.NumberOfTotalUsersSupported
            )
            or 0
        )

        for idx in range(1, max_users + 1):
            get_user_response = await matter.matter_client.send_device_command(
                node_id=node.node_id,
                endpoint_id=lock_endpoint.endpoint_id,
                command=clusters.DoorLock.Commands.GetUser(userIndex=idx),
            )
            if _get_attr(get_user_response, "userStatus") is None:
                user_index = idx
                break

        if user_index is None:
            connection.send_error(
                msg[ID],
                ERR_NO_AVAILABLE_SLOTS,
                "No available user slots on the lock",
            )
            return

        user_status_enum = (
            clusters.DoorLock.Enums.UserStatusEnum.kOccupiedEnabled
            if msg.get(ATTR_USER_STATUS) == "occupied_enabled"
            else clusters.DoorLock.Enums.UserStatusEnum.kOccupiedDisabled
        )

        await matter.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.SetUser(
                operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
                userIndex=user_index,
                userName=msg.get(ATTR_USER_NAME),
                userUniqueID=msg.get(ATTR_USER_UNIQUE_ID),
                userStatus=user_status_enum,
                userType=USER_TYPE_REVERSE_MAP.get(
                    msg.get(ATTR_USER_TYPE, "unrestricted_user"), 0
                ),
                credentialRule=CREDENTIAL_RULE_REVERSE_MAP.get(
                    msg.get(ATTR_CREDENTIAL_RULE, "single"), 0
                ),
            ),
            timed_request_timeout_ms=1000,
        )
    else:
        # Updating existing user
        get_user_response = await matter.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.GetUser(userIndex=user_index),
        )

        if _get_attr(get_user_response, "userStatus") is None:
            connection.send_error(
                msg[ID],
                ERR_USER_NOT_FOUND,
                f"User slot {user_index} is empty",
            )
            return

        user_name = msg.get(ATTR_USER_NAME, _get_attr(get_user_response, "userName"))
        user_unique_id = msg.get(
            ATTR_USER_UNIQUE_ID, _get_attr(get_user_response, "userUniqueID")
        )

        user_status = _get_attr(get_user_response, "userStatus")
        if ATTR_USER_STATUS in msg:
            user_status = USER_STATUS_REVERSE_MAP.get(
                msg[ATTR_USER_STATUS], user_status
            )

        user_type = _get_attr(get_user_response, "userType")
        if ATTR_USER_TYPE in msg:
            user_type = USER_TYPE_REVERSE_MAP.get(msg[ATTR_USER_TYPE], user_type)

        credential_rule = _get_attr(get_user_response, "credentialRule")
        if ATTR_CREDENTIAL_RULE in msg:
            credential_rule = CREDENTIAL_RULE_REVERSE_MAP.get(
                msg[ATTR_CREDENTIAL_RULE], credential_rule
            )

        await matter.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.SetUser(
                operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kModify,
                userIndex=user_index,
                userName=user_name,
                userUniqueID=user_unique_id,
                userStatus=user_status,
                userType=user_type,
                credentialRule=credential_rule,
            ),
            timed_request_timeout_ms=1000,
        )

    connection.send_result(msg[ID], {ATTR_USER_INDEX: user_index})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/get_user",
        vol.Required(DEVICE_ID): str,
        vol.Required(ATTR_USER_INDEX): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)
@websocket_api.async_response
@async_handle_lock_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_get_lock_user(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Get a single user from the lock."""
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    get_user_response = await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.GetUser(
            userIndex=msg[ATTR_USER_INDEX],
        ),
    )

    result = _format_user_response(get_user_response)
    if result is None:
        connection.send_error(
            msg[ID],
            ERR_USER_NOT_FOUND,
            f"User slot {msg[ATTR_USER_INDEX]} is empty",
        )
        return

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
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    max_users = (
        lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfTotalUsersSupported
        )
        or 0
    )

    users: list[dict[str, Any]] = []
    current_index = 1

    # Iterate through users using next_user_index for efficiency
    while current_index is not None and current_index <= max_users:
        get_user_response = await matter.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.GetUser(
                userIndex=current_index,
            ),
        )

        user_data = _format_user_response(get_user_response)
        if user_data is not None:
            users.append(user_data)

        # Move to next user index
        next_index = _get_attr(get_user_response, "nextUserIndex")
        if next_index is None or next_index <= current_index:
            break
        current_index = next_index

    connection.send_result(
        msg[ID],
        {
            "total_users": len(users),
            "max_users": max_users,
            "users": users,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/clear_user",
        vol.Required(DEVICE_ID): str,
        vol.Required(ATTR_USER_INDEX): vol.All(
            vol.Coerce(int), vol.Any(vol.Range(min=1), 0xFFFE)
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
    """Clear a user from the lock.

    Use index 0xFFFE to clear all users.
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.ClearUser(
            userIndex=msg[ATTR_USER_INDEX],
        ),
        timed_request_timeout_ms=1000,
    )

    connection.send_result(msg[ID])
