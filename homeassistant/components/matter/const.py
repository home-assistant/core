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

# Event names
EVENT_LOCK_OPERATION = f"{DOMAIN}_lock_operation"
EVENT_LOCK_DISPOSABLE_USER_DELETED = f"{DOMAIN}_lock_disposable_user_deleted"

# Shared field keys (used across lock.py and api_lock.py)
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

# Credential field keys
ATTR_PIN_CODE = "pin_code"

# Error codes
ERR_LOCK_NOT_FOUND = "lock_not_found"
ERR_USR_NOT_SUPPORTED = "usr_not_supported"
ERR_USER_ALREADY_EXISTS = "user_already_exists"
ERR_USER_NOT_FOUND = "user_not_found"
ERR_NO_AVAILABLE_SLOTS = "no_available_slots"
ERR_INVALID_PIN_CODE = "invalid_pin_code"
ERR_CREDENTIAL_NOT_SUPPORTED = "credential_not_supported"
ERR_NO_AVAILABLE_CREDENTIAL_SLOTS = "no_available_credential_slots"

# Service names
SERVICE_SET_LOCK_USERCODE = "set_lock_usercode"
SERVICE_CLEAR_LOCK_USERCODE = "clear_lock_usercode"
SERVICE_SET_LOCK_USER = "set_lock_user"
SERVICE_CLEAR_LOCK_USER = "clear_lock_user"
SERVICE_GET_LOCK_INFO = "get_lock_info"
SERVICE_GET_LOCK_USERS = "get_lock_users"

# Service field keys
ATTR_CODE_SLOT = "code_slot"
ATTR_USERCODE = "usercode"

# SetCredential status mapping (Matter DlStatus)
SET_CREDENTIAL_STATUS_MAP: dict[int, str] = {
    0: "success",
    1: "failure",
    2: "duplicate",
    3: "occupied",
}

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

# Door lock operation type mapping (Matter DoorLock LockOperationTypeEnum)
DOOR_LOCK_OPERATION_TYPE: dict[int, str] = {
    0: "lock",
    1: "unlock",
    2: "non_access_user_event",
    3: "forced_user_event",
    4: "unlatch",
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
