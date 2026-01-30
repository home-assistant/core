"""Lock-specific helpers for the Matter integration.

Provides DoorLock cluster endpoint resolution, feature detection, and
business logic for lock user/credential management. These are separated
from the general Matter helpers (helpers.py) to maintain single
responsibility — general helpers handle node/device resolution while
this module handles lock-specific concerns.

All business logic functions accept MatterClient + MatterNode (or raw IDs)
and have no dependency on websocket or entity interfaces.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

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
    CLEAR_ALL_INDEX,
    CRED_TYPE_FACE,
    CRED_TYPE_FINGERPRINT,
    CRED_TYPE_PIN,
    CRED_TYPE_RFID,
    CREDENTIAL_RULE_MAP,
    CREDENTIAL_RULE_REVERSE_MAP,
    CREDENTIAL_TYPE_MAP,
    ERR_INVALID_PIN_CODE,
    LOCK_TIMED_REQUEST_TIMEOUT_MS,
    SET_CREDENTIAL_STATUS_MAP,
    USER_STATUS_MAP,
    USER_STATUS_REVERSE_MAP,
    USER_TYPE_MAP,
    USER_TYPE_REVERSE_MAP,
)

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint, MatterNode

_LOGGER = logging.getLogger(__name__)

# DoorLock Feature bitmap from Matter SDK
DoorLockFeature = clusters.DoorLock.Bitmaps.Feature


@callback
def get_lock_endpoint_from_node(node: MatterNode) -> MatterEndpoint | None:
    """Get the DoorLock endpoint from a node.

    Returns the first endpoint that has the DoorLock cluster, or None if not found.
    """
    for endpoint in node.endpoints.values():
        if endpoint.has_cluster(clusters.DoorLock):
            return endpoint
    return None


def _get_feature_map(endpoint: MatterEndpoint) -> int | None:
    """Read the DoorLock FeatureMap attribute from an endpoint."""
    value: int | None = endpoint.get_attribute_value(
        None, clusters.DoorLock.Attributes.FeatureMap
    )
    return value


@callback
def lock_supports_usr_feature(endpoint: MatterEndpoint) -> bool:
    """Check if lock endpoint supports USR (User) feature.

    The USR feature indicates the lock supports user and credential management
    commands like SetUser, GetUser, SetCredential, etc.
    """
    feature_map = _get_feature_map(endpoint)
    if feature_map is None:
        return False
    return bool(feature_map & DoorLockFeature.kUser)


@callback
def lock_supports_week_day_schedules(endpoint: MatterEndpoint) -> bool:
    """Check if lock endpoint supports Week Day Schedules (WDSCH) feature."""
    feature_map = _get_feature_map(endpoint)
    if feature_map is None:
        return False
    return bool(feature_map & DoorLockFeature.kWeekDayAccessSchedules)


@callback
def lock_supports_year_day_schedules(endpoint: MatterEndpoint) -> bool:
    """Check if lock endpoint supports Year Day Schedules (YDSCH) feature."""
    feature_map = _get_feature_map(endpoint)
    if feature_map is None:
        return False
    return bool(feature_map & DoorLockFeature.kYearDayAccessSchedules)


@callback
def lock_supports_holiday_schedules(endpoint: MatterEndpoint) -> bool:
    """Check if lock endpoint supports Holiday Schedules (HDSCH) feature."""
    feature_map = _get_feature_map(endpoint)
    if feature_map is None:
        return False
    return bool(feature_map & DoorLockFeature.kHolidaySchedules)


# --- Pure utility functions ---


def _get_attr(obj: Any, attr: str) -> Any:
    """Get attribute from object or dict.

    Matter SDK responses can be either dataclass objects or dicts depending on
    the SDK version and serialization context.
    """
    if isinstance(obj, dict):
        return obj.get(attr)
    return getattr(obj, attr, None)


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


# --- Credential management helpers ---


def validate_pin_code(pin: str, min_len: int, max_len: int) -> str | None:
    """Validate a PIN code against lock constraints.

    Returns an error code string on failure, or None if valid.
    """
    if not pin.isdigit():
        return ERR_INVALID_PIN_CODE
    if len(pin) < min_len or len(pin) > max_len:
        return ERR_INVALID_PIN_CODE
    return None


async def find_available_credential_slot(
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


async def set_credential_for_user(
    matter_client: MatterClient,
    node_id: int,
    endpoint_id: int,
    user_index: int,
    cred_type: int,
    cred_data: bytes,
    credential_index: int,
    operation: clusters.DoorLock.Enums.DataOperationTypeEnum,
) -> dict[str, Any]:
    """Set a credential for a user at a specific credential slot.

    Uses the given operation type (kAdd for new credentials, kModify for
    existing ones) and writes credential data to the specified slot index.

    Returns a dict with 'status' (str) and 'credential_index' (int|None).
    """
    response = await matter_client.send_device_command(
        node_id=node_id,
        endpoint_id=endpoint_id,
        command=clusters.DoorLock.Commands.SetCredential(
            operationType=operation,
            credential=clusters.DoorLock.Structs.CredentialStruct(
                credentialType=cred_type,
                credentialIndex=credential_index,
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


async def clear_user_credentials(
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


class LockEndpointNotFoundError(HomeAssistantError):
    """Lock endpoint not found on node."""


class UsrFeatureNotSupportedError(HomeAssistantError):
    """Lock does not support USR (user management) feature."""


class UserSlotEmptyError(HomeAssistantError):
    """User slot is empty."""


class NoAvailableUserSlotsError(HomeAssistantError):
    """No available user slots on the lock."""


class InvalidPinCodeError(HomeAssistantError):
    """PIN code is invalid."""


class PinCredentialNotSupportedError(HomeAssistantError):
    """Lock does not support PIN credentials."""


class CredentialSlotError(HomeAssistantError):
    """No available credential slots."""


class CredentialSetError(HomeAssistantError):
    """SetCredential command failed."""


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
        await set_credential_for_user(
            matter_client,
            node_id,
            endpoint_id,
            user_index,
            pin_cred_type,
            pin_code.encode(),
            credential_index=existing_cred_index,
            operation=clusters.DoorLock.Enums.DataOperationTypeEnum.kModify,
        )
    else:
        # Find available slot and add new credential
        max_pin_slots = (
            lock_endpoint.get_attribute_value(
                None, clusters.DoorLock.Attributes.NumberOfPINUsersSupported
            )
            or 0
        )
        slot = await find_available_credential_slot(
            matter_client, node_id, endpoint_id, pin_cred_type, max_pin_slots
        )
        if slot is None:
            raise CredentialSlotError("No available credential slots on the lock")

        result = await set_credential_for_user(
            matter_client,
            node_id,
            endpoint_id,
            user_index,
            pin_cred_type,
            pin_code.encode(),
            credential_index=slot,
            operation=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
        )
        if result["status"] != "success":
            raise CredentialSetError(result["status"])


# --- High-level business logic functions ---


async def get_lock_info(
    matter_client: MatterClient,
    node: MatterNode,
) -> dict[str, Any]:
    """Get lock capabilities and configuration info.

    Returns a dict with lock capability information.
    Raises HomeAssistantError if lock endpoint not found.
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockEndpointNotFoundError("No lock endpoint found on this device")

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

    return result


