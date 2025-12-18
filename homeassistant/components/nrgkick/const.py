"""Constants for the NRGkick integration."""

from typing import Final

DOMAIN: Final = "nrgkick"

# Configuration.
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Default values.
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 300

# Note: API Endpoints are in the nrgkick-api library.
# Import from nrgkick_api if needed: from nrgkick_api import ENDPOINT_INFO, ...

# Charging Status Constants.
# These map to the numeric values returned by the API's status field.
STATUS_UNKNOWN: Final = 0
STATUS_STANDBY: Final = 1
STATUS_CONNECTED: Final = 2
STATUS_CHARGING: Final = 3
STATUS_ERROR: Final = 6
STATUS_WAKEUP: Final = 7

# Human-readable status mapping for the status sensor.
# Values are translation keys that match translations/<lang>.json
STATUS_MAP: Final = {
    STATUS_UNKNOWN: "unknown",
    STATUS_STANDBY: "standby",
    STATUS_CONNECTED: "connected",
    STATUS_CHARGING: "charging",
    STATUS_ERROR: "error",
    STATUS_WAKEUP: "wakeup",
}

# RCD Trigger Status Constants.
RCD_NO_FAULT: Final = 0
RCD_AC_30MA_FAULT: Final = 1
RCD_AC_60MA_FAULT: Final = 2
RCD_AC_150MA_FAULT: Final = 3
RCD_DC_POSITIVE_6MA_FAULT: Final = 4
RCD_DC_NEGATIVE_6MA_FAULT: Final = 5

# Human-readable RCD trigger mapping.
# Values are translation keys that match translations/<lang>.json
RCD_TRIGGER_MAP: Final = {
    RCD_NO_FAULT: "no_fault",
    RCD_AC_30MA_FAULT: "ac_30ma_fault",
    RCD_AC_60MA_FAULT: "ac_60ma_fault",
    RCD_AC_150MA_FAULT: "ac_150ma_fault",
    RCD_DC_POSITIVE_6MA_FAULT: "dc_positive_6ma_fault",
    RCD_DC_NEGATIVE_6MA_FAULT: "dc_negative_6ma_fault",
}

# Warning Code Constants.
WARNING_NO_WARNING: Final = 0
WARNING_NO_PE: Final = 1
WARNING_BLACKOUT_PROTECTION: Final = 2
WARNING_ENERGY_LIMIT_REACHED: Final = 3
WARNING_EV_DOES_NOT_COMPLY_STANDARD: Final = 4
WARNING_UNSUPPORTED_CHARGING_MODE: Final = 5
WARNING_NO_ATTACHMENT_DETECTED: Final = 6
WARNING_NO_COMM_WITH_TYPE2_ATTACHMENT: Final = 7
WARNING_INCREASED_TEMPERATURE: Final = 16
WARNING_INCREASED_HOUSING_TEMPERATURE: Final = 17
WARNING_INCREASED_ATTACHMENT_TEMPERATURE: Final = 18
WARNING_INCREASED_DOMESTIC_PLUG_TEMPERATURE: Final = 19

# Human-readable warning code mapping.
# Values are translation keys that match translations/<lang>.json
WARNING_CODE_MAP: Final = {
    WARNING_NO_WARNING: "no_warning",
    WARNING_NO_PE: "no_pe",
    WARNING_BLACKOUT_PROTECTION: "blackout_protection",
    WARNING_ENERGY_LIMIT_REACHED: "energy_limit_reached",
    WARNING_EV_DOES_NOT_COMPLY_STANDARD: "ev_does_not_comply_standard",
    WARNING_UNSUPPORTED_CHARGING_MODE: "unsupported_charging_mode",
    WARNING_NO_ATTACHMENT_DETECTED: "no_attachment_detected",
    WARNING_NO_COMM_WITH_TYPE2_ATTACHMENT: "no_comm_with_type2_attachment",
    WARNING_INCREASED_TEMPERATURE: "increased_temperature",
    WARNING_INCREASED_HOUSING_TEMPERATURE: "increased_housing_temperature",
    WARNING_INCREASED_ATTACHMENT_TEMPERATURE: "increased_attachment_temperature",
    WARNING_INCREASED_DOMESTIC_PLUG_TEMPERATURE: "increased_domestic_plug_temperature",
}

