"""Constants for the Fronius integration."""

from enum import StrEnum
from typing import Final, NamedTuple, TypedDict

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import StateType

DOMAIN: Final = "fronius"

type SolarNetId = str
SOLAR_NET_DISCOVERY_NEW: Final = "fronius_discovery_new"
SOLAR_NET_ID_POWER_FLOW: SolarNetId = "power_flow"
SOLAR_NET_ID_SYSTEM: SolarNetId = "system"
SOLAR_NET_RESCAN_TIMER: Final = 60


class FroniusConfigEntryData(TypedDict):
    """ConfigEntry for the Fronius integration."""

    host: str
    is_logger: bool


class FroniusDeviceInfo(NamedTuple):
    """Information about a Fronius inverter device."""

    device_info: DeviceInfo
    solar_net_id: SolarNetId
    unique_id: str


class InverterStatusCodeOption(StrEnum):
    """Status codes for Fronius inverters."""

    # these are keys for state translations - so snake_case is used
    STARTUP = "startup"
    RUNNING = "running"
    STANDBY = "standby"
    BOOTLOADING = "bootloading"
    ERROR = "error"
    IDLE = "idle"
    READY = "ready"
    SLEEPING = "sleeping"


_INVERTER_STATUS_CODES: Final[dict[int, InverterStatusCodeOption]] = {
    0: InverterStatusCodeOption.STARTUP,
    1: InverterStatusCodeOption.STARTUP,
    2: InverterStatusCodeOption.STARTUP,
    3: InverterStatusCodeOption.STARTUP,
    4: InverterStatusCodeOption.STARTUP,
    5: InverterStatusCodeOption.STARTUP,
    6: InverterStatusCodeOption.STARTUP,
    7: InverterStatusCodeOption.RUNNING,
    8: InverterStatusCodeOption.STANDBY,
    9: InverterStatusCodeOption.BOOTLOADING,
    10: InverterStatusCodeOption.ERROR,
    11: InverterStatusCodeOption.IDLE,
    12: InverterStatusCodeOption.READY,
    13: InverterStatusCodeOption.SLEEPING,
    # 255: "Unknown" is handled by `None` state - same as the invalid codes.
}


def get_inverter_status_message(code: StateType) -> InverterStatusCodeOption | None:
    """Return a status message for a given status code."""
    return _INVERTER_STATUS_CODES.get(code)  # type: ignore[arg-type]


