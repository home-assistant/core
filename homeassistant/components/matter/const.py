"""Constants for the Matter integration."""

import logging

from chip.clusters import Objects as clusters

ADDON_SLUG = "core_matter_server"

CONF_INTEGRATION_CREATED_ADDON = "integration_created_addon"
CONF_USE_ADDON = "use_addon"

DOMAIN = "matter"
LOGGER = logging.getLogger(__package__)

# prefixes to identify device identifier id types
ID_TYPE_DEVICE_ID = "deviceid"
ID_TYPE_SERIAL = "serial"

FEATUREMAP_ATTRIBUTE_ID = 65532

# --- Lock domain constants ---

# Shared field keys
ATTR_CREDENTIAL_RULE = "credential_rule"
ATTR_MAX_CREDENTIALS_PER_USER = "max_credentials_per_user"
ATTR_MAX_PIN_USERS = "max_pin_users"
ATTR_MAX_RFID_USERS = "max_rfid_users"
ATTR_MAX_USERS = "max_users"
ATTR_SUPPORTS_USER_MGMT = "supports_user_management"
ATTR_USER_INDEX = "user_index"
ATTR_USER_NAME = "user_name"
ATTR_USER_STATUS = "user_status"
ATTR_USER_TYPE = "user_type"
ATTR_USER_UNIQUE_ID = "user_unique_id"

# Magic values
CLEAR_ALL_INDEX = 0xFFFE  # Matter spec: pass to ClearUser/ClearCredential to clear all

# Timed request timeout (used by all lock commands that modify state)
LOCK_TIMED_REQUEST_TIMEOUT_MS = 10000

# Service names
SERVICE_CLEAR_LOCK_CREDENTIAL = "clear_lock_credential"
SERVICE_CLEAR_LOCK_USER = "clear_lock_user"
SERVICE_GET_LOCK_CREDENTIAL_STATUS = "get_lock_credential_status"
SERVICE_GET_LOCK_INFO = "get_lock_info"
SERVICE_GET_LOCK_USERS = "get_lock_users"
SERVICE_SET_LOCK_CREDENTIAL = "set_lock_credential"
SERVICE_SET_LOCK_USER = "set_lock_user"

# Credential field keys
ATTR_CREDENTIAL_DATA = "credential_data"
ATTR_CREDENTIAL_INDEX = "credential_index"
ATTR_CREDENTIAL_TYPE = "credential_type"

# Error code constants
ERR_CREDENTIAL_TYPE_NOT_SUPPORTED = "credential_type_not_supported"
ERR_INVALID_CREDENTIAL_DATA = "invalid_credential_data"
ERR_SET_CREDENTIAL_FAILED = "set_credential_failed"

# Credential type strings
CRED_TYPE_FACE = "face"
CRED_TYPE_FINGERPRINT = "fingerprint"
CRED_TYPE_PIN = "pin"
CRED_TYPE_RFID = "rfid"

# Door lock operation source mapping (Matter DoorLock OperationSourceEnum)
_OperationSource = clusters.DoorLock.Enums.OperationSourceEnum
DOOR_LOCK_OPERATION_SOURCE: dict[int, str] = {
    _OperationSource.kUnspecified: "Unspecified",
    _OperationSource.kManual: "Manual",
    _OperationSource.kProprietaryRemote: "Proprietary Remote",
    _OperationSource.kKeypad: "Keypad",
    _OperationSource.kAuto: "Auto",
    _OperationSource.kButton: "Button",
    _OperationSource.kSchedule: "Schedule",
    _OperationSource.kRemote: "Remote",
    _OperationSource.kRfid: "RFID",
    _OperationSource.kBiometric: "Biometric",
    _OperationSource.kAliro: "Aliro",
}

# User status mapping (Matter DoorLock UserStatusEnum)
_UserStatus = clusters.DoorLock.Enums.UserStatusEnum
USER_STATUS_MAP: dict[int, str] = {
    _UserStatus.kAvailable: "available",
    _UserStatus.kOccupiedEnabled: "occupied_enabled",
    _UserStatus.kOccupiedDisabled: "occupied_disabled",
}
USER_STATUS_REVERSE_MAP: dict[str, int] = {v: k for k, v in USER_STATUS_MAP.items()}

# User type mapping (Matter DoorLock UserTypeEnum)
_UserType = clusters.DoorLock.Enums.UserTypeEnum
USER_TYPE_MAP: dict[int, str] = {
    _UserType.kUnrestrictedUser: "unrestricted_user",
    _UserType.kYearDayScheduleUser: "year_day_schedule_user",
    _UserType.kWeekDayScheduleUser: "week_day_schedule_user",
    _UserType.kProgrammingUser: "programming_user",
    _UserType.kNonAccessUser: "non_access_user",
    _UserType.kForcedUser: "forced_user",
    _UserType.kDisposableUser: "disposable_user",
    _UserType.kExpiringUser: "expiring_user",
    _UserType.kScheduleRestrictedUser: "schedule_restricted_user",
    _UserType.kRemoteOnlyUser: "remote_only_user",
}
USER_TYPE_REVERSE_MAP: dict[str, int] = {v: k for k, v in USER_TYPE_MAP.items()}

# Credential type mapping (Matter DoorLock CredentialTypeEnum)
_CredentialType = clusters.DoorLock.Enums.CredentialTypeEnum
CREDENTIAL_TYPE_MAP: dict[int, str] = {
    _CredentialType.kProgrammingPIN: "programming_pin",
    _CredentialType.kPin: CRED_TYPE_PIN,
    _CredentialType.kRfid: CRED_TYPE_RFID,
    _CredentialType.kFingerprint: CRED_TYPE_FINGERPRINT,
    _CredentialType.kFingerVein: "finger_vein",
    _CredentialType.kFace: CRED_TYPE_FACE,
    _CredentialType.kAliroCredentialIssuerKey: "aliro_credential_issuer_key",
    _CredentialType.kAliroEvictableEndpointKey: "aliro_evictable_endpoint_key",
    _CredentialType.kAliroNonEvictableEndpointKey: "aliro_non_evictable_endpoint_key",
}

# Credential rule mapping (Matter DoorLock CredentialRuleEnum)
_CredentialRule = clusters.DoorLock.Enums.CredentialRuleEnum
CREDENTIAL_RULE_MAP: dict[int, str] = {
    _CredentialRule.kSingle: "single",
    _CredentialRule.kDual: "dual",
    _CredentialRule.kTri: "tri",
}
CREDENTIAL_RULE_REVERSE_MAP: dict[str, int] = {
    v: k for k, v in CREDENTIAL_RULE_MAP.items()
}

# Reverse mapping for credential types (str -> int)
CREDENTIAL_TYPE_REVERSE_MAP: dict[str, int] = {
    v: k for k, v in CREDENTIAL_TYPE_MAP.items()
}

# Credential types allowed in set/clear services (excludes programming_pin, aliro_*)
SERVICE_CREDENTIAL_TYPES = [
    CRED_TYPE_PIN,
    CRED_TYPE_RFID,
    CRED_TYPE_FINGERPRINT,
    "finger_vein",
    CRED_TYPE_FACE,
]

# SetCredential response status mapping (Matter DlStatus)
_DlStatus = clusters.DoorLock.Enums.DlStatus
SET_CREDENTIAL_STATUS_MAP: dict[int, str] = {
    _DlStatus.kSuccess: "success",
    _DlStatus.kFailure: "failure",
    _DlStatus.kDuplicate: "duplicate",
    _DlStatus.kOccupied: "occupied",
}
