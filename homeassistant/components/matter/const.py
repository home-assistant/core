"""Constants for the Matter integration."""

import logging

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
ATTR_USER_INDEX = "user_index"
ATTR_USER_NAME = "user_name"
ATTR_USER_UNIQUE_ID = "user_unique_id"
ATTR_USER_STATUS = "user_status"
ATTR_USER_TYPE = "user_type"
ATTR_CREDENTIAL_RULE = "credential_rule"
ATTR_SUPPORTS_USER_MGMT = "supports_user_management"
ATTR_MAX_USERS = "max_users"
ATTR_MAX_PIN_USERS = "max_pin_users"
ATTR_MAX_RFID_USERS = "max_rfid_users"
ATTR_MAX_CREDENTIALS_PER_USER = "max_credentials_per_user"

# Magic values
CLEAR_ALL_INDEX = 0xFFFE  # Matter spec: pass to ClearUser/ClearCredential to clear all

# Timed request timeout (used by all lock commands that modify state)
LOCK_TIMED_REQUEST_TIMEOUT_MS = 1000

# Service names
SERVICE_SET_LOCK_USER = "set_lock_user"
SERVICE_CLEAR_LOCK_USER = "clear_lock_user"
SERVICE_GET_LOCK_INFO = "get_lock_info"
SERVICE_GET_LOCK_USERS = "get_lock_users"
SERVICE_SET_LOCK_CREDENTIAL = "set_lock_credential"
SERVICE_CLEAR_LOCK_CREDENTIAL = "clear_lock_credential"
SERVICE_GET_LOCK_CREDENTIAL_STATUS = "get_lock_credential_status"

# Credential field keys
ATTR_CREDENTIAL_TYPE = "credential_type"
ATTR_CREDENTIAL_INDEX = "credential_index"
ATTR_CREDENTIAL_DATA = "credential_data"

# Error code constants
ERR_INVALID_CREDENTIAL_DATA = "invalid_credential_data"
ERR_CREDENTIAL_TYPE_NOT_SUPPORTED = "credential_type_not_supported"
ERR_SET_CREDENTIAL_FAILED = "set_credential_failed"

# Credential type strings
CRED_TYPE_PIN = "pin"
CRED_TYPE_RFID = "rfid"
CRED_TYPE_FINGERPRINT = "fingerprint"
CRED_TYPE_FACE = "face"

# Door lock operation source mapping (Matter DoorLock OperationSourceEnum)
DOOR_LOCK_OPERATION_SOURCE: dict[int, str] = {
    0: "Unspecified",
    1: "Manual",  # [Optional]
    2: "Proprietary Remote",  # [Optional]
    3: "Keypad",  # [Optional]
    4: "Auto",  # [Optional]
    5: "Button",  # [Optional]
    6: "Schedule",  # [HDSCH]
    7: "Remote",  # [M]
    8: "RFID",  # [RID]
    9: "Biometric",  # [USR]
    10: "Aliro",  # [Aliro]
}

# User status mapping (Matter DoorLock UserStatusEnum)
USER_STATUS_MAP: dict[int, str] = {
    0: "available",
    1: "occupied_enabled",
    3: "occupied_disabled",
}
USER_STATUS_REVERSE_MAP: dict[str, int] = {v: k for k, v in USER_STATUS_MAP.items()}

# User type mapping (Matter DoorLock UserTypeEnum)
USER_TYPE_MAP: dict[int, str] = {
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
USER_TYPE_REVERSE_MAP: dict[str, int] = {v: k for k, v in USER_TYPE_MAP.items()}

# Credential type mapping (Matter DoorLock CredentialTypeEnum)
CREDENTIAL_TYPE_MAP: dict[int, str] = {
    0: "programming_pin",
    1: CRED_TYPE_PIN,
    2: CRED_TYPE_RFID,
    3: CRED_TYPE_FINGERPRINT,
    4: "finger_vein",
    5: CRED_TYPE_FACE,
    6: "aliro_credential_issuer_key",
    7: "aliro_evictable_endpoint_key",
    8: "aliro_non_evictable_endpoint_key",
}

# Credential rule mapping (Matter DoorLock CredentialRuleEnum)
CREDENTIAL_RULE_MAP: dict[int, str] = {
    0: "single",
    1: "dual",
    2: "tri",
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
SET_CREDENTIAL_STATUS_MAP: dict[int, str] = {
    0: "success",
    1: "failure",
    2: "duplicate",
    3: "occupied",
}
