"""Lock helpers for Z-Wave JS credential management.

Provides business logic for user/credential CRUD, capability queries,
auto-find logic, and validation.
"""

import asyncio
from collections import defaultdict
import logging
from typing import TypedDict

from zwave_js_server.const.command_class.access_control import (
    SetCredentialResult,
    SetUserResult,
    UserCredentialRule,
    UserCredentialType,
    UserCredentialUserType,
)
from zwave_js_server.model.access_control import SetUserOptions
from zwave_js_server.model.node import Node

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import (
    CREDENTIAL_RULE_DUAL,
    CREDENTIAL_RULE_SINGLE,
    CREDENTIAL_RULE_TRIPLE,
    CREDENTIAL_TYPE_BLE,
    CREDENTIAL_TYPE_DESFIRE,
    CREDENTIAL_TYPE_EYE_BIOMETRIC,
    CREDENTIAL_TYPE_FACE_BIOMETRIC,
    CREDENTIAL_TYPE_FINGER_BIOMETRIC,
    CREDENTIAL_TYPE_HAND_BIOMETRIC,
    CREDENTIAL_TYPE_NFC,
    CREDENTIAL_TYPE_PASSWORD,
    CREDENTIAL_TYPE_PIN_CODE,
    CREDENTIAL_TYPE_RFID_CODE,
    CREDENTIAL_TYPE_UNSPECIFIED_BIOMETRIC,
    CREDENTIAL_TYPE_UWB,
    DOMAIN,
    USER_TYPE_DISPOSABLE,
    USER_TYPE_DURESS,
    USER_TYPE_EXPIRING,
    USER_TYPE_GENERAL,
    USER_TYPE_NON_ACCESS,
    USER_TYPE_PROGRAMMING,
    USER_TYPE_REMOTE_ONLY,
)

_LOGGER = logging.getLogger(__name__)

# --- Enum <-> string mappings ---

CREDENTIAL_TYPE_MAP: dict[UserCredentialType, str] = {
    UserCredentialType.PIN_CODE: CREDENTIAL_TYPE_PIN_CODE,
    UserCredentialType.PASSWORD: CREDENTIAL_TYPE_PASSWORD,
    UserCredentialType.RFID_CODE: CREDENTIAL_TYPE_RFID_CODE,
    UserCredentialType.BLE: CREDENTIAL_TYPE_BLE,
    UserCredentialType.NFC: CREDENTIAL_TYPE_NFC,
    UserCredentialType.UWB: CREDENTIAL_TYPE_UWB,
    UserCredentialType.EYE_BIOMETRIC: CREDENTIAL_TYPE_EYE_BIOMETRIC,
    UserCredentialType.FACE_BIOMETRIC: CREDENTIAL_TYPE_FACE_BIOMETRIC,
    UserCredentialType.FINGER_BIOMETRIC: CREDENTIAL_TYPE_FINGER_BIOMETRIC,
    UserCredentialType.HAND_BIOMETRIC: CREDENTIAL_TYPE_HAND_BIOMETRIC,
    UserCredentialType.UNSPECIFIED_BIOMETRIC: CREDENTIAL_TYPE_UNSPECIFIED_BIOMETRIC,
    UserCredentialType.DESFIRE: CREDENTIAL_TYPE_DESFIRE,
}
CREDENTIAL_TYPE_REVERSE_MAP: dict[str, UserCredentialType] = {
    v: k for k, v in CREDENTIAL_TYPE_MAP.items()
}

USER_TYPE_MAP: dict[UserCredentialUserType, str] = {
    UserCredentialUserType.GENERAL: USER_TYPE_GENERAL,
    UserCredentialUserType.PROGRAMMING: USER_TYPE_PROGRAMMING,
    UserCredentialUserType.NON_ACCESS: USER_TYPE_NON_ACCESS,
    UserCredentialUserType.DURESS: USER_TYPE_DURESS,
    UserCredentialUserType.DISPOSABLE: USER_TYPE_DISPOSABLE,
    UserCredentialUserType.EXPIRING: USER_TYPE_EXPIRING,
    UserCredentialUserType.REMOTE_ONLY: USER_TYPE_REMOTE_ONLY,
}
USER_TYPE_REVERSE_MAP: dict[str, UserCredentialUserType] = {
    v: k for k, v in USER_TYPE_MAP.items()
}

