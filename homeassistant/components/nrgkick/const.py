"""Constants for the NRGkick integration."""

from typing import Final

from nrgkick_api import (
    CellularMode,
    ChargingStatus,
    ConnectorType,
    ErrorCode,
    GridPhases,
    RcdTriggerStatus,
    RelayState,
    WarningCode,
)

DOMAIN: Final = "nrgkick"

# Default polling interval (seconds).
DEFAULT_SCAN_INTERVAL: Final = 30

# Note: API Endpoints are in the nrgkick-api library.
# Import from nrgkick_api if needed: from nrgkick_api import ENDPOINT_INFO, ...

# Human-readable status mapping for the status sensor.
# Values are translation keys that match translations/<lang>.json
STATUS_MAP: Final[dict[int, str]] = {
    ChargingStatus.UNKNOWN: "unknown",
    ChargingStatus.STANDBY: "standby",
    ChargingStatus.CONNECTED: "connected",
    ChargingStatus.CHARGING: "charging",
    ChargingStatus.ERROR: "error",
    ChargingStatus.WAKEUP: "wakeup",
}

# Human-readable RCD trigger mapping.
# Values are translation keys that match translations/<lang>.json
RCD_TRIGGER_MAP: Final[dict[int, str]] = {
    RcdTriggerStatus.NO_FAULT: "no_fault",
    RcdTriggerStatus.AC_30MA_FAULT: "ac_30ma_fault",
    RcdTriggerStatus.AC_60MA_FAULT: "ac_60ma_fault",
    RcdTriggerStatus.AC_150MA_FAULT: "ac_150ma_fault",
    RcdTriggerStatus.DC_POSITIVE_6MA_FAULT: "dc_positive_6ma_fault",
    RcdTriggerStatus.DC_NEGATIVE_6MA_FAULT: "dc_negative_6ma_fault",
}


# Human-readable warning code mapping.
# Values are translation keys that match translations/<lang>.json
WARNING_CODE_MAP: Final[dict[int, str]] = {
    WarningCode.NO_WARNING: "no_warning",
    WarningCode.NO_PE: "no_pe",
    WarningCode.BLACKOUT_PROTECTION: "blackout_protection",
    WarningCode.ENERGY_LIMIT_REACHED: "energy_limit_reached",
    WarningCode.EV_DOES_NOT_COMPLY_STANDARD: "ev_does_not_comply_standard",
    WarningCode.UNSUPPORTED_CHARGING_MODE: "unsupported_charging_mode",
    WarningCode.NO_ATTACHMENT_DETECTED: "no_attachment_detected",
    WarningCode.NO_COMM_WITH_TYPE2_ATTACHMENT: "no_comm_with_type2_attachment",
    WarningCode.INCREASED_TEMPERATURE: "increased_temperature",
    WarningCode.INCREASED_HOUSING_TEMPERATURE: "increased_housing_temperature",
    WarningCode.INCREASED_ATTACHMENT_TEMPERATURE: "increased_attachment_temperature",
    WarningCode.INCREASED_DOMESTIC_PLUG_TEMPERATURE: (
        "increased_domestic_plug_temperature"
    ),
}


