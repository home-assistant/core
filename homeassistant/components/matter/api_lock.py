"""WebSocket API for Matter lock user management."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
import logging
from typing import Any, Concatenate

from chip.clusters import Objects as clusters
from matter_server.client import MatterClient
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
    ATTR_PIN_CODE,
    ATTR_SUPPORTS_USER_MGMT,
    ATTR_USER_INDEX,
    ATTR_USER_NAME,
    ATTR_USER_STATUS,
    ATTR_USER_TYPE,
    ATTR_USER_UNIQUE_ID,
    CLEAR_ALL_INDEX,
    CRED_TYPE_FACE,
    CRED_TYPE_FINGERPRINT,
    CRED_TYPE_PIN,
    CRED_TYPE_RFID,
    CREDENTIAL_RULE_MAP,
    CREDENTIAL_RULE_REVERSE_MAP,
    CREDENTIAL_TYPE_MAP,
    ERR_CREDENTIAL_NOT_SUPPORTED,
    ERR_INVALID_PIN_CODE,
    ERR_LOCK_NOT_FOUND,
    ERR_NO_AVAILABLE_CREDENTIAL_SLOTS,
    ERR_NO_AVAILABLE_SLOTS,
    ERR_USER_NOT_FOUND,
    ERR_USR_NOT_SUPPORTED,
    LOCK_TIMED_REQUEST_TIMEOUT_MS,
    SET_CREDENTIAL_STATUS_MAP,
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


# --- Private helpers for credential management ---


def _validate_pin_code(pin: str, min_len: int, max_len: int) -> str | None:
    """Validate a PIN code against lock constraints.

    Returns an error code string on failure, or None if valid.
    """
    if not pin.isdigit():
        return ERR_INVALID_PIN_CODE
    if len(pin) < min_len or len(pin) > max_len:
        return ERR_INVALID_PIN_CODE
    return None


async def _find_available_credential_slot(
    matter_client: MatterClient,
    node_id: int,
    endpoint_id: int,
    cred_type: int,
    max_slots: int,
) -> int | None:
    """Find the first available credential slot by iterating GetCredentialStatus.

    Returns the slot index, or None if all slots are occupied.
    """
    for idx in range(1, max_slots + 1):
        cred_status = await matter_client.send_device_command(
            node_id=node_id,
            endpoint_id=endpoint_id,
            command=clusters.DoorLock.Commands.GetCredentialStatus(
                credential=clusters.DoorLock.Structs.CredentialStruct(
                    credentialType=cred_type,
                    credentialIndex=idx,
                ),
            ),
        )
        if not _get_attr(cred_status, "credentialExists"):
            return idx
    return None


async def _set_credential_for_user(
    matter_client: MatterClient,
    node_id: int,
    endpoint_id: int,
    user_index: int,
    cred_type: int,
    cred_data: bytes,
    cred_index: int | None,
) -> dict[str, Any]:
    """Set a credential for a user.

    If cred_index is provided, modifies existing credential.
    Otherwise adds a new credential.

    Returns a dict with 'status' (str) and 'credential_index' (int|None).
    """
    if cred_index is not None:
        operation = clusters.DoorLock.Enums.DataOperationTypeEnum.kModify
        index = cred_index
    else:
        operation = clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd
        index = 0  # Lock assigns the index for kAdd when we don't know it

    # For kAdd we need to pass the actual slot index we found
    # For kModify we use the existing credential index
    response = await matter_client.send_device_command(
        node_id=node_id,
        endpoint_id=endpoint_id,
        command=clusters.DoorLock.Commands.SetCredential(
            operationType=operation,
            credential=clusters.DoorLock.Structs.CredentialStruct(
                credentialType=cred_type,
                credentialIndex=index,
            ),
            credentialData=cred_data,
            userIndex=user_index,
            userStatus=None,
            userType=None,
        ),
        timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
    )

    status_int = _get_attr(response, "status") or 0
    next_index = _get_attr(response, "nextCredentialIndex")
    return {
        "status": SET_CREDENTIAL_STATUS_MAP.get(status_int, "unknown"),
        "credential_index": next_index,
    }


async def _clear_user_credentials(
    matter_client: MatterClient,
    node_id: int,
    endpoint_id: int,
    user_index: int,
) -> None:
    """Clear all credentials for a specific user.

    Fetches the user to get credential list, then clears each credential.
    """
    get_user_response = await matter_client.send_device_command(
        node_id=node_id,
        endpoint_id=endpoint_id,
        command=clusters.DoorLock.Commands.GetUser(userIndex=user_index),
    )

    creds = _get_attr(get_user_response, "credentials")
    if not creds:
        return

    for cred in creds:
        cred_type = _get_attr(cred, "credentialType")
        cred_index = _get_attr(cred, "credentialIndex")
        await matter_client.send_device_command(
            node_id=node_id,
            endpoint_id=endpoint_id,
            command=clusters.DoorLock.Commands.ClearCredential(
                credential=clusters.DoorLock.Structs.CredentialStruct(
                    credentialType=cred_type,
                    credentialIndex=cred_index,
                ),
            ),
            timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
        )


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
    """Add or update a user on the lock with optional PIN credential.

    If user_index is null/omitted, finds the first available slot and creates a new user.
    If user_index is provided, updates the existing user at that index.

    pin_code behavior:
    - Omitted: leave PIN unchanged
    - str value: set/replace PIN (validated against lock min/max)
    - null: clear existing PIN
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    feature_map = (
        lock_endpoint.get_attribute_value(None, clusters.DoorLock.Attributes.FeatureMap)
        or 0
    )
    has_pin_feature = bool(feature_map & DoorLockFeature.kPinCredential)

    # Determine if we need to handle PIN credential
    pin_code_present = ATTR_PIN_CODE in msg
    pin_code = msg.get(ATTR_PIN_CODE) if pin_code_present else None

    # Validate PIN code if a non-null value was provided
    if pin_code_present and pin_code is not None:
        if not has_pin_feature:
            connection.send_error(
                msg[ID],
                ERR_CREDENTIAL_NOT_SUPPORTED,
                "Lock does not support PIN credentials",
            )
            return

        min_pin = (
            lock_endpoint.get_attribute_value(
                None, clusters.DoorLock.Attributes.MinPINCodeLength
            )
            or 0
        )
        max_pin = (
            lock_endpoint.get_attribute_value(
                None, clusters.DoorLock.Attributes.MaxPINCodeLength
            )
            or 0
        )
        pin_error = _validate_pin_code(pin_code, min_pin, max_pin)
        if pin_error is not None:
            connection.send_error(
                msg[ID],
                pin_error,
                f"PIN code must be {min_pin}-{max_pin} digits",
            )
            return

    user_index = msg.get(ATTR_USER_INDEX)
    is_new_user = False

    if user_index is None:
        # Adding new user - find first available slot
        is_new_user = True
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
            timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
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
            timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
        )

    # Handle PIN credential operations
    if pin_code_present:
        try:
            await _handle_pin_credential(
                matter.matter_client,
                node.node_id,
                lock_endpoint.endpoint_id,
                user_index,
                pin_code,
                has_pin_feature,
                lock_endpoint,
            )
        except _CredentialSlotError:
            if is_new_user:
                _LOGGER.debug(
                    "No credential slots for new user at index %s, rolling back",
                    user_index,
                )
                await matter.matter_client.send_device_command(
                    node_id=node.node_id,
                    endpoint_id=lock_endpoint.endpoint_id,
                    command=clusters.DoorLock.Commands.ClearUser(userIndex=user_index),
                    timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
                )
            connection.send_error(
                msg[ID],
                ERR_NO_AVAILABLE_CREDENTIAL_SLOTS,
                "No available credential slots on the lock",
            )
            return
        except _CredentialSetError:
            if is_new_user:
                _LOGGER.debug(
                    "SetCredential failed for new user at index %s, rolling back",
                    user_index,
                )
                await matter.matter_client.send_device_command(
                    node_id=node.node_id,
                    endpoint_id=lock_endpoint.endpoint_id,
                    command=clusters.DoorLock.Commands.ClearUser(userIndex=user_index),
                    timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
                )
            raise

    connection.send_result(msg[ID], {ATTR_USER_INDEX: user_index})