CREDENTIAL_RULE_MAP: dict[UserCredentialRule, str] = {
    UserCredentialRule.SINGLE: CREDENTIAL_RULE_SINGLE,
    UserCredentialRule.DUAL: CREDENTIAL_RULE_DUAL,
    UserCredentialRule.TRIPLE: CREDENTIAL_RULE_TRIPLE,
}
CREDENTIAL_RULE_REVERSE_MAP: dict[str, UserCredentialRule] = {
    v: k for k, v in CREDENTIAL_RULE_MAP.items()
}


_SET_USER_RESULT_KEYS: dict[SetUserResult, str] = {
    SetUserResult.ERROR_ADD_REJECTED_LOCATION_OCCUPIED: "user_rejected_add_occupied",
    SetUserResult.ERROR_MODIFY_REJECTED_LOCATION_EMPTY: "user_rejected_modify_empty",
    SetUserResult.ERROR_UNKNOWN: "user_rejected_unknown",
}

_SET_CREDENTIAL_RESULT_KEYS: dict[SetCredentialResult, str] = {
    SetCredentialResult.ERROR_ADD_REJECTED_LOCATION_OCCUPIED: (
        "credential_rejected_add_occupied"
    ),
    SetCredentialResult.ERROR_MODIFY_REJECTED_LOCATION_EMPTY: (
        "credential_rejected_modify_empty"
    ),
    SetCredentialResult.ERROR_DUPLICATE_CREDENTIAL: "credential_rejected_duplicate",
    SetCredentialResult.ERROR_MANUFACTURER_SECURITY_RULES: (
        "credential_rejected_manufacturer_rules"
    ),
    SetCredentialResult.ERROR_DUPLICATE_ADMIN_PIN_CODE: "credential_rejected_duplicate",
    SetCredentialResult.ERROR_WRONG_USER_UNIQUE_IDENTIFIER: (
        "credential_rejected_wrong_uuid"
    ),
    SetCredentialResult.ERROR_UNKNOWN: "credential_rejected_unknown",
}


def _raise_on_set_user_error(status: SetUserResult) -> None:
    """Raise HomeAssistantError when a user-mutation command is rejected."""
    if status is SetUserResult.OK:
        return
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=_SET_USER_RESULT_KEYS.get(status, "user_rejected_unknown"),
    )


def _raise_on_set_credential_error(status: SetCredentialResult) -> None:
    """Raise HomeAssistantError when a credential-mutation command is rejected."""
    if status is SetCredentialResult.OK:
        return
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=_SET_CREDENTIAL_RESULT_KEYS.get(
            status, "credential_rejected_unknown"
        ),
    )


# --- TypedDicts for structured return values ---


class CredentialTypeCapability(TypedDict):
    """Capability info for a single credential type."""

    num_slots: int
    min_length: int
    max_length: int
    supports_learn: bool


class CredentialCapabilitiesResult(TypedDict):
    """Return type for get_credential_capabilities."""

    supports_user_management: bool
    max_users: int
    supported_user_types: list[str]
    max_user_name_length: int
    supported_credential_rules: list[str]
    supported_credential_types: dict[str, CredentialTypeCapability]


class Credential(TypedDict):
    """A credential reference within a user entry."""

    type: str
    slot: int


class UserEntry(TypedDict):
    """A single user entry in the users list."""

    user_id: int
    user_name: str | None
    active: bool
    user_type: str
    credential_rule: str | None
    credentials: list[Credential]


class UsersResult(TypedDict):
    """Return type for get_users."""

    max_users: int
    users: list[UserEntry]


class SetUserReturn(TypedDict):
    """Return type for set_user."""

    user_id: int


class SetCredentialReturn(TypedDict):
    """Return type for set_credential."""

    credential_slot: int
    user_id: int


# --- Business logic functions ---


