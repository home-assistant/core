"""Constant values for OpenEVSE."""

DOMAIN = "openevse"
BRAND = "OpenEVSE"

CONF_UNIQUE_ID = "unique_id"
CONF_BASE_TOPIC = "base_topic"
CONF_CONFIG_URL = "config_url"

STATES = {
    0: "unknown",
    1: "not_connected",
    2: "connected",
    3: "charging",
    4: "vent_required",
    5: "diod_check_failed",
    6: "gfci_fault",
    7: "no_ground",
    8: "stuck_relay",
    9: "gfci_self_test_failure",
    10: "over_temperature",
    254: "sleeping",
    255: "disabled",
}

DEVICE_SUGGESTED_AREA = "Garage"