async def _handle_pin_credential(
    matter_client: MatterClient,
    node_id: int,
    endpoint_id: int,
    user_index: int,
    pin_code: str | None,
    has_pin_feature: bool,
    lock_endpoint: Any,
) -> None:
    """Handle PIN credential set/clear/replace for a user.

    Raises on failure so caller can roll back if needed.
    """
    pin_cred_type = clusters.DoorLock.Enums.CredentialTypeEnum.kPin

    if pin_code is None:
        # Clear existing PIN credentials for this user
        if not has_pin_feature:
            return
        await _clear_pin_credentials_for_user(
            matter_client, node_id, endpoint_id, user_index
        )
        return

    # Set or replace PIN
    # Check if user already has a PIN credential
    existing_cred_index = await _get_existing_pin_credential_index(
        matter_client, node_id, endpoint_id, user_index
    )

    if existing_cred_index is not None:
        # Modify existing credential
        await _set_credential_for_user(
            matter_client,
            node_id,
            endpoint_id,
            user_index,
            pin_cred_type,
            pin_code.encode(),
            existing_cred_index,
        )
    else:
        # Find available slot and add new credential
        max_pin_slots = (
            lock_endpoint.get_attribute_value(
                None, clusters.DoorLock.Attributes.NumberOfPINUsersSupported
            )
            or 0
        )
        slot = await _find_available_credential_slot(
            matter_client, node_id, endpoint_id, pin_cred_type, max_pin_slots
        )
        if slot is None:
            raise _CredentialSlotError

        result = await _set_credential_for_user(
            matter_client,
            node_id,
            endpoint_id,
            user_index,
            pin_cred_type,
            pin_code.encode(),
            slot,
        )
        if result["status"] != "success":
            raise _CredentialSetError(result["status"])