async def async_get_credential_capabilities(
    node: Node,
) -> CredentialCapabilitiesResult:
    """Query access-control capabilities for the node."""
    supported = await node.access_control.is_supported()
    if not supported:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="access_control_not_supported",
        )

    user_caps = await node.access_control.get_user_capabilities_cached()
    cred_caps = await node.access_control.get_credential_capabilities_cached()

    supported_credential_types: dict[str, CredentialTypeCapability] = {}
    for cred_type, capability in cred_caps.supported_credential_types.items():
        type_str = CREDENTIAL_TYPE_MAP.get(cred_type)
        if type_str is None:
            continue
        supported_credential_types[type_str] = CredentialTypeCapability(
            num_slots=capability.number_of_credential_slots,
            min_length=capability.min_credential_length,
            max_length=capability.max_credential_length,
            supports_learn=capability.supports_credential_learn,
        )

    return CredentialCapabilitiesResult(
        supports_user_management=True,
        max_users=user_caps.max_users,
        supported_user_types=[
            USER_TYPE_MAP[ut]
            for ut in user_caps.supported_user_types
            if ut in USER_TYPE_MAP
        ],
        max_user_name_length=user_caps.max_user_name_length or 0,
        supported_credential_rules=[
            CREDENTIAL_RULE_MAP[cr]
            for cr in user_caps.supported_credential_rules
            if cr in CREDENTIAL_RULE_MAP
        ],
        supported_credential_types=supported_credential_types,
    )


async def async_get_users(node: Node) -> UsersResult:
    """List all users with their credential references."""
    supported = await node.access_control.is_supported()
    if not supported:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="access_control_not_supported",
        )

    user_caps = await node.access_control.get_user_capabilities_cached()
    users = await node.access_control.get_users_cached()
    all_credentials = await node.access_control.get_all_credentials_cached()

    credentials_by_user: defaultdict[int, list[Credential]] = defaultdict(list)
    for cred in all_credentials:
        credentials_by_user[cred.user_id].append(
            Credential(
                type=CREDENTIAL_TYPE_MAP.get(cred.type, str(cred.type)),
                slot=cred.slot,
            )
        )

    user_list: list[UserEntry] = [
        UserEntry(
            user_id=user.user_id,
            user_name=user.user_name,
            active=user.active,
            user_type=USER_TYPE_MAP.get(user.user_type, str(user.user_type)),
            credential_rule=(
                CREDENTIAL_RULE_MAP.get(user.credential_rule)
                if user.credential_rule is not None
                else None
            ),
            credentials=credentials_by_user.get(user.user_id, []),
        )
        for user in users
    ]

    return UsersResult(
        max_users=user_caps.max_users,
        users=user_list,
    )


async def async_set_user(
    node: Node,
    user_id: int | None = None,
    user_name: str | None = None,
    user_type: UserCredentialUserType | None = None,
    credential_rule: UserCredentialRule | None = None,
    active: bool | None = None,
) -> SetUserReturn:
    """Create or update an access-control user. Returns the allocated user_id."""
    supported = await node.access_control.is_supported()
    if not supported:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="access_control_not_supported",
        )

    # Auto-find first available user slot
    if user_id is None:
        user_caps = await node.access_control.get_user_capabilities_cached()
        users = await node.access_control.get_users_cached()
        used_ids = {u.user_id for u in users}
        user_id = next(
            (i for i in range(1, user_caps.max_users + 1) if i not in used_ids),
            None,
        )
        if user_id is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_available_user_slots",
            )

    options = SetUserOptions(
        active=active,
        user_type=user_type,
        user_name=user_name,
        credential_rule=credential_rule,
    )

    status = await node.access_control.set_user(user_id, options)
    _raise_on_set_user_error(status)
    return SetUserReturn(user_id=user_id)


async def async_delete_user(node: Node, user_id: int) -> None:
    """Delete a single access-control user."""
    if not await node.access_control.is_supported():
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="access_control_not_supported",
        )

    status = await node.access_control.delete_user(user_id)
    _raise_on_set_user_error(status)


async def async_delete_all_users(node: Node) -> None:
    """Delete all access-control users."""
    if not await node.access_control.is_supported():
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="access_control_not_supported",
        )

    status = await node.access_control.delete_all_users()
    _raise_on_set_user_error(status)


