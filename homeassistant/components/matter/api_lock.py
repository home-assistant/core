"""WebSocket API for Matter lock credential management."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
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

ERROR_LOCK_NOT_FOUND = "lock_not_found"
ERROR_USR_NOT_SUPPORTED = "usr_not_supported"


class LockNotFound(Exception):
    """Exception raised when a lock endpoint is not found on a node."""


class UsrNotSupported(Exception):
    """Exception raised when lock does not support USR feature."""


# Feature bits for DoorLock FeatureMap (per Matter spec)
DOOR_LOCK_FEATURE_PIN = 0x1  # Bit 0 - PIN credential support
DOOR_LOCK_FEATURE_RFID = 0x2  # Bit 1 - RFID credential support
DOOR_LOCK_FEATURE_FINGER = 0x4  # Bit 2 - Fingerprint credential support
DOOR_LOCK_FEATURE_FACE = 0x40  # Bit 6 - Face credential support

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

# SetCredential status codes (Matter DoorLock SetCredentialResponse.status)
SET_CREDENTIAL_STATUS_MAP = {
    0: "success",
    1: "general_failure",
    2: "memory_full",
    3: "duplicate_code_error",
    4: "occupied",
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
    if feature_map & DOOR_LOCK_FEATURE_PIN:
        types.append("pin")
    if feature_map & DOOR_LOCK_FEATURE_RFID:
        types.append("rfid")
    if feature_map & DOOR_LOCK_FEATURE_FINGER:
        types.append("fingerprint")
    if feature_map & DOOR_LOCK_FEATURE_FACE:
        types.append("face")
    return types


def _format_user_response(user_data: Any) -> dict[str, Any] | None:
    """Format GetUser response to API response format."""
    if user_data is None:
        return None

    # user_data is a GetUserResponse cluster object
    if user_data.userStatus is None:
        # User slot is empty
        return None

    credentials = []
    if user_data.credentials:
        for cred in user_data.credentials:
            credentials.append({
                "type": CREDENTIAL_TYPE_MAP.get(cred.credentialType, "unknown"),
                "index": cred.credentialIndex,
            })

    return {
        "user_index": user_data.userIndex,
        "user_name": user_data.userName,
        "user_unique_id": user_data.userUniqueID,
        "user_status": USER_STATUS_MAP.get(user_data.userStatus, "unknown"),
        "user_type": USER_TYPE_MAP.get(user_data.userType, "unknown"),
        "credential_rule": CREDENTIAL_RULE_MAP.get(
            user_data.credentialRule, "unknown"
        ),
        "credentials": credentials,
        "next_user_index": user_data.nextUserIndex,
    }


@callback
def async_register_lock_api(hass: HomeAssistant) -> None:
    """Register lock credential management API endpoints."""
    websocket_api.async_register_command(hass, websocket_get_lock_info)
    websocket_api.async_register_command(hass, websocket_add_lock_user)
    websocket_api.async_register_command(hass, websocket_update_lock_user)
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
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    supports_usr = lock_supports_usr_feature(lock_endpoint)

    # Get feature map for credential type detection
    feature_map = lock_endpoint.get_attribute_value(
        None, clusters.DoorLock.Attributes.FeatureMap
    ) or 0

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

    # Include schedule capacity if respective features are supported
    if result["supports_week_day_schedules"]:
        result["max_week_day_schedules_per_user"] = lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfWeekDaySchedulesSupportedPerUser
        )

    if result["supports_year_day_schedules"]:
        result["max_year_day_schedules_per_user"] = lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfYearDaySchedulesSupportedPerUser
        )

    if result["supports_holiday_schedules"]:
        result["max_holiday_schedules"] = lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfHolidaySchedulesSupported
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

    if get_user_response.userStatus is not None:
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

    if get_user_response.userStatus is None:
        connection.send_error(
            msg[ID],
            "user_not_found",
            f"User slot {msg['user_index']} is empty",
        )
        return

    # Prepare update values - use existing values for fields not specified
    user_name = msg.get("user_name", get_user_response.userName)
    user_unique_id = msg.get("user_unique_id", get_user_response.userUniqueID)

    user_status = get_user_response.userStatus
    if "user_status" in msg:
        user_status = USER_STATUS_REVERSE_MAP.get(msg["user_status"], user_status)

    user_type = get_user_response.userType
    if "user_type" in msg:
        user_type = USER_TYPE_REVERSE_MAP.get(msg["user_type"], user_type)

    credential_rule = get_user_response.credentialRule
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

    max_users = lock_endpoint.get_attribute_value(
        None, clusters.DoorLock.Attributes.NumberOfTotalUsersSupported
    ) or 0

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
        next_index = get_user_response.nextUserIndex
        if next_index is None or next_index <= current_index:
            break
        current_index = next_index

    connection.send_result(
        msg[ID],
        {
            "users": users,
            "total_users": len(users),
            "max_users": max_users,
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
        vol.Required("credential_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required("credential_data"): str,
        vol.Required("user_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
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
    """Set a credential (PIN, RFID, etc.) for a user on the lock."""
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    credential_type = CREDENTIAL_TYPE_REVERSE_MAP.get(msg["credential_type"], 1)

    # Create credential struct
    credential = clusters.DoorLock.Structs.CredentialStruct(
        credentialType=credential_type,
        credentialIndex=msg["credential_index"],
    )

    # Encode credential data as bytes
    credential_data = msg["credential_data"].encode("utf-8")

    # Check if this is a new credential or modification
    status_response = await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.GetCredentialStatus(
            credential=credential,
        ),
    )

    operation_type = (
        clusters.DoorLock.Enums.DataOperationTypeEnum.kModify
        if status_response.credentialExists
        else clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd
    )

    # Set the credential
    set_response = await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.SetCredential(
            operationType=operation_type,
            credential=credential,
            credentialData=credential_data,
            userIndex=msg["user_index"],
            userStatus=USER_STATUS_REVERSE_MAP.get(
                msg.get("user_status", "occupied_enabled"), 1
            ),
            userType=USER_TYPE_REVERSE_MAP.get(
                msg.get("user_type", "unrestricted_user"), 0
            ),
        ),
        timed_request_timeout_ms=1000,
    )

    status = SET_CREDENTIAL_STATUS_MAP.get(set_response.status, "unknown")
    if status != "success":
        connection.send_error(
            msg[ID],
            f"set_credential_{status}",
            f"Failed to set credential: {status}",
        )
        return

    connection.send_result(
        msg[ID],
        {
            "status": status,
            "user_index": set_response.userIndex,
            "next_credential_index": set_response.nextCredentialIndex,
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
            "credential_exists": status_response.credentialExists,
            "user_index": status_response.userIndex,
            "next_credential_index": status_response.nextCredentialIndex,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/clear_credential",
        vol.Required(DEVICE_ID): str,
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