class _CredentialSlotError(Exception):
    """No available credential slots."""


class _CredentialSetError(Exception):
    """SetCredential command failed."""


async def _get_existing_pin_credential_index(
    matter_client: MatterClient,
    node_id: int,
    endpoint_id: int,
    user_index: int,
) -> int | None:
    """Get the credential index of an existing PIN credential for a user."""
    get_user_response = await matter_client.send_device_command(
        node_id=node_id,
        endpoint_id=endpoint_id,
        command=clusters.DoorLock.Commands.GetUser(userIndex=user_index),
    )
    creds = _get_attr(get_user_response, "credentials")
    if creds:
        pin_type = clusters.DoorLock.Enums.CredentialTypeEnum.kPin
        for cred in creds:
            if _get_attr(cred, "credentialType") == pin_type:
                index: int | None = _get_attr(cred, "credentialIndex")
                return index
    return None


async def _clear_pin_credentials_for_user(
    matter_client: MatterClient,
    node_id: int,
    endpoint_id: int,
    user_index: int,
) -> None:
    """Clear all PIN credentials for a specific user."""
    get_user_response = await matter_client.send_device_command(
        node_id=node_id,
        endpoint_id=endpoint_id,
        command=clusters.DoorLock.Commands.GetUser(userIndex=user_index),
    )
    creds = _get_attr(get_user_response, "credentials")
    if not creds:
        return
    pin_type = clusters.DoorLock.Enums.CredentialTypeEnum.kPin
    for cred in creds:
        if _get_attr(cred, "credentialType") == pin_type:
            cred_index = _get_attr(cred, "credentialIndex")
            await matter_client.send_device_command(
                node_id=node_id,
                endpoint_id=endpoint_id,
                command=clusters.DoorLock.Commands.ClearCredential(
                    credential=clusters.DoorLock.Structs.CredentialStruct(
                        credentialType=pin_type,
                        credentialIndex=cred_index,
                    ),
                ),
                timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
            )


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
    """Clear a user from the lock, cleaning up credentials first.

    Use index 0xFFFE (CLEAR_ALL_INDEX) to clear all users.
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrNotSupported

    user_index = msg[ATTR_USER_INDEX]

    if user_index == CLEAR_ALL_INDEX:
        # Clear all: clear all credentials first, then all users
        await matter.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.ClearCredential(
                credential=None,
            ),
            timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
        )
    else:
        # Clear credentials for this specific user before deleting them
        await _clear_user_credentials(
            matter.matter_client,
            node.node_id,
            lock_endpoint.endpoint_id,
            user_index,
        )

    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.ClearUser(
            userIndex=user_index,
        ),
        timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
    )

    connection.send_result(msg[ID])
