"""Access-control helpers for Z-Wave JS credential management.

Provides business logic for user/credential CRUD, capability queries,
auto-find logic, and validation.
"""

from __future__ import annotations

from typing import TypedDict

from zwave_js_server.const import SupervisionStatus
from zwave_js_server.const.command_class.access_control import (
    UserCredentialRule,
    UserCredentialType,
    UserCredentialUserType,
)
from zwave_js_server.model.access_control import SetUserOptions
from zwave_js_server.model.node import Node
from zwave_js_server.model.value import SupervisionResult

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


def _raise_on_supervision_fail(
    result: SupervisionResult | None, translation_key: str
) -> None:
    """Raise HomeAssistantError if the supervision result indicates failure.

    A ``None`` result means the device did not report supervision (treated as
    success-by-omission). ``WORKING`` is reported while a long-running command
    is still in progress — it is never a final state once awaited, so it is
    treated as success here. ``NO_SUPPORT`` and ``FAIL`` both indicate the
    device rejected or cannot handle the command.
    """
    if result is None:
        return
    if result.status in (SupervisionStatus.FAIL, SupervisionStatus.NO_SUPPORT):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
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


class CredentialReference(TypedDict):
    """A credential reference within a user entry."""

    type: str
    slot: int


class UserEntry(TypedDict):
    """A single user entry in the users list."""

    user_index: int
    user_name: str | None
    active: bool
    user_type: str
    credential_rule: str | None
    credentials: list[CredentialReference]


class UsersResult(TypedDict):
    """Return type for get_users."""

    max_users: int
    users: list[UserEntry]


class SetUserResult(TypedDict):
    """Return type for set_user."""

    user_index: int


class SetCredentialResult(TypedDict):
    """Return type for set_credential."""

    credential_slot: int
    user_index: int


class CredentialStatusResult(TypedDict):
    """Return type for get_credential_status."""

    credential_exists: bool
    user_index: int
    credential_type: str
    credential_slot: int


# --- Business logic functions ---


async def async_get_credential_capabilities(
    node: Node,
) -> CredentialCapabilitiesResult:
    """Query access-control capabilities for the node."""
    supported = await node.access_control.async_is_supported()
    if not supported:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="access_control_not_supported",
        )

    user_caps = await node.access_control.async_get_user_capabilities_cached()
    cred_caps = await node.access_control.async_get_credential_capabilities_cached()

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
        max_user_name_length=user_caps.max_user_name_length,
        supported_credential_rules=[
            CREDENTIAL_RULE_MAP[cr]
            for cr in user_caps.supported_credential_rules
            if cr in CREDENTIAL_RULE_MAP
        ],
        supported_credential_types=supported_credential_types,
    )


async def async_get_users(node: Node) -> UsersResult:
    """List all users with their credential references."""
    supported = await node.access_control.async_is_supported()
    if not supported:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="access_control_not_supported",
        )

    user_caps = await node.access_control.async_get_user_capabilities_cached()
    users = await node.access_control.async_get_users_cached()

    user_list: list[UserEntry] = []
    for user in users:
        credentials_data = await node.access_control.async_get_credentials_cached(
            user.user_id
        )
        credentials: list[CredentialReference] = [
            CredentialReference(
                type=CREDENTIAL_TYPE_MAP.get(cred.type, str(cred.type)),
                slot=cred.slot,
            )
            for cred in credentials_data
        ]
        user_list.append(
            UserEntry(
                user_index=user.user_id,
                user_name=user.user_name,
                active=user.active,
                user_type=USER_TYPE_MAP.get(user.user_type, str(user.user_type)),
                credential_rule=(
                    CREDENTIAL_RULE_MAP.get(user.credential_rule)
                    if user.credential_rule is not None
                    else None
                ),
                credentials=credentials,
            )
        )

    return UsersResult(
        max_users=user_caps.max_users,
        users=user_list,
    )


