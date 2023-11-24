"""Constants for the loqed integration."""


DOMAIN = "loqed"
CONF_CLOUDHOOK_URL = "cloudhook_url"

BATTERY_TYPES = ["alkaline", "nickel_metal_hydride", "lithium", "unknown"]

EVENT_TYPES = [
    "go_to_state_instantopen_open",
    "go_to_state_instantopen_latch",
    "go_to_state_manual_unlock_remote_open",
    "go_to_state_manual_unlock_ble_open",
    "go_to_state_manual_unlock_via_outside_module_pin",
    "go_to_state_manual_unlock_via_outside_module_button",
    "go_to_state_manual_lock_ble_latch",
    "go_to_state_manual_lock_ble_night_lock",
    "go_to_state_manual_lock_remote_latch",
    "go_to_state_manual_lock_remote_night_lock",
    "go_to_state_twist_assist_open",
    "go_to_state_twist_assist_latch",
    "go_to_state_twist_assist_lock",
    "go_to_state_touch_to_lock",
    "state_changed_open",
    "state_changed_latch",
    "state_changed_night_lock",
    "state_changed_unknown",
    "motor_stall",
    "state_changed_open_remote",
    "state_changed_latch_remote",
    "state_changed_night_lock_remote",
]