INVERTER_ERROR_CODES: Final[dict[int, str]] = {
    0: "no_error",
    102: "ac_voltage_too_high",
    103: "ac_voltage_too_low",
    105: "ac_frequency_too_high",
    106: "ac_frequency_too_low",
    107: "ac_grid_outside_permissible_limits",
    108: "stand_alone_operation_detected",
    112: "rcmu_error",
    240: "arc_detection_triggered",
    241: "arc_detection_triggered",
    242: "arc_detection_triggered",
    243: "arc_detection_triggered",
    301: "overcurrent_ac",
    302: "overcurrent_dc",
    303: "dc_module_over_temperature",
    304: "ac_module_over_temperature",
    305: "no_power_fed_in_despite_closed_relay",
    306: "pv_output_too_low_for_feeding_energy_into_the_grid",
    307: "low_pv_voltage_dc_input_voltage_too_low",
    308: "intermediate_circuit_voltage_too_high",
    309: "dc_input_voltage_mppt_1_too_high",
    311: "polarity_of_dc_strings_reversed",
    313: "dc_input_voltage_mppt_2_too_high",
    314: "current_sensor_calibration_timeout",
    315: "ac_current_sensor_error",
    316: "interrupt_check_fail",
    325: "overtemperature_in_connection_area",
    326: "fan_1_error",
    327: "fan_2_error",
    401: "no_communication_with_power_stage_set",
    406: "ac_module_temperature_sensor_faulty_l1",
    407: "ac_module_temperature_sensor_faulty_l2",
    408: "dc_component_measured_in_grid_too_high",
    412: "fixed_voltage_mode_out_of_range",
    415: "safety_cut_out_triggered",
    416: "no_communication_between_power_stage_and_control_system",
    417: "hardware_id_problem",
    419: "unique_id_conflict",
    420: "no_communication_with_hybrid_manager",
    421: "hid_range_error",
    425: "no_communication_with_power_stage_set",
    426: "possible_hardware_fault",
    427: "possible_hardware_fault",
    428: "possible_hardware_fault",
    431: "software_problem",
    436: "functional_incompatibility_between_pc_boards",
    437: "power_stage_set_problem",
    438: "functional_incompatibility_between_pc_boards",
    443: "intermediate_circuit_voltage_too_low_or_asymmetric",
    445: "compatibility_error_invalid_power_stage_configuration",
    447: "insulation_fault",
    448: "neutral_conductor_not_connected",
    450: "guard_cannot_be_found",
    451: "memory_error_detected",
    452: "communication",
    502: "insulation_error_on_solar_panels",
    509: "no_energy_fed_into_grid_past_24_hours",
    515: "no_communication_with_filter",
    516: "no_communication_with_storage_unit",
    517: "power_derating_due_to_high_temperature",
    518: "internal_dsp_malfunction",
    519: "no_communication_with_storage_unit",
    520: "no_energy_fed_by_mppt1_past_24_hours",
    522: "dc_low_string_1",
    523: "dc_low_string_2",
    558: "functional_incompatibility_between_pc_boards",
    559: "functional_incompatibility_between_pc_boards",
    560: "derating_caused_by_over_frequency",
    564: "functional_incompatibility_between_pc_boards",
    566: "arc_detector_switched_off",
    567: "grid_voltage_dependent_power_reduction_active",
    601: "can_bus_full",
    603: "ac_module_temperature_sensor_faulty_l3",
    604: "dc_module_temperature_sensor_faulty",
    607: "rcmu_error",
    608: "functional_incompatibility_between_pc_boards",
    701: "internal_processor_status",
    702: "internal_processor_status",
    703: "internal_processor_status",
    704: "internal_processor_status",
    705: "internal_processor_status",
    706: "internal_processor_status",
    707: "internal_processor_status",
    708: "internal_processor_status",
    709: "internal_processor_status",
    710: "internal_processor_status",
    711: "internal_processor_status",
    712: "internal_processor_status",
    713: "internal_processor_status",
    714: "internal_processor_status",
    715: "internal_processor_status",
    716: "internal_processor_status",
    721: "eeprom_reinitialised",
    722: "internal_processor_status",
    723: "internal_processor_status",
    724: "internal_processor_status",
    725: "internal_processor_status",
    726: "internal_processor_status",
    727: "internal_processor_status",
    728: "internal_processor_status",
    729: "internal_processor_status",
    730: "internal_processor_status",
    731: "initialisation_error_usb_flash_drive_not_supported",
    732: "initialisation_error_usb_stick_over_current",
    733: "no_usb_flash_drive_connected",
    734: "update_file_not_recognised_or_missing",
    735: "update_file_does_not_match_device",
    736: "write_or_read_error_occurred",
    737: "file_could_not_be_opened",
    738: "log_file_cannot_be_saved",
    740: "initialisation_error_file_system_error_on_usb",
    741: "error_during_logging_data_recording",
    743: "error_during_update_process",
    745: "update_file_corrupt",
    746: "error_during_update_process",
    751: "time_lost",
    752: "real_time_clock_communication_error",
    753: "real_time_clock_in_emergency_mode",
    754: "internal_processor_status",
    755: "internal_processor_status",
    757: "real_time_clock_hardware_error",
    758: "real_time_clock_in_emergency_mode",
    760: "internal_hardware_error",
    761: "internal_processor_status",
    762: "internal_processor_status",
    763: "internal_processor_status",
    764: "internal_processor_status",
    765: "internal_processor_status",
    766: "emergency_power_derating_activated",
    767: "internal_processor_status",
    768: "different_power_limitation_in_hardware_modules",
    772: "storage_unit_not_available",
    773: "software_update_invalid_country_setup",
    775: "pmc_power_stage_set_not_available",
    776: "invalid_device_type",
    781: "internal_processor_status",
    782: "internal_processor_status",
    783: "internal_processor_status",
    784: "internal_processor_status",
    785: "internal_processor_status",
    786: "internal_processor_status",
    787: "internal_processor_status",
    788: "internal_processor_status",
    789: "internal_processor_status",
    790: "internal_processor_status",
    791: "internal_processor_status",
    792: "internal_processor_status",
    793: "internal_processor_status",
    794: "internal_processor_status",
    1001: "insulation_measurement_triggered",
    1024: "inverter_settings_changed_restart_required",
    1030: "wired_shut_down_triggered",
    1036: "grid_frequency_exceeded_limit_reconnecting",
    1112: "mains_voltage_dependent_power_reduction",
    1175: "too_little_dc_power_for_feed_in_operation",
    1196: "inverter_required_setup_values_not_received",
    65000: "dc_connection_inverter_battery_interrupted",
}


class MeterLocationCodeOption(StrEnum):
    """Meter location codes for Fronius meters."""

    # these are keys for state translations - so snake_case is used
    FEED_IN = "feed_in"
    CONSUMPTION_PATH = "consumption_path"
    GENERATOR = "external_generator"
    EXT_BATTERY = "external_battery"
    SUBLOAD = "subload"


def get_meter_location_description(code: StateType) -> MeterLocationCodeOption | None:
    """Return a location_description for a given location code."""
    match int(code):  # type: ignore[arg-type]
        case 0:
            return MeterLocationCodeOption.FEED_IN
        case 1:
            return MeterLocationCodeOption.CONSUMPTION_PATH
        case 3:
            return MeterLocationCodeOption.GENERATOR
        case 4:
            return MeterLocationCodeOption.EXT_BATTERY
        case _ as _code if 256 <= _code <= 511:
            return MeterLocationCodeOption.SUBLOAD
    return None


class OhmPilotStateCodeOption(StrEnum):
    """OhmPilot state codes for Fronius inverters."""

    # these are keys for state translations - so snake_case is used
    UP_AND_RUNNING = "up_and_running"
    KEEP_MINIMUM_TEMPERATURE = "keep_minimum_temperature"
    LEGIONELLA_PROTECTION = "legionella_protection"
    CRITICAL_FAULT = "critical_fault"
    FAULT = "fault"
    BOOST_MODE = "boost_mode"


_OHMPILOT_STATE_CODES: Final[dict[int, OhmPilotStateCodeOption]] = {
    0: OhmPilotStateCodeOption.UP_AND_RUNNING,
    1: OhmPilotStateCodeOption.KEEP_MINIMUM_TEMPERATURE,
    2: OhmPilotStateCodeOption.LEGIONELLA_PROTECTION,
    3: OhmPilotStateCodeOption.CRITICAL_FAULT,
    4: OhmPilotStateCodeOption.FAULT,
    5: OhmPilotStateCodeOption.BOOST_MODE,
}


def get_ohmpilot_state_message(code: StateType) -> OhmPilotStateCodeOption | None:
    """Return a status message for a given status code."""
    return _OHMPILOT_STATE_CODES.get(code)  # type: ignore[arg-type]