# Error Code Constants.
ERROR_NO_ERROR: Final = 0
ERROR_GENERAL_ERROR: Final = 1
ERROR_32A_ATTACHMENT_ON_16A_UNIT: Final = 2
ERROR_VOLTAGE_DROP_DETECTED: Final = 3
ERROR_UNPLUG_DETECTION_TRIGGERED: Final = 4
ERROR_TYPE2_NOT_AUTHORIZED: Final = 5
ERROR_RESIDUAL_CURRENT_DETECTED: Final = 16
ERROR_CP_SIGNAL_VOLTAGE_ERROR: Final = 32
ERROR_CP_SIGNAL_IMPERMISSIBLE: Final = 33
ERROR_EV_DIODE_FAULT: Final = 34
ERROR_PE_SELF_TEST_FAILED: Final = 48
ERROR_RCD_SELF_TEST_FAILED: Final = 49
ERROR_RELAY_SELF_TEST_FAILED: Final = 50
ERROR_PE_AND_RCD_SELF_TEST_FAILED: Final = 51
ERROR_PE_AND_RELAY_SELF_TEST_FAILED: Final = 52
ERROR_RCD_AND_RELAY_SELF_TEST_FAILED: Final = 53
ERROR_PE_AND_RCD_AND_RELAY_SELF_TEST_FAILED: Final = 54
ERROR_SUPPLY_VOLTAGE_ERROR: Final = 64
ERROR_PHASE_SHIFT_ERROR: Final = 65
ERROR_OVERVOLTAGE_DETECTED: Final = 66
ERROR_UNDERVOLTAGE_DETECTED: Final = 67
ERROR_OVERVOLTAGE_WITHOUT_PE_DETECTED: Final = 68
ERROR_UNDERVOLTAGE_WITHOUT_PE_DETECTED: Final = 69
ERROR_UNDERFREQUENCY_DETECTED: Final = 70
ERROR_OVERFREQUENCY_DETECTED: Final = 71
ERROR_UNKNOWN_FREQUENCY_TYPE: Final = 72
ERROR_UNKNOWN_GRID_TYPE: Final = 73
ERROR_GENERAL_OVERTEMPERATURE: Final = 80
ERROR_HOUSING_OVERTEMPERATURE: Final = 81
ERROR_ATTACHMENT_OVERTEMPERATURE: Final = 82
ERROR_DOMESTIC_PLUG_OVERTEMPERATURE: Final = 83

# Human-readable error code mapping.
# Values are translation keys that match translations/<lang>.json
ERROR_CODE_MAP: Final = {
    ERROR_NO_ERROR: "no_error",
    ERROR_GENERAL_ERROR: "general_error",
    ERROR_32A_ATTACHMENT_ON_16A_UNIT: "32a_attachment_on_16a_unit",
    ERROR_VOLTAGE_DROP_DETECTED: "voltage_drop_detected",
    ERROR_UNPLUG_DETECTION_TRIGGERED: "unplug_detection_triggered",
    ERROR_TYPE2_NOT_AUTHORIZED: "type2_not_authorized",
    ERROR_RESIDUAL_CURRENT_DETECTED: "residual_current_detected",
    ERROR_CP_SIGNAL_VOLTAGE_ERROR: "cp_signal_voltage_error",
    ERROR_CP_SIGNAL_IMPERMISSIBLE: "cp_signal_impermissible",
    ERROR_EV_DIODE_FAULT: "ev_diode_fault",
    ERROR_PE_SELF_TEST_FAILED: "pe_self_test_failed",
    ERROR_RCD_SELF_TEST_FAILED: "rcd_self_test_failed",
    ERROR_RELAY_SELF_TEST_FAILED: "relay_self_test_failed",
    ERROR_PE_AND_RCD_SELF_TEST_FAILED: "pe_and_rcd_self_test_failed",
    ERROR_PE_AND_RELAY_SELF_TEST_FAILED: "pe_and_relay_self_test_failed",
    ERROR_RCD_AND_RELAY_SELF_TEST_FAILED: "rcd_and_relay_self_test_failed",
    ERROR_PE_AND_RCD_AND_RELAY_SELF_TEST_FAILED: (
        "pe_and_rcd_and_relay_self_test_failed"
    ),
    ERROR_SUPPLY_VOLTAGE_ERROR: "supply_voltage_error",
    ERROR_PHASE_SHIFT_ERROR: "phase_shift_error",
    ERROR_OVERVOLTAGE_DETECTED: "overvoltage_detected",
    ERROR_UNDERVOLTAGE_DETECTED: "undervoltage_detected",
    ERROR_OVERVOLTAGE_WITHOUT_PE_DETECTED: "overvoltage_without_pe_detected",
    ERROR_UNDERVOLTAGE_WITHOUT_PE_DETECTED: "undervoltage_without_pe_detected",
    ERROR_UNDERFREQUENCY_DETECTED: "underfrequency_detected",
    ERROR_OVERFREQUENCY_DETECTED: "overfrequency_detected",
    ERROR_UNKNOWN_FREQUENCY_TYPE: "unknown_frequency_type",
    ERROR_UNKNOWN_GRID_TYPE: "unknown_grid_type",
    ERROR_GENERAL_OVERTEMPERATURE: "general_overtemperature",
    ERROR_HOUSING_OVERTEMPERATURE: "housing_overtemperature",
    ERROR_ATTACHMENT_OVERTEMPERATURE: "attachment_overtemperature",
    ERROR_DOMESTIC_PLUG_OVERTEMPERATURE: "domestic_plug_overtemperature",
}