async def set_lock_user(
    matter_client: MatterClient,
    node: MatterNode,
    *,
    user_index: int | None = None,
    user_name: str | None = None,
    user_unique_id: int | None = None,
    user_status: str = "occupied_enabled",
    user_type: str = "unrestricted_user",
    credential_rule: str = "single",
    pin_code: str | None = None,
    pin_code_present: bool = False,
) -> dict[str, Any]:
    """Add or update a user on the lock with optional PIN credential.

    Returns dict with user_index on success.
    Raises HomeAssistantError on failure.
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockEndpointNotFoundError("No lock endpoint found on this device")

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrFeatureNotSupportedError(
            "Lock does not support user/credential management"
        )

    feature_map = (
        lock_endpoint.get_attribute_value(None, clusters.DoorLock.Attributes.FeatureMap)
        or 0
    )
    has_pin_feature = bool(feature_map & DoorLockFeature.kPinCredential)

    # Validate PIN code if a non-null value was provided
    if pin_code_present and pin_code is not None:
        if not has_pin_feature:
            raise PinCredentialNotSupportedError(
                "Lock does not support PIN credentials"
            )

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
        pin_error = validate_pin_code(pin_code, min_pin, max_pin)
        if pin_error is not None:
            raise InvalidPinCodeError(f"PIN code must be {min_pin}-{max_pin} digits")

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
            get_user_response = await matter_client.send_device_command(
                node_id=node.node_id,
                endpoint_id=lock_endpoint.endpoint_id,
                command=clusters.DoorLock.Commands.GetUser(userIndex=idx),
            )
            if _get_attr(get_user_response, "userStatus") is None:
                user_index = idx
                break

        if user_index is None:
            raise NoAvailableUserSlotsError("No available user slots on the lock")

        user_status_enum = (
            clusters.DoorLock.Enums.UserStatusEnum.kOccupiedEnabled
            if user_status == "occupied_enabled"
            else clusters.DoorLock.Enums.UserStatusEnum.kOccupiedDisabled
        )

        await matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.SetUser(
                operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
                userIndex=user_index,
                userName=user_name,
                userUniqueID=user_unique_id,
                userStatus=user_status_enum,
                userType=USER_TYPE_REVERSE_MAP.get(user_type, 0),
                credentialRule=CREDENTIAL_RULE_REVERSE_MAP.get(credential_rule, 0),
            ),
            timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
        )
    else:
        # Updating existing user
        get_user_response = await matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.GetUser(userIndex=user_index),
        )

        if _get_attr(get_user_response, "userStatus") is None:
            raise UserSlotEmptyError(f"User slot {user_index} is empty")

        resolved_user_name = (
            user_name
            if user_name is not None
            else _get_attr(get_user_response, "userName")
        )
        resolved_unique_id = (
            user_unique_id
            if user_unique_id is not None
            else _get_attr(get_user_response, "userUniqueID")
        )

        resolved_status = _get_attr(get_user_response, "userStatus")
        resolved_status = USER_STATUS_REVERSE_MAP.get(user_status, resolved_status)

        resolved_type = _get_attr(get_user_response, "userType")
        resolved_type = USER_TYPE_REVERSE_MAP.get(user_type, resolved_type)

        resolved_rule = _get_attr(get_user_response, "credentialRule")
        resolved_rule = CREDENTIAL_RULE_REVERSE_MAP.get(credential_rule, resolved_rule)

        await matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.SetUser(
                operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kModify,
                userIndex=user_index,
                userName=resolved_user_name,
                userUniqueID=resolved_unique_id,
                userStatus=resolved_status,
                userType=resolved_type,
                credentialRule=resolved_rule,
            ),
            timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
        )

    # Handle PIN credential operations
    if pin_code_present:
        try:
            await _handle_pin_credential(
                matter_client,
                node.node_id,
                lock_endpoint.endpoint_id,
                user_index,
                pin_code,
                has_pin_feature,
                lock_endpoint,
            )
        except CredentialSlotError:
            if is_new_user:
                _LOGGER.debug(
                    "No credential slots for new user at index %s, rolling back",
                    user_index,
                )
                await matter_client.send_device_command(
                    node_id=node.node_id,
                    endpoint_id=lock_endpoint.endpoint_id,
                    command=clusters.DoorLock.Commands.ClearUser(userIndex=user_index),
                    timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
                )
            raise
        except CredentialSetError:
            if is_new_user:
                _LOGGER.debug(
                    "SetCredential failed for new user at index %s, rolling back",
                    user_index,
                )
                await matter_client.send_device_command(
                    node_id=node.node_id,
                    endpoint_id=lock_endpoint.endpoint_id,
                    command=clusters.DoorLock.Commands.ClearUser(userIndex=user_index),
                    timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
                )
            raise

    return {ATTR_USER_INDEX: user_index}


async def get_lock_users(
    matter_client: MatterClient,
    node: MatterNode,
) -> dict[str, Any]:
    """Get all users from the lock.

    Returns dict with users list and metadata.
    Raises HomeAssistantError on failure.
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockEndpointNotFoundError("No lock endpoint found on this device")

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrFeatureNotSupportedError(
            "Lock does not support user/credential management"
        )

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
        get_user_response = await matter_client.send_device_command(
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

    return {
        "total_users": len(users),
        "max_users": max_users,
        "users": users,
    }


async def clear_lock_user(
    matter_client: MatterClient,
    node: MatterNode,
    user_index: int,
) -> None:
    """Clear a user from the lock, cleaning up credentials first.

    Use index 0xFFFE (CLEAR_ALL_INDEX) to clear all users.
    Raises HomeAssistantError on failure.
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockEndpointNotFoundError("No lock endpoint found on this device")

    if not lock_supports_usr_feature(lock_endpoint):
        raise UsrFeatureNotSupportedError(
            "Lock does not support user/credential management"
        )

    if user_index == CLEAR_ALL_INDEX:
        # Clear all: clear all credentials first, then all users
        await matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.ClearCredential(
                credential=None,
            ),
            timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
        )
    else:
        # Clear credentials for this specific user before deleting them
        await clear_user_credentials(
            matter_client,
            node.node_id,
            lock_endpoint.endpoint_id,
            user_index,
        )

    await matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.ClearUser(
            userIndex=user_index,
        ),
        timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
    )
