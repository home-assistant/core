"""Lock-specific helpers for the Matter integration.

Provides DoorLock cluster endpoint resolution, feature detection, and
business logic for lock user/credential management.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import (
    CRED_TYPE_FACE,
    CRED_TYPE_FINGER_VEIN,
    CRED_TYPE_FINGERPRINT,
    CRED_TYPE_PIN,
    CRED_TYPE_RFID,
    CREDENTIAL_RULE_MAP,
    CREDENTIAL_RULE_REVERSE_MAP,
    CREDENTIAL_TYPE_MAP,
    CREDENTIAL_TYPE_REVERSE_MAP,
    LOCK_TIMED_REQUEST_TIMEOUT_MS,
    USER_STATUS_MAP,
    USER_STATUS_REVERSE_MAP,
    USER_TYPE_MAP,
    USER_TYPE_REVERSE_MAP,
)

# Error translation keys (used in ServiceValidationError/HomeAssistantError)
ERR_CREDENTIAL_TYPE_NOT_SUPPORTED = "credential_type_not_supported"
ERR_INVALID_CREDENTIAL_DATA = "invalid_credential_data"

# SetCredential response status mapping (Matter DlStatus)
_DlStatus = clusters.DoorLock.Enums.DlStatus
SET_CREDENTIAL_STATUS_MAP: dict[int, str] = {
    _DlStatus.kSuccess: "success",
    _DlStatus.kFailure: "failure",
    _DlStatus.kDuplicate: "duplicate",
    _DlStatus.kOccupied: "occupied",
}

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint, MatterNode

# DoorLock Feature bitmap from Matter SDK
DoorLockFeature = clusters.DoorLock.Bitmaps.Feature


# --- TypedDicts for service action responses ---


class LockUserCredentialData(TypedDict):
    """Credential data within a user response."""

    type: str
    index: int | None


class LockUserData(TypedDict):
    """User data returned from lock queries."""

    user_index: int | None
    user_name: str | None
    user_unique_id: int | None
    user_status: str
    user_type: str
    credential_rule: str
    credentials: list[LockUserCredentialData]
    next_user_index: int | None


class SetLockUserResult(TypedDict):
    """Result of set_lock_user service action."""

    user_index: int


class GetLockUsersResult(TypedDict):
    """Result of get_lock_users service action."""

    max_users: int
    users: list[LockUserData]


class GetLockInfoResult(TypedDict):
    """Result of get_lock_info service action."""

    supports_user_management: bool
    supported_credential_types: list[str]
    max_users: int | None
    max_pin_users: int | None
    max_rfid_users: int | None
    max_credentials_per_user: int | None
    min_pin_length: int | None
    max_pin_length: int | None
    min_rfid_length: int | None
    max_rfid_length: int | None


class SetLockCredentialResult(TypedDict):
    """Result of set_lock_credential service action."""

    credential_index: int
    user_index: int | None
    next_credential_index: int | None


class GetLockCredentialStatusResult(TypedDict):
    """Result of get_lock_credential_status service action."""

    credential_exists: bool
    user_index: int | None
    next_credential_index: int | None


def _get_lock_endpoint_from_node(node: MatterNode) -> MatterEndpoint | None:
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


def _lock_supports_usr_feature(endpoint: MatterEndpoint) -> bool:
    """Check if lock endpoint supports USR (User) feature.

    The USR feature indicates the lock supports user and credential management
    commands like SetUser, GetUser, SetCredential, etc.
    """
    feature_map = _get_feature_map(endpoint)
    if feature_map is None:
        return False
    return bool(feature_map & DoorLockFeature.kUser)


# --- Pure utility functions ---


def _get_attr(obj: Any, attr: str) -> Any:
    """Get attribute from object or dict.

    Matter SDK responses can be either dataclass objects or dicts depending on
    the SDK version and serialization context. NullValue (a truthy,
    non-iterable singleton) is normalized to None.
    """
    if isinstance(obj, dict):
        value = obj.get(attr)
    else:
        value = getattr(obj, attr, None)
    # The Matter SDK uses NullValue for nullable fields instead of None.
    if value is NullValue:
        return None
    return value


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


def _format_user_response(user_data: Any) -> LockUserData | None:
    """Format GetUser response to API response format.

    Returns None if the user slot is empty (no userStatus).
    """
    if user_data is None:
        return None

    user_status = _get_attr(user_data, "userStatus")
    if user_status is None:
        return None

    creds = _get_attr(user_data, "credentials")
    credentials: list[LockUserCredentialData] = [
        LockUserCredentialData(
            type=CREDENTIAL_TYPE_MAP.get(_get_attr(cred, "credentialType"), "unknown"),
            index=_get_attr(cred, "credentialIndex"),
        )
        for cred in (creds or [])
    ]

    return LockUserData(
        user_index=_get_attr(user_data, "userIndex"),
        user_name=_get_attr(user_data, "userName"),
        user_unique_id=_get_attr(user_data, "userUniqueID"),
        user_status=USER_STATUS_MAP.get(user_status, "unknown"),
        user_type=USER_TYPE_MAP.get(_get_attr(user_data, "userType"), "unknown"),
        credential_rule=CREDENTIAL_RULE_MAP.get(
            _get_attr(user_data, "credentialRule"), "unknown"
        ),
        credentials=credentials,
        next_user_index=_get_attr(user_data, "nextUserIndex"),
    )


# --- Credential management helpers ---


class LockEndpointNotFoundError(HomeAssistantError):
    """Lock endpoint not found on node."""


class UsrFeatureNotSupportedError(ServiceValidationError):
    """Lock does not support USR (user management) feature."""


class UserSlotEmptyError(ServiceValidationError):
    """User slot is empty."""


class NoAvailableUserSlotsError(ServiceValidationError):
    """No available user slots on the lock."""


class CredentialTypeNotSupportedError(ServiceValidationError):
    """Lock does not support the requested credential type."""


class CredentialDataInvalidError(ServiceValidationError):
    """Credential data fails validation."""


class SetCredentialFailedError(HomeAssistantError):
    """SetCredential command returned a non-success status."""


def _get_lock_endpoint_or_raise(node: MatterNode) -> MatterEndpoint:
    """Get the DoorLock endpoint from a node or raise an error."""
    lock_endpoint = _get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockEndpointNotFoundError("No lock endpoint found on this device")
    return lock_endpoint


def _ensure_usr_support(lock_endpoint: MatterEndpoint) -> None:
    """Ensure the lock endpoint supports USR (user management) feature.

    Raises UsrFeatureNotSupportedError if the lock doesn't support user management.
    """
    if not _lock_supports_usr_feature(lock_endpoint):
        raise UsrFeatureNotSupportedError(
            "Lock does not support user/credential management"
        )


# --- High-level business logic functions ---


async def get_lock_info(
    matter_client: MatterClient,
    node: MatterNode,
) -> GetLockInfoResult:
    """Get lock capabilities and configuration info.

    Returns a typed dict with lock capability information.
    Raises HomeAssistantError if lock endpoint not found.
    """
    lock_endpoint = _get_lock_endpoint_or_raise(node)
    supports_usr = _lock_supports_usr_feature(lock_endpoint)

    # Get feature map for credential type detection
    feature_map = (
        lock_endpoint.get_attribute_value(None, clusters.DoorLock.Attributes.FeatureMap)
        or 0
    )

    result = GetLockInfoResult(
        supports_user_management=supports_usr,
        supported_credential_types=_get_supported_credential_types(feature_map),
        max_users=None,
        max_pin_users=None,
        max_rfid_users=None,
        max_credentials_per_user=None,
        min_pin_length=None,
        max_pin_length=None,
        min_rfid_length=None,
        max_rfid_length=None,
    )

    # Populate capacity info if USR feature is supported
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

    return result


async def set_lock_user(
    matter_client: MatterClient,
    node: MatterNode,
    *,
    user_index: int | None = None,
    user_name: str | None = None,
    user_unique_id: int | None = None,
    user_status: str | None = None,
    user_type: str | None = None,
    credential_rule: str | None = None,
) -> SetLockUserResult:
    """Add or update a user on the lock.

    When user_status, user_type, or credential_rule is None, defaults are used
    for new users and existing values are preserved for modifications.

    Returns typed dict with user_index on success.
    Raises HomeAssistantError on failure.
    """
    lock_endpoint = _get_lock_endpoint_or_raise(node)
    _ensure_usr_support(lock_endpoint)

    if user_index is None:
        # Adding new user - find first available slot
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
            USER_STATUS_REVERSE_MAP.get(
                user_status,
                clusters.DoorLock.Enums.UserStatusEnum.kOccupiedEnabled,
            )
            if user_status is not None
            else clusters.DoorLock.Enums.UserStatusEnum.kOccupiedEnabled
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
                userType=USER_TYPE_REVERSE_MAP.get(
                    user_type,
                    clusters.DoorLock.Enums.UserTypeEnum.kUnrestrictedUser,
                )
                if user_type is not None
                else clusters.DoorLock.Enums.UserTypeEnum.kUnrestrictedUser,
                credentialRule=CREDENTIAL_RULE_REVERSE_MAP.get(
                    credential_rule,
                    clusters.DoorLock.Enums.CredentialRuleEnum.kSingle,
                )
                if credential_rule is not None
                else clusters.DoorLock.Enums.CredentialRuleEnum.kSingle,
            ),
            timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
        )
    else:
        # Updating existing user - preserve existing values when not specified
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

        resolved_status = (
            USER_STATUS_REVERSE_MAP[user_status]
            if user_status is not None
            else _get_attr(get_user_response, "userStatus")
        )

        resolved_type = (
            USER_TYPE_REVERSE_MAP[user_type]
            if user_type is not None
            else _get_attr(get_user_response, "userType")
        )

        resolved_rule = (
            CREDENTIAL_RULE_REVERSE_MAP[credential_rule]
            if credential_rule is not None
            else _get_attr(get_user_response, "credentialRule")
        )

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

    return SetLockUserResult(user_index=user_index)


async def get_lock_users(
    matter_client: MatterClient,
    node: MatterNode,
) -> GetLockUsersResult:
    """Get all users from the lock.

    Returns typed dict with users list and max_users capacity.
    Raises HomeAssistantError on failure.
    """
    lock_endpoint = _get_lock_endpoint_or_raise(node)
    _ensure_usr_support(lock_endpoint)

    max_users = (
        lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfTotalUsersSupported
        )
        or 0
    )

    users: list[LockUserData] = []
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

    return GetLockUsersResult(
        max_users=max_users,
        users=users,
    )


async def clear_lock_user(
    matter_client: MatterClient,
    node: MatterNode,
    user_index: int,
) -> None:
    """Clear a user from the lock.

    Per the Matter spec, ClearUser also clears all associated credentials
    and schedules for the user.
    Use index 0xFFFE (CLEAR_ALL_INDEX) to clear all users.
    Raises HomeAssistantError on failure.
    """
    lock_endpoint = _get_lock_endpoint_or_raise(node)
    _ensure_usr_support(lock_endpoint)

    await matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.ClearUser(
            userIndex=user_index,
        ),
        timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
    )


# --- Credential validation helpers ---

# Map credential type strings to the feature bit that must be set
_CREDENTIAL_TYPE_FEATURE_MAP: dict[str, int] = {
    CRED_TYPE_PIN: DoorLockFeature.kPinCredential,
    CRED_TYPE_RFID: DoorLockFeature.kRfidCredential,
    CRED_TYPE_FINGERPRINT: DoorLockFeature.kFingerCredentials,
    CRED_TYPE_FINGER_VEIN: DoorLockFeature.kFingerCredentials,
    CRED_TYPE_FACE: DoorLockFeature.kFaceCredentials,
}

# Map credential type strings to the capacity attribute for slot iteration.
# Biometric types have no dedicated capacity attribute; fall back to total users.
_CREDENTIAL_TYPE_CAPACITY_ATTR = {
    CRED_TYPE_PIN: clusters.DoorLock.Attributes.NumberOfPINUsersSupported,
    CRED_TYPE_RFID: clusters.DoorLock.Attributes.NumberOfRFIDUsersSupported,
}


def _validate_credential_type_support(
    lock_endpoint: MatterEndpoint, credential_type: str
) -> None:
    """Validate the lock supports the requested credential type.

    Raises CredentialTypeNotSupportedError if not supported.
    """
    required_bit = _CREDENTIAL_TYPE_FEATURE_MAP.get(credential_type)
    if required_bit is None:
        raise CredentialTypeNotSupportedError(
            translation_domain="matter",
            translation_key=ERR_CREDENTIAL_TYPE_NOT_SUPPORTED,
            translation_placeholders={"credential_type": credential_type},
        )

    feature_map = _get_feature_map(lock_endpoint) or 0
    if not (feature_map & required_bit):
        raise CredentialTypeNotSupportedError(
            translation_domain="matter",
            translation_key=ERR_CREDENTIAL_TYPE_NOT_SUPPORTED,
            translation_placeholders={"credential_type": credential_type},
        )


def _validate_credential_data(
    lock_endpoint: MatterEndpoint, credential_type: str, credential_data: str
) -> None:
    """Validate credential data against lock constraints.

    For PIN: checks digits-only and length against Min/MaxPINCodeLength.
    For RFID: checks valid hex and byte length against Min/MaxRFIDCodeLength.
    Raises CredentialDataInvalidError on failure.
    """
    if credential_type == CRED_TYPE_PIN:
        if not credential_data.isdigit():
            raise CredentialDataInvalidError(
                translation_domain="matter",
                translation_key=ERR_INVALID_CREDENTIAL_DATA,
                translation_placeholders={"reason": "PIN must contain only digits"},
            )
        min_len = (
            lock_endpoint.get_attribute_value(
                None, clusters.DoorLock.Attributes.MinPINCodeLength
            )
            or 0
        )
        max_len = (
            lock_endpoint.get_attribute_value(
                None, clusters.DoorLock.Attributes.MaxPINCodeLength
            )
            or 255
        )
        if not min_len <= len(credential_data) <= max_len:
            raise CredentialDataInvalidError(
                translation_domain="matter",
                translation_key=ERR_INVALID_CREDENTIAL_DATA,
                translation_placeholders={
                    "reason": (f"PIN length must be between {min_len} and {max_len}")
                },
            )

    elif credential_type == CRED_TYPE_RFID:
        try:
            rfid_bytes = bytes.fromhex(credential_data)
        except ValueError as err:
            raise CredentialDataInvalidError(
                translation_domain="matter",
                translation_key=ERR_INVALID_CREDENTIAL_DATA,
                translation_placeholders={
                    "reason": "RFID data must be valid hexadecimal"
                },
            ) from err
        min_len = (
            lock_endpoint.get_attribute_value(
                None, clusters.DoorLock.Attributes.MinRFIDCodeLength
            )
            or 0
        )
        max_len = (
            lock_endpoint.get_attribute_value(
                None, clusters.DoorLock.Attributes.MaxRFIDCodeLength
            )
            or 255
        )
        if not min_len <= len(rfid_bytes) <= max_len:
            raise CredentialDataInvalidError(
                translation_domain="matter",
                translation_key=ERR_INVALID_CREDENTIAL_DATA,
                translation_placeholders={
                    "reason": (
                        f"RFID data length must be between"
                        f" {min_len} and {max_len} bytes"
                    )
                },
            )


def _credential_data_to_bytes(credential_type: str, credential_data: str) -> bytes:
    """Convert credential data string to bytes for the Matter command."""
    if credential_type == CRED_TYPE_RFID:
        return bytes.fromhex(credential_data)
    # PIN and other types: encode as UTF-8
    return credential_data.encode()


# --- Credential business logic functions ---


async def set_lock_credential(
    matter_client: MatterClient,
    node: MatterNode,
    *,
    credential_type: str,
    credential_data: str,
    credential_index: int | None = None,
    user_index: int | None = None,
    user_status: str | None = None,
    user_type: str | None = None,
) -> SetLockCredentialResult:
    """Add or modify a credential on the lock.

    Returns typed dict with credential_index, user_index, and next_credential_index.
    Raises ServiceValidationError for validation failures.
    Raises HomeAssistantError for device communication failures.
    """
    lock_endpoint = _get_lock_endpoint_or_raise(node)
    _ensure_usr_support(lock_endpoint)
    _validate_credential_type_support(lock_endpoint, credential_type)
    _validate_credential_data(lock_endpoint, credential_type, credential_data)

    cred_type_int = CREDENTIAL_TYPE_REVERSE_MAP[credential_type]
    cred_data_bytes = _credential_data_to_bytes(credential_type, credential_data)

    # Determine operation type and credential index
    operation_type = clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd

    if credential_index is None:
        # Auto-find first available credential slot.
        # Use the credential-type-specific capacity as the upper bound.
        max_creds_attr = _CREDENTIAL_TYPE_CAPACITY_ATTR.get(
            credential_type,
            clusters.DoorLock.Attributes.NumberOfTotalUsersSupported,
        )
        max_creds_raw = lock_endpoint.get_attribute_value(None, max_creds_attr)
        max_creds = (
            max_creds_raw if isinstance(max_creds_raw, int) and max_creds_raw > 0 else 5
        )
        for idx in range(1, max_creds + 1):
            status_response = await matter_client.send_device_command(
                node_id=node.node_id,
                endpoint_id=lock_endpoint.endpoint_id,
                command=clusters.DoorLock.Commands.GetCredentialStatus(
                    credential=clusters.DoorLock.Structs.CredentialStruct(
                        credentialType=cred_type_int,
                        credentialIndex=idx,
                    ),
                ),
            )
            if not _get_attr(status_response, "credentialExists"):
                credential_index = idx
                break

        if credential_index is None:
            raise NoAvailableUserSlotsError("No available credential slots on the lock")
    else:
        # Check if slot is occupied to determine Add vs Modify
        status_response = await matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.GetCredentialStatus(
                credential=clusters.DoorLock.Structs.CredentialStruct(
                    credentialType=cred_type_int,
                    credentialIndex=credential_index,
                ),
            ),
        )
        if _get_attr(status_response, "credentialExists"):
            operation_type = clusters.DoorLock.Enums.DataOperationTypeEnum.kModify

    # Resolve optional user_status and user_type enums
    resolved_user_status = (
        USER_STATUS_REVERSE_MAP.get(user_status) if user_status is not None else None
    )
    resolved_user_type = (
        USER_TYPE_REVERSE_MAP.get(user_type) if user_type is not None else None
    )

    set_cred_response = await matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.SetCredential(
            operationType=operation_type,
            credential=clusters.DoorLock.Structs.CredentialStruct(
                credentialType=cred_type_int,
                credentialIndex=credential_index,
            ),
            credentialData=cred_data_bytes,
            userIndex=user_index,
            userStatus=resolved_user_status,
            userType=resolved_user_type,
        ),
        timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
    )

    status_code = _get_attr(set_cred_response, "status")
    status_str = SET_CREDENTIAL_STATUS_MAP.get(status_code, f"unknown({status_code})")
    if status_str != "success":
        raise SetCredentialFailedError(
            translation_domain="matter",
            translation_key="set_credential_failed",
            translation_placeholders={"status": status_str},
        )

    return SetLockCredentialResult(
        credential_index=credential_index,
        user_index=_get_attr(set_cred_response, "userIndex"),
        next_credential_index=_get_attr(set_cred_response, "nextCredentialIndex"),
    )


async def clear_lock_credential(
    matter_client: MatterClient,
    node: MatterNode,
    *,
    credential_type: str,
    credential_index: int,
) -> None:
    """Clear a credential from the lock.

    Raises HomeAssistantError on failure.
    """
    lock_endpoint = _get_lock_endpoint_or_raise(node)
    _ensure_usr_support(lock_endpoint)

    cred_type_int = CREDENTIAL_TYPE_REVERSE_MAP[credential_type]

    await matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.ClearCredential(
            credential=clusters.DoorLock.Structs.CredentialStruct(
                credentialType=cred_type_int,
                credentialIndex=credential_index,
            ),
        ),
        timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
    )


async def get_lock_credential_status(
    matter_client: MatterClient,
    node: MatterNode,
    *,
    credential_type: str,
    credential_index: int,
) -> GetLockCredentialStatusResult:
    """Get the status of a credential slot on the lock.

    Returns typed dict with credential_exists, user_index, next_credential_index.
    Raises HomeAssistantError on failure.
    """
    lock_endpoint = _get_lock_endpoint_or_raise(node)
    _ensure_usr_support(lock_endpoint)

    cred_type_int = CREDENTIAL_TYPE_REVERSE_MAP[credential_type]

    response = await matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.GetCredentialStatus(
            credential=clusters.DoorLock.Structs.CredentialStruct(
                credentialType=cred_type_int,
                credentialIndex=credential_index,
            ),
        ),
    )

    return GetLockCredentialStatusResult(
        credential_exists=bool(_get_attr(response, "credentialExists")),
        user_index=_get_attr(response, "userIndex"),
        next_credential_index=_get_attr(response, "nextCredentialIndex"),
    )