# Relay State Constants.
# Bit 0: N, Bit 1: L1, Bit 2: L2, Bit 3: L3
RELAY_NO_RELAY: Final = 0
RELAY_N: Final = 1
RELAY_L1: Final = 2
RELAY_N_L1: Final = 3
RELAY_L2: Final = 4
RELAY_N_L2: Final = 5
RELAY_L1_L2: Final = 6
RELAY_N_L1_L2: Final = 7
RELAY_L3: Final = 8
RELAY_N_L3: Final = 9
RELAY_L1_L3: Final = 10
RELAY_N_L1_L3: Final = 11
RELAY_L2_L3: Final = 12
RELAY_N_L2_L3: Final = 13
RELAY_L1_L2_L3: Final = 14
RELAY_N_L1_L2_L3: Final = 15

# Human-readable relay state mapping.
# Values are translation keys that match translations/<lang>.json
RELAY_STATE_MAP: Final = {
    RELAY_NO_RELAY: "no_relay",
    RELAY_N: "n",
    RELAY_L1: "l1",
    RELAY_N_L1: "n_l1",
    RELAY_L2: "l2",
    RELAY_N_L2: "n_l2",
    RELAY_L1_L2: "l1_l2",
    RELAY_N_L1_L2: "n_l1_l2",
    RELAY_L3: "l3",
    RELAY_N_L3: "n_l3",
    RELAY_L1_L3: "l1_l3",
    RELAY_N_L1_L3: "n_l1_l3",
    RELAY_L2_L3: "l2_l3",
    RELAY_N_L2_L3: "n_l2_l3",
    RELAY_L1_L2_L3: "l1_l2_l3",
    RELAY_N_L1_L2_L3: "n_l1_l2_l3",
}

# Connector Type Constants.
CONNECTOR_TYPE_UNKNOWN: Final = 0
CONNECTOR_TYPE_CEE: Final = 1
CONNECTOR_TYPE_DOMESTIC: Final = 2
CONNECTOR_TYPE_TYPE2: Final = 3
CONNECTOR_TYPE_WALL: Final = 4
CONNECTOR_TYPE_AUS: Final = 5

# Human-readable connector type mapping.
# Values are translation keys that match translations/<lang>.json
CONNECTOR_TYPE_MAP: Final = {
    CONNECTOR_TYPE_UNKNOWN: "unknown",
    CONNECTOR_TYPE_CEE: "cee",
    CONNECTOR_TYPE_DOMESTIC: "domestic",
    CONNECTOR_TYPE_TYPE2: "type2",
    CONNECTOR_TYPE_WALL: "wall",
    CONNECTOR_TYPE_AUS: "aus",
}

# Grid Phases Constants.
# Bit 0: L1, Bit 1: L2, Bit 2: L3
GRID_PHASES_UNKNOWN: Final = 0
GRID_PHASES_L1: Final = 1
GRID_PHASES_L2: Final = 2
GRID_PHASES_L1_L2: Final = 3
GRID_PHASES_L3: Final = 4
GRID_PHASES_L1_L3: Final = 5
GRID_PHASES_L2_L3: Final = 6
GRID_PHASES_L1_L2_L3: Final = 7

# Human-readable grid phases mapping.
# Values are translation keys that match translations/<lang>.json
GRID_PHASES_MAP: Final = {
    GRID_PHASES_UNKNOWN: "unknown",
    GRID_PHASES_L1: "l1",
    GRID_PHASES_L2: "l2",
    GRID_PHASES_L1_L2: "l1_l2",
    GRID_PHASES_L3: "l3",
    GRID_PHASES_L1_L3: "l1_l3",
    GRID_PHASES_L2_L3: "l2_l3",
    GRID_PHASES_L1_L2_L3: "l1_l2_l3",
}

# Cellular Mode Constants.
CELLULAR_MODE_UNKNOWN: Final = 0
CELLULAR_MODE_NO_SERVICE: Final = 1
CELLULAR_MODE_GSM: Final = 2
CELLULAR_MODE_LTE_CAT_M1: Final = 3
CELLULAR_MODE_LTE_NB_IOT: Final = 4

# Human-readable cellular mode mapping.
# Values are translation keys that match translations/<lang>.json
CELLULAR_MODE_MAP: Final = {
    CELLULAR_MODE_UNKNOWN: "unknown",
    CELLULAR_MODE_NO_SERVICE: "no_service",
    CELLULAR_MODE_GSM: "gsm",
    CELLULAR_MODE_LTE_CAT_M1: "lte_cat_m1",
    CELLULAR_MODE_LTE_NB_IOT: "lte_nb_iot",
}