# Human-readable error code mapping.
# Values are translation keys that match translations/<lang>.json
ERROR_CODE_MAP: Final[dict[int, str]] = {
    ErrorCode.NO_ERROR: "no_error",
    ErrorCode.GENERAL_ERROR: "general_error",
    ErrorCode.ATTACHMENT_32A_ON_16A_UNIT: "32a_attachment_on_16a_unit",
    ErrorCode.VOLTAGE_DROP_DETECTED: "voltage_drop_detected",
    ErrorCode.UNPLUG_DETECTION_TRIGGERED: "unplug_detection_triggered",
    ErrorCode.TYPE2_NOT_AUTHORIZED: "type2_not_authorized",
    ErrorCode.RESIDUAL_CURRENT_DETECTED: "residual_current_detected",
    ErrorCode.CP_SIGNAL_VOLTAGE_ERROR: "cp_signal_voltage_error",
    ErrorCode.CP_SIGNAL_IMPERMISSIBLE: "cp_signal_impermissible",
    ErrorCode.EV_DIODE_FAULT: "ev_diode_fault",
    ErrorCode.PE_SELF_TEST_FAILED: "pe_self_test_failed",
    ErrorCode.RCD_SELF_TEST_FAILED: "rcd_self_test_failed",
    ErrorCode.RELAY_SELF_TEST_FAILED: "relay_self_test_failed",
    ErrorCode.PE_AND_RCD_SELF_TEST_FAILED: "pe_and_rcd_self_test_failed",
    ErrorCode.PE_AND_RELAY_SELF_TEST_FAILED: "pe_and_relay_self_test_failed",
    ErrorCode.RCD_AND_RELAY_SELF_TEST_FAILED: "rcd_and_relay_self_test_failed",
    ErrorCode.PE_AND_RCD_AND_RELAY_SELF_TEST_FAILED: (
        "pe_and_rcd_and_relay_self_test_failed"
    ),
    ErrorCode.SUPPLY_VOLTAGE_ERROR: "supply_voltage_error",
    ErrorCode.PHASE_SHIFT_ERROR: "phase_shift_error",
    ErrorCode.OVERVOLTAGE_DETECTED: "overvoltage_detected",
    ErrorCode.UNDERVOLTAGE_DETECTED: "undervoltage_detected",
    ErrorCode.OVERVOLTAGE_WITHOUT_PE_DETECTED: "overvoltage_without_pe_detected",
    ErrorCode.UNDERVOLTAGE_WITHOUT_PE_DETECTED: "undervoltage_without_pe_detected",
    ErrorCode.UNDERFREQUENCY_DETECTED: "underfrequency_detected",
    ErrorCode.OVERFREQUENCY_DETECTED: "overfrequency_detected",
    ErrorCode.UNKNOWN_FREQUENCY_TYPE: "unknown_frequency_type",
    ErrorCode.UNKNOWN_GRID_TYPE: "unknown_grid_type",
    ErrorCode.GENERAL_OVERTEMPERATURE: "general_overtemperature",
    ErrorCode.HOUSING_OVERTEMPERATURE: "housing_overtemperature",
    ErrorCode.ATTACHMENT_OVERTEMPERATURE: "attachment_overtemperature",
    ErrorCode.DOMESTIC_PLUG_OVERTEMPERATURE: "domestic_plug_overtemperature",
}


# Human-readable relay state mapping.
# Values are translation keys that match translations/<lang>.json
RELAY_STATE_MAP: Final[dict[int, str]] = {
    RelayState.NO_RELAY: "no_relay",
    RelayState.N: "n",
    RelayState.L1: "l1",
    RelayState.N_L1: "n_l1",
    RelayState.L2: "l2",
    RelayState.N_L2: "n_l2",
    RelayState.L1_L2: "l1_l2",
    RelayState.N_L1_L2: "n_l1_l2",
    RelayState.L3: "l3",
    RelayState.N_L3: "n_l3",
    RelayState.L1_L3: "l1_l3",
    RelayState.N_L1_L3: "n_l1_l3",
    RelayState.L2_L3: "l2_l3",
    RelayState.N_L2_L3: "n_l2_l3",
    RelayState.L1_L2_L3: "l1_l2_l3",
    RelayState.N_L1_L2_L3: "n_l1_l2_l3",
}


# Human-readable connector type mapping.
# Values are translation keys that match translations/<lang>.json
CONNECTOR_TYPE_MAP: Final[dict[int, str]] = {
    ConnectorType.UNKNOWN: "unknown",
    ConnectorType.CEE: "cee",
    ConnectorType.DOMESTIC: "domestic",
    ConnectorType.TYPE2: "type2",
    ConnectorType.WALL: "wall",
    ConnectorType.AUS: "aus",
}


# Human-readable grid phases mapping.
# Values are translation keys that match translations/<lang>.json
GRID_PHASES_MAP: Final[dict[int, str]] = {
    GridPhases.UNKNOWN: "unknown",
    GridPhases.L1: "l1",
    GridPhases.L2: "l2",
    GridPhases.L1_L2: "l1_l2",
    GridPhases.L3: "l3",
    GridPhases.L1_L3: "l1_l3",
    GridPhases.L2_L3: "l2_l3",
    GridPhases.L1_L2_L3: "l1_l2_l3",
}


# Human-readable cellular mode mapping.
# Values are translation keys that match translations/<lang>.json
CELLULAR_MODE_MAP: Final[dict[int, str]] = {
    CellularMode.UNKNOWN: "unknown",
    CellularMode.NO_SERVICE: "no_service",
    CellularMode.GSM: "gsm",
    CellularMode.LTE_CAT_M1: "lte_cat_m1",
    CellularMode.LTE_NB_IOT: "lte_nb_iot",
}