async def async_set_credential(
    node: Node,
    user_id: int,
    credential_type: UserCredentialType,
    credential_data: str,
    credential_slot: int | None = None,
) -> SetCredentialReturn:
    """Add or update a credential (PIN/password only).

    user_id must refer to an existing user. To create a new user, call
    async_set_user first, then pass the returned user_id here. This service
    does not create or modify users.
    """
    supported = await node.access_control.is_supported()
    if not supported:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="access_control_not_supported",
        )

    cred_type_str = CREDENTIAL_TYPE_MAP.get(credential_type, str(credential_type))
    cred_caps = await node.access_control.get_credential_capabilities_cached()
    type_cap = cred_caps.supported_credential_types.get(credential_type)
    if type_cap is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="credential_type_not_supported",
            translation_placeholders={"credential_type": cred_type_str},
        )

    # Validate credential_data length and format against device capabilities
    if not (
        type_cap.min_credential_length
        <= len(credential_data)
        <= type_cap.max_credential_length
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="credential_data_invalid_length",
            translation_placeholders={
                "credential_type": cred_type_str,
                "min_length": str(type_cap.min_credential_length),
                "max_length": str(type_cap.max_credential_length),
            },
        )
    if credential_type is UserCredentialType.PIN_CODE and not (
        credential_data.isascii() and credential_data.isdigit()
    ):
        # str.isdigit() accepts non-ASCII digit code points (e.g. Arabic-Indic),
        # which the lock firmware cannot store. Restrict to ASCII 0-9.
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="credential_data_pin_not_digits",
        )

    if credential_slot is None:
        existing = await node.access_control.get_credentials_by_type_cached(
            credential_type
        )
        used_slots = {c.slot for c in existing}
        credential_slot = next(
            (
                s
                for s in range(1, type_cap.number_of_credential_slots + 1)
                if s not in used_slots
            ),
            None,
        )
        if credential_slot is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_available_credential_slots",
                translation_placeholders={"credential_type": cred_type_str},
            )
    elif not 1 <= credential_slot <= type_cap.number_of_credential_slots:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="credential_slot_out_of_range",
            translation_placeholders={
                "credential_type": cred_type_str,
                "max_slot": str(type_cap.number_of_credential_slots),
            },
        )

    status = await node.access_control.set_credential(
        user_id, credential_type, credential_slot, credential_data
    )
    _raise_on_set_credential_error(status)

    return SetCredentialReturn(
        credential_slot=credential_slot,
        user_id=user_id,
    )


async def async_delete_credential(
    node: Node,
    user_id: int,
    credential_type: UserCredentialType,
    credential_slot: int,
) -> None:
    """Delete a single credential."""
    if not await node.access_control.is_supported():
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="access_control_not_supported",
        )

    status = await node.access_control.delete_credential(
        user_id, credential_type, credential_slot
    )
    _raise_on_set_credential_error(status)


async def async_delete_all_credentials(node: Node, user_id: int) -> None:
    """Delete all credentials for a user."""
    if not await node.access_control.is_supported():
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="access_control_not_supported",
        )

    credentials = await node.access_control.get_credentials_cached(user_id)
    # Until Z-Wave JS exposes a bulk-delete API, we have to delete credentials one at a time.
    # Use return_exceptions=True so a single failure does not cancel the remaining deletions
    # and leave the user with a partially-deleted credential set.
    results = await asyncio.gather(
        *(
            node.access_control.delete_credential(user_id, cred.type, cred.slot)
            for cred in credentials
        ),
        return_exceptions=True,
    )
    failures: list[tuple[int, BaseException]] = []
    for cred, result in zip(credentials, results, strict=True):
        if isinstance(result, BaseException):
            failures.append((cred.slot, result))
            continue
        try:
            _raise_on_set_credential_error(result)
        except HomeAssistantError as err:
            failures.append((cred.slot, err))

    if not failures:
        return
    for slot, failure in failures:
        _LOGGER.warning(
            "Failed to delete credential at slot %s for user %s: %s",
            slot,
            user_id,
            failure,
        )
    if len(failures) == 1:
        raise failures[0][1]
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="delete_all_credentials_partial_failure",
        translation_placeholders={
            "user_id": str(user_id),
            "failed_count": str(len(failures)),
        },
    )