async def async_set_user(
    node: Node,
    user_index: int | None = None,
    user_name: str | None = None,
    user_type: UserCredentialUserType | None = None,
    credential_rule: UserCredentialRule | None = None,
    active: bool | None = None,
) -> SetUserResult:
    """Create or update an access-control user. Returns the allocated user_index."""
    supported = await node.access_control.async_is_supported()
    if not supported:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="access_control_not_supported",
        )

    # Auto-find first available user slot
    if user_index is None:
        user_caps = await node.access_control.async_get_user_capabilities_cached()
        users = await node.access_control.async_get_users_cached()
        used_ids = {u.user_id for u in users}
        user_index = next(
            (i for i in range(1, user_caps.max_users + 1) if i not in used_ids),
            None,
        )
        if user_index is None:
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

    result = await node.access_control.async_set_user(user_index, options)
    _raise_on_supervision_fail(result, "set_user_rejected")
    return SetUserResult(user_index=user_index)


async def async_clear_user(node: Node, user_index: int) -> None:
    """Delete a single access-control user."""
    result = await node.access_control.async_delete_user(user_index)
    _raise_on_supervision_fail(result, "clear_user_rejected")


async def async_clear_all_users(node: Node) -> None:
    """Delete all access-control users."""
    result = await node.access_control.async_delete_all_users()
    _raise_on_supervision_fail(result, "clear_all_users_rejected")


async def async_set_credential(
    node: Node,
    user_index: int,
    credential_type: UserCredentialType,
    credential_data: str,
    credential_slot: int | None = None,
) -> SetCredentialResult:
    """Add or update a credential (PIN/password only).

    user_index must refer to an existing user. To create a new user, call
    async_set_user first, then pass the returned user_index here. This service
    does not create or modify users.
    """
    supported = await node.access_control.async_is_supported()
    if not supported:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="access_control_not_supported",
        )

    # Auto-find first available credential slot if not provided
    if credential_slot is None:
        cred_caps = await node.access_control.async_get_credential_capabilities_cached()
        type_cap = cred_caps.supported_credential_types.get(credential_type)
        if type_cap is None:
            cred_type_str = CREDENTIAL_TYPE_MAP.get(
                credential_type, str(credential_type)
            )
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="credential_type_not_supported",
                translation_placeholders={"credential_type": cred_type_str},
            )
        existing = await node.access_control.async_get_credentials_cached(user_index)
        used_slots = {c.slot for c in existing if c.type == credential_type}
        credential_slot = next(
            (
                s
                for s in range(1, type_cap.number_of_credential_slots + 1)
                if s not in used_slots
            ),
            None,
        )
        if credential_slot is None:
            cred_type_str = CREDENTIAL_TYPE_MAP.get(
                credential_type, str(credential_type)
            )
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_available_credential_slots",
                translation_placeholders={"credential_type": cred_type_str},
            )

    result = await node.access_control.async_set_credential(
        user_index, credential_type, credential_slot, credential_data
    )
    _raise_on_supervision_fail(result, "set_credential_rejected")

    return SetCredentialResult(
        credential_slot=credential_slot,
        user_index=user_index,
    )


async def async_clear_credential(
    node: Node,
    user_index: int,
    credential_type: UserCredentialType,
    credential_slot: int,
) -> None:
    """Delete a single credential."""
    result = await node.access_control.async_delete_credential(
        user_index, credential_type, credential_slot
    )
    _raise_on_supervision_fail(result, "clear_credential_rejected")


async def async_clear_all_credentials(node: Node, user_index: int) -> None:
    """Delete all credentials for a user."""
    credentials = await node.access_control.async_get_credentials_cached(user_index)
    for cred in credentials:
        result = await node.access_control.async_delete_credential(
            user_index, cred.type, cred.slot
        )
        _raise_on_supervision_fail(result, "clear_credential_rejected")


async def async_get_credential_status(
    node: Node,
    user_index: int,
    credential_type: UserCredentialType,
    credential_slot: int,
) -> CredentialStatusResult:
    """Query the status of a credential slot."""
    credential = await node.access_control.async_get_credential_cached(
        user_index, credential_type, credential_slot
    )

    return CredentialStatusResult(
        credential_exists=credential is not None,
        user_index=user_index,
        credential_type=CREDENTIAL_TYPE_MAP.get(credential_type, str(credential_type)),
        credential_slot=credential_slot,
    )
