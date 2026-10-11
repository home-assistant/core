"""Constants for the Yale Access Bluetooth integration."""

from yalexs_ble import KEYPAD_MASTER_CODE_SLOT

DOMAIN = "yalexs_ble"

CONF_LOCAL_NAME = "local_name"
CONF_KEY = "key"
CONF_SLOT = "slot"
CONF_ALWAYS_CONNECTED = "always_connected"
CONF_MASTER_CODE_NAME = "master_code_name"

DEVICE_TIMEOUT = 55

ATTR_CREDENTIAL_DATA = "credential_data"
ATTR_CREDENTIAL_INDEX = "credential_index"
ATTR_CREDENTIAL_TYPE = "credential_type"

CREDENTIAL_TYPE_PIN = "pin"

MIN_PIN_SLOT = 1
MAX_PIN_SLOT = 250

ACTIVITY_HOLD_SECONDS = 2.0
HA_OPERATION_TIMEOUT_SECONDS = 30

EVENT_LOCK_ACTIVITY = "yalexs_ble_lock_activity"
ATTR_SOURCE = "source"
ATTR_SLOT = "slot"
ATTR_MASTER_CODE = "master_code"

SOURCE_PIN = "pin"

CHANGED_BY_BY_SOURCE = {
    "manual": "Manual",
    "auto_lock": "Auto lock",
    "remote": "Remote",
}


def changed_by_for_source(
    source: str, slot: int | None, name: str | None, master_code_name: str | None
) -> str | None:
    """Return who operated the lock for an activity source, slot and credential name."""
    if source == SOURCE_PIN:
        if slot == KEYPAD_MASTER_CODE_SLOT:
            return master_code_name or "Master code"
        if slot is None:
            return "Keypad"
        return name or f"Keypad slot {slot}"
    return CHANGED_BY_BY_SOURCE.get(source)


def activity_signal(address: str) -> str:
    """Return the dispatcher signal for lock activities of a lock."""
    return f"{DOMAIN}_activity_{address}"
