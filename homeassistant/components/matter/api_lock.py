"""WebSocket API for Matter lock credential management."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import contextlib
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
from .helpers import (
    get_lock_endpoint_from_node,
    lock_supports_holiday_schedules,
    lock_supports_usr_feature,
    lock_supports_week_day_schedules,
    lock_supports_year_day_schedules,
)

_LOGGER = logging.getLogger(__name__)

ERROR_LOCK_NOT_FOUND = "lock_not_found"
ERROR_USR_NOT_SUPPORTED = "usr_not_supported"


class LockNotFound(Exception):
    """Exception raised when a lock endpoint is not found on a node."""


class UsrNotSupported(Exception):
    """Exception raised when lock does not support USR feature."""


# DoorLock Feature bitmap from Matter SDK
DoorLockFeature = clusters.DoorLock.Bitmaps.Feature

# User status mapping (Matter DoorLock UserStatusEnum)
USER_STATUS_MAP = {
    0: "available",
    1: "occupied_enabled",
    3: "occupied_disabled",
}
USER_STATUS_REVERSE_MAP = {v: k for k, v in USER_STATUS_MAP.items()}

# User type mapping (Matter DoorLock UserTypeEnum)
USER_TYPE_MAP = {
    0: "unrestricted_user",
    1: "year_day_schedule_user",
    2: "week_day_schedule_user",
    3: "programming_user",
    4: "non_access_user",
    5: "forced_user",
    6: "disposable_user",
    7: "expiring_user",
    8: "schedule_restricted_user",
    9: "remote_only_user",
}
USER_TYPE_REVERSE_MAP = {v: k for k, v in USER_TYPE_MAP.items()}

# Credential type mapping (Matter DoorLock CredentialTypeEnum)
CREDENTIAL_TYPE_MAP = {
    0: "programming_pin",
    1: "pin",
    2: "rfid",
    3: "fingerprint",
    4: "finger_vein",
    5: "face",
    6: "aliro_credential_issuer_key",
    7: "aliro_evictable_endpoint_key",
    8: "aliro_non_evictable_endpoint_key",
}
CREDENTIAL_TYPE_REVERSE_MAP = {v: k for k, v in CREDENTIAL_TYPE_MAP.items()}

# Credential rule mapping (Matter DoorLock CredentialRuleEnum)
CREDENTIAL_RULE_MAP = {
    0: "single",
    1: "dual",
    2: "tri",
}
CREDENTIAL_RULE_REVERSE_MAP = {v: k for k, v in CREDENTIAL_RULE_MAP.items()}

# SetCredential status codes (Matter DoorLock DlStatus enum)
SET_CREDENTIAL_STATUS_MAP = {
    0: "success",  # kSuccess
    1: "failure",  # kFailure
    2: "duplicate",  # kDuplicate - code already exists
    3: "occupied",  # kOccupied - slot in use
    133: "invalid_field",  # kInvalidField
    137: "resource_exhausted",  # kResourceExhausted - no slots
    139: "not_found",  # kNotFound
}


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
                msg[ID], ERROR_LOCK_NOT_FOUND, "No lock endpoint found on this device"
            )
        except UsrNotSupported:
            connection.send_error(
                msg[ID],
                ERROR_USR_NOT_SUPPORTED,
                "Lock does not support user/credential management",
            )

    return async_handle_lock_errors_func


def _get_supported_credential_types(feature_map: int) -> list[str]:
    """Get list of supported credential types from feature map."""
    types = []
    if feature_map & DoorLockFeature.kPinCredential:
        types.append("pin")
    if feature_map & DoorLockFeature.kRfidCredential:
        types.append("rfid")
    if feature_map & DoorLockFeature.kFingerCredentials:
        types.append("fingerprint")
    if feature_map & DoorLockFeature.kFaceCredentials:
        types.append("face")
    return types


def _get_attr(obj: Any, attr: str) -> Any:
    """Get attribute from object or dict."""
    if isinstance(obj, dict):
        return obj.get(attr)
    return getattr(obj, attr, None)


def _format_user_response(user_data: Any) -> dict[str, Any] | None:
    """Format GetUser response to API response format."""
    if user_data is None:
        return None

    # user_data can be a GetUserResponse cluster object or a dict
    user_status = _get_attr(user_data, "userStatus")
    if user_status is None:
        # User slot is empty
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
        "user_index": _get_attr(user_data, "userIndex"),
        "user_name": _get_attr(user_data, "userName"),
        "user_unique_id": _get_attr(user_data, "userUniqueID"),
        "user_status": USER_STATUS_MAP.get(user_status, "unknown"),
        "user_type": USER_TYPE_MAP.get(_get_attr(user_data, "userType"), "unknown"),
        "credential_rule": CREDENTIAL_RULE_MAP.get(
            _get_attr(user_data, "credentialRule"), "unknown"
        ),
        "credentials": credentials,
        "next_user_index": _get_attr(user_data, "nextUserIndex"),
    }


@callback
def async_register_lock_api(hass: HomeAssistant) -> None:
    """Register lock credential management API endpoints."""
    websocket_api.async_register_command(hass, websocket_get_lock_info)
    websocket_api.async_register_command(hass, websocket_add_lock_user)
    websocket_api.async_register_command(hass, websocket_update_lock_user)
    websocket_api.async_register_command(hass, websocket_set_lock_user)
    websocket_api.async_register_command(hass, websocket_get_lock_user)
    websocket_api.async_register_command(hass, websocket_get_lock_users)
    websocket_api.async_register_command(hass, websocket_clear_lock_user)
    websocket_api.async_register_command(hass, websocket_set_lock_credential)
    websocket_api.async_register_command(hass, websocket_get_lock_credential_status)
    websocket_api.async_register_command(hass, websocket_clear_lock_credential)


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
    _LOGGER.debug("get_lock_info called for node %s", node.node_id)
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        _LOGGER.debug("No lock endpoint found on node %s", node.node_id)
        raise LockNotFound

    _LOGGER.debug(
        "Found lock endpoint %s on node %s", lock_endpoint.endpoint_id, node.node_id
    )
    supports_usr = lock_supports_usr_feature(lock_endpoint)
    _LOGGER.debug("Lock USR feature support: %s", supports_usr)

    # Get feature map for credential type detection
    feature_map = (
        lock_endpoint.get_attribute_value(None, clusters.DoorLock.Attributes.FeatureMap)
        or 0
    )
    _LOGGER.debug(
        "Lock feature map: 0x%X (%d) - USR bit (0x100) is %s",
        feature_map,
        feature_map,
        "SET" if feature_map & 0x100 else "NOT SET",
    )

    # Get lock capabilities from attributes
    result: dict[str, Any] = {
        "supports_user_management": supports_usr,
        "supported_credential_types": _get_supported_credential_types(feature_map),
    }

    # Only include capacity info if USR feature is supported
    if supports_usr:
        result["max_users"] = lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfTotalUsersSupported
        )
        result["max_pin_users"] = lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfPINUsersSupported
        )
        result["max_rfid_users"] = lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfRFIDUsersSupported
        )
        result["max_credentials_per_user"] = lock_endpoint.get_attribute_value(
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

    # Schedule feature support and capacity
    result["supports_week_day_schedules"] = lock_supports_week_day_schedules(
        lock_endpoint
    )
    result["supports_year_day_schedules"] = lock_supports_year_day_schedules(
        lock_endpoint
    )
    result["supports_holiday_schedules"] = lock_supports_holiday_schedules(
        lock_endpoint
    )

    # Always include schedule capacity (0 if not supported)
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


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/add_user",
        vol.Required(DEVICE_ID): str,
        vol.Required("user_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("user_name"): vol.Any(str, None),
        vol.Optional("user_unique_id"): vol.Any(vol.Coerce(int), None),
        vol.Optional("user_type", default="unrestricted_user"): vol.In(
            USER_TYPE_REVERSE_MAP.keys()
        ),
        vol.Optional("credential_rule", default="single"): vol.In(
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
    """Add a new user to the lock."""
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    # First check if user slot is already occupied
    get_user_response = await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.GetUser(
            userIndex=msg["user_index"],
        ),
    )

    if _get_attr(get_user_response, "userStatus") is not None:
        connection.send_error(
            msg[ID],
            "user_already_exists",
            f"User slot {msg['user_index']} is already occupied",
        )
        return

    # Add the new user using SetUser with OperationType.Add (0)
    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.SetUser(
            operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
            userIndex=msg["user_index"],
            userName=msg.get("user_name"),
            userUniqueID=msg.get("user_unique_id"),
            userStatus=clusters.DoorLock.Enums.UserStatusEnum.kOccupiedEnabled,
            userType=USER_TYPE_REVERSE_MAP.get(
                msg.get("user_type", "unrestricted_user"), 0
            ),
            credentialRule=CREDENTIAL_RULE_REVERSE_MAP.get(
                msg.get("credential_rule", "single"), 0
            ),
        ),
        timed_request_timeout_ms=1000,
    )

    connection.send_result(msg[ID], {"user_index": msg["user_index"]})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/update_user",
        vol.Required(DEVICE_ID): str,
        vol.Required("user_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("user_name"): vol.Any(str, None),
        vol.Optional("user_unique_id"): vol.Any(vol.Coerce(int), None),
        vol.Optional("user_status"): vol.In(["occupied_enabled", "occupied_disabled"]),
        vol.Optional("user_type"): vol.In(USER_TYPE_REVERSE_MAP.keys()),
        vol.Optional("credential_rule"): vol.In(CREDENTIAL_RULE_REVERSE_MAP.keys()),
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

    # First check if user slot exists
    get_user_response = await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.GetUser(
            userIndex=msg["user_index"],
        ),
    )

    if _get_attr(get_user_response, "userStatus") is None:
        connection.send_error(
            msg[ID],
            "user_not_found",
            f"User slot {msg['user_index']} is empty",
        )
        return

    # Prepare update values - use existing values for fields not specified
    user_name = msg.get("user_name", _get_attr(get_user_response, "userName"))
    user_unique_id = msg.get(
        "user_unique_id", _get_attr(get_user_response, "userUniqueID")
    )

    user_status = _get_attr(get_user_response, "userStatus")
    if "user_status" in msg:
        user_status = USER_STATUS_REVERSE_MAP.get(msg["user_status"], user_status)

    user_type = _get_attr(get_user_response, "userType")
    if "user_type" in msg:
        user_type = USER_TYPE_REVERSE_MAP.get(msg["user_type"], user_type)

    credential_rule = _get_attr(get_user_response, "credentialRule")
    if "credential_rule" in msg:
        credential_rule = CREDENTIAL_RULE_REVERSE_MAP.get(
            msg["credential_rule"], credential_rule
        )

    # Update the user using SetUser with OperationType.Modify (1)
    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.SetUser(
            operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kModify,
            userIndex=msg["user_index"],
            userName=user_name,
            userUniqueID=user_unique_id,
            userStatus=user_status,
            userType=user_type,
            credentialRule=credential_rule,
        ),
        timed_request_timeout_ms=1000,
    )

    connection.send_result(msg[ID], {"user_index": msg["user_index"]})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/set_user",
        vol.Required(DEVICE_ID): str,
        vol.Optional("user_index"): vol.Any(
            vol.All(vol.Coerce(int), vol.Range(min=1)), None
        ),
        vol.Optional("user_name"): vol.Any(str, None),
        vol.Optional("user_unique_id"): vol.Any(vol.Coerce(int), None),
        vol.Optional("user_status", default="occupied_enabled"): vol.In(
            ["occupied_enabled", "occupied_disabled"]
        ),
        vol.Optional("user_type", default="unrestricted_user"): vol.In(
            USER_TYPE_REVERSE_MAP.keys()
        ),
        vol.Optional("credential_rule", default="single"): vol.In(
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
    """Add or update a user on the lock (frontend-compatible endpoint)."""
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    user_index = msg.get("user_index")

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
                "no_available_slots",
                "No available user slots on the lock",
            )
            return

        # Add the new user
        user_status_enum = (
            clusters.DoorLock.Enums.UserStatusEnum.kOccupiedEnabled
            if msg.get("user_status") == "occupied_enabled"
            else clusters.DoorLock.Enums.UserStatusEnum.kOccupiedDisabled
        )

        await matter.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.SetUser(
                operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
                userIndex=user_index,
                userName=msg.get("user_name"),
                userUniqueID=msg.get("user_unique_id"),
                userStatus=user_status_enum,
                userType=USER_TYPE_REVERSE_MAP.get(
                    msg.get("user_type", "unrestricted_user"), 0
                ),
                credentialRule=CREDENTIAL_RULE_REVERSE_MAP.get(
                    msg.get("credential_rule", "single"), 0
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
                "user_not_found",
                f"User slot {user_index} is empty",
            )
            return

        # Get existing values for fields not specified
        user_name = msg.get("user_name", _get_attr(get_user_response, "userName"))
        user_unique_id = msg.get(
            "user_unique_id", _get_attr(get_user_response, "userUniqueID")
        )

        user_status = _get_attr(get_user_response, "userStatus")
        if "user_status" in msg:
            user_status = USER_STATUS_REVERSE_MAP.get(msg["user_status"], user_status)

        user_type = _get_attr(get_user_response, "userType")
        if "user_type" in msg:
            user_type = USER_TYPE_REVERSE_MAP.get(msg["user_type"], user_type)

        credential_rule = _get_attr(get_user_response, "credentialRule")
        if "credential_rule" in msg:
            credential_rule = CREDENTIAL_RULE_REVERSE_MAP.get(
                msg["credential_rule"], credential_rule
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

    connection.send_result(msg[ID], {"user_index": user_index})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/get_user",
        vol.Required(DEVICE_ID): str,
        vol.Required("user_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
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
            userIndex=msg["user_index"],
        ),
    )

    result = _format_user_response(get_user_response)
    if result is None:
        connection.send_error(
            msg[ID],
            "user_not_found",
            f"User slot {msg['user_index']} is empty",
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
        vol.Required("user_index"): vol.All(
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
    """Clear a user from the lock (use index 0xFFFE to clear all users)."""
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.ClearUser(
            userIndex=msg["user_index"],
        ),
        timed_request_timeout_ms=1000,
    )

    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/set_credential",
        vol.Required(DEVICE_ID): str,
        vol.Required("credential_type"): vol.In(
            ["pin", "rfid", "fingerprint", "finger_vein", "face"]
        ),
        vol.Optional("credential_index"): vol.Any(
            vol.All(vol.Coerce(int), vol.Range(min=1)), None
        ),
        vol.Required("credential_data"): str,
        vol.Optional("user_index"): vol.Any(
            vol.All(vol.Coerce(int), vol.Range(min=1)), None
        ),
        vol.Optional("user_name"): vol.Any(str, None),
        vol.Optional("user_status", default="occupied_enabled"): vol.In(
            ["occupied_enabled", "occupied_disabled"]
        ),
        vol.Optional("user_type", default="unrestricted_user"): vol.In(
            USER_TYPE_REVERSE_MAP.keys()
        ),
    }
)
@websocket_api.async_response
@async_handle_lock_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_set_lock_credential(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Set a credential (PIN, RFID, etc.) for a user on the lock.

    If user_index is null, creates a new user first, then adds the credential.
    If credential_index is null, uses the next available slot.
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    credential_type_enum = CREDENTIAL_TYPE_REVERSE_MAP.get(msg["credential_type"], 1)
    user_index = msg.get("user_index")
    credential_index = msg.get("credential_index")
    create_new_user = user_index is None

    # Encode credential data as bytes
    credential_data = msg["credential_data"].encode("utf-8")

    # Check PIN length constraints
    min_pin = (
        lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.MinPINCodeLength
        )
        or 4
    )
    max_pin = (
        lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.MaxPINCodeLength
        )
        or 8
    )
    _LOGGER.debug("Lock PIN constraints: min=%s, max=%s", min_pin, max_pin)

    if msg["credential_type"] == "pin":
        if len(credential_data) < min_pin or len(credential_data) > max_pin:
            connection.send_error(
                msg[ID],
                "invalid_pin_length",
                f"PIN must be {min_pin}-{max_pin} digits, got {len(credential_data)}",
            )
            return

    # Get user type enum value
    user_type_str = msg.get("user_type", "unrestricted_user")
    user_type_enum = USER_TYPE_REVERSE_MAP.get(user_type_str, 0)

    # For schedule-based user types, create as unrestricted first
    # The schedule itself will restrict access - some locks don't support
    # setting schedule user types directly during creation
    create_user_type_enum = user_type_enum
    if user_type_str in (
        "week_day_schedule_user",
        "year_day_schedule_user",
        "schedule_restricted_user",
    ):
        create_user_type_enum = 0  # unrestricted_user
        _LOGGER.debug(
            "Using unrestricted_user for creation, schedule will restrict access"
        )

    # If no user_index provided, we need to create the user first
    # Some locks don't support auto-assign (userIndex=0) in SetCredential
    if create_new_user:
        max_users = (
            lock_endpoint.get_attribute_value(
                None, clusters.DoorLock.Attributes.NumberOfTotalUsersSupported
            )
            or 0
        )

        # Find first available user slot
        available_user_index = None
        for idx in range(1, max_users + 1):
            get_user_response = await matter.matter_client.send_device_command(
                node_id=node.node_id,
                endpoint_id=lock_endpoint.endpoint_id,
                command=clusters.DoorLock.Commands.GetUser(userIndex=idx),
            )
            if _get_attr(get_user_response, "userStatus") is None:
                available_user_index = idx
                break

        if available_user_index is None:
            connection.send_error(
                msg[ID],
                "no_available_slots",
                "No available user slots on the lock",
            )
            return

        user_index = available_user_index
        user_name = msg.get("user_name")

        _LOGGER.debug(
            "Creating new user at index %s with name '%s' and type %s (create as %s)",
            user_index,
            user_name,
            user_type_str,
            create_user_type_enum,
        )

        # Create the user first with SetUser
        await matter.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.SetUser(
                operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
                userIndex=user_index,
                userName=user_name,
                userUniqueID=None,
                userStatus=clusters.DoorLock.Enums.UserStatusEnum.kOccupiedEnabled,
                userType=create_user_type_enum,
                credentialRule=clusters.DoorLock.Enums.CredentialRuleEnum.kSingle,
            ),
            timed_request_timeout_ms=1000,
        )
        _LOGGER.debug("User created successfully at index %s", user_index)

    # Now find an available credential slot if not specified
    if credential_index is None:
        # Query credential status starting from index 1 to find next available
        # Use NumberOfPINUsersSupported as limit for PIN credential slots
        if credential_type_enum == 1:  # PIN type
            max_credential_slots = (
                lock_endpoint.get_attribute_value(
                    None, clusters.DoorLock.Attributes.NumberOfPINUsersSupported
                )
                or 20
            )
        else:
            max_credential_slots = 20  # Reasonable default for other types

        _LOGGER.debug(
            "Searching for available credential slot (max: %s)", max_credential_slots
        )

        for cred_idx in range(1, max_credential_slots + 1):
            check_credential = clusters.DoorLock.Structs.CredentialStruct(
                credentialType=credential_type_enum,
                credentialIndex=cred_idx,
            )
            status_response = await matter.matter_client.send_device_command(
                node_id=node.node_id,
                endpoint_id=lock_endpoint.endpoint_id,
                command=clusters.DoorLock.Commands.GetCredentialStatus(
                    credential=check_credential,
                ),
            )
            cred_exists = _get_attr(status_response, "credentialExists")
            _LOGGER.debug("Credential slot %s exists: %s", cred_idx, cred_exists)
            if not cred_exists:
                credential_index = cred_idx
                _LOGGER.debug("Found available credential slot: %s", cred_idx)
                break

        if credential_index is None:
            connection.send_error(
                msg[ID],
                "no_available_credential_slots",
                "No available credential slots on the lock",
            )
            return

    _LOGGER.debug(
        "SetCredential params: user_index=%s, credential_type=%s, credential_index=%s, "
        "credential_data_len=%s, user_type=%s",
        user_index,
        credential_type_enum,
        credential_index,
        len(credential_data),
        user_type_str,
    )

    # Create credential struct with the specific index
    credential = clusters.DoorLock.Structs.CredentialStruct(
        credentialType=credential_type_enum,
        credentialIndex=credential_index,
    )

    # Set the credential on the existing user
    set_response = await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.SetCredential(
            operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
            credential=credential,
            credentialData=credential_data,
            userIndex=user_index,
            userStatus=None,  # Not creating user, so these are ignored
            userType=None,
        ),
        timed_request_timeout_ms=1000,
    )

    # Debug: log the full response
    _LOGGER.debug(
        "SetCredential response: %s (type: %s)", set_response, type(set_response)
    )

    raw_status = _get_attr(set_response, "status")
    _LOGGER.debug(
        "SetCredential raw status: %s (type: %s)", raw_status, type(raw_status)
    )

    # Handle enum status values
    if hasattr(raw_status, "value"):
        raw_status = raw_status.value

    status = SET_CREDENTIAL_STATUS_MAP.get(raw_status, "unknown")
    _LOGGER.debug("SetCredential mapped status: %s", status)

    if status != "success":
        # If credential failed and we created a new user, clean it up
        if create_new_user:
            with contextlib.suppress(Exception):
                await matter.matter_client.send_device_command(
                    node_id=node.node_id,
                    endpoint_id=lock_endpoint.endpoint_id,
                    command=clusters.DoorLock.Commands.ClearUser(userIndex=user_index),
                    timed_request_timeout_ms=1000,
                )

        connection.send_error(
            msg[ID],
            f"set_credential_{status}",
            f"Failed to set credential: {status}",
        )
        return

    # Success
    connection.send_result(
        msg[ID],
        {
            "status": status,
            "user_index": user_index,
            "credential_index": credential_index,
            "next_credential_index": _get_attr(set_response, "nextCredentialIndex"),
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/get_credential_status",
        vol.Required(DEVICE_ID): str,
        vol.Required("credential_type"): vol.In(
            ["programming_pin", "pin", "rfid", "fingerprint", "finger_vein", "face"]
        ),
        vol.Required("credential_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)
@websocket_api.async_response
@async_handle_lock_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_get_lock_credential_status(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Get the status of a credential slot on the lock."""
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    credential_type = CREDENTIAL_TYPE_REVERSE_MAP.get(msg["credential_type"], 1)

    credential = clusters.DoorLock.Structs.CredentialStruct(
        credentialType=credential_type,
        credentialIndex=msg["credential_index"],
    )

    status_response = await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.GetCredentialStatus(
            credential=credential,
        ),
    )

    connection.send_result(
        msg[ID],
        {
            "credential_exists": _get_attr(status_response, "credentialExists"),
            "user_index": _get_attr(status_response, "userIndex"),
            "next_credential_index": _get_attr(status_response, "nextCredentialIndex"),
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/clear_credential",
        vol.Required(DEVICE_ID): str,
        vol.Optional("user_index"): vol.Any(
            vol.Coerce(int), None
        ),  # Accepted but not used
        vol.Required("credential_type"): vol.In(
            ["programming_pin", "pin", "rfid", "fingerprint", "finger_vein", "face"]
        ),
        vol.Required("credential_index"): vol.All(
            vol.Coerce(int), vol.Any(vol.Range(min=1), 0xFFFE)
        ),
    }
)
@websocket_api.async_response
@async_handle_lock_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_clear_lock_credential(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Clear a credential from the lock.

    Use index 0xFFFE to clear all credentials of the specified type.
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    credential_type = CREDENTIAL_TYPE_REVERSE_MAP.get(msg["credential_type"], 1)

    credential = clusters.DoorLock.Structs.CredentialStruct(
        credentialType=credential_type,
        credentialIndex=msg["credential_index"],
    )

    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.ClearCredential(
            credential=credential,
        ),
        timed_request_timeout_ms=1000,
    )

    connection.send_result(msg[ID])
