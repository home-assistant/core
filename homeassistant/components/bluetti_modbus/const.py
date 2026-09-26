"""Constants for the BLUETTI Modbus integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "bluetti_modbus"
LOGGER = logging.getLogger(__package__)

CONF_UNIT_ID: Final = "unit_id"

# Also the inverter type string the device reports over Modbus.
MODEL: Final = "Balco260"

# BLUETTI's factory defaults.
DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 1

# The device's Modbus TCP stack becomes unresponsive when polled faster.
SCAN_INTERVAL: Final = timedelta(seconds=30)

# Left out of the read plan as well as entity creation.
EXCLUDED_FIELDS: Final = frozenset(
    {
        # Writable controls; this integration is read-only.
        "ac_o_switch",
        "g_i_switch",
        "g_o_switch",
        "b_soc_high",
        "b_soc_low",
        # The library only decodes their zero member, so a real code reads None.
        "d_inverter_fault",
        "d_inverter_warning",
        # Undecoded bitmaps.
        "b_protect",
        "b_error",
        "b_alarm_residential",
        "b_alarm_portable",
        # Only served at the aggregate unit id (250); read 0 at the device's own.
        "d_num_battery_packs",
        "b_soc_total",
        "b_soh_total",
        "b_status",
        "b_time_to_full_total",
        "b_time_to_empty_total",
        # Phases 2 and 3 read 0 on the single-phase units verified so far.
        "d_phase_count",
        "g_2_i_p",
        "g_2_i_v",
        "g_2_i_c",
        "g_3_i_p",
        "g_3_i_v",
        "g_3_i_c",
        "ac_phase_count",
        "ac_2_o_p",
        "ac_2_o_v",
        "ac_2_o_c",
        "ac_3_o_p",
        "ac_3_o_v",
        "ac_3_o_c",
        "d_inverter_phase_count",
        "d_inverter_2_status",
        "d_inverter_2_p",
        "d_inverter_2_v",
        "d_inverter_2_c",
        "d_inverter_3_status",
        "d_inverter_3_p",
        "d_inverter_3_v",
        "d_inverter_3_c",
        # Always 0 on the Balco 260 tested, whose four PV inputs are all DC.
        "pv_ac_count",
        # Equal to a total already exposed on a single-phase, single-inverter unit.
        "pv_i_p_local",
        "g_1_i_p",
        "ac_1_o_p",
        "d_inverter_1_p",
        "d_inverter_1_status",
        # Identity of the battery pack and IoT module, not of this device.
        "b_serial",
        "b_ver_count",
        "b_ver_1",
        "b_ver_2",
        "b_ver_3",
        "b_ver_4",
        "d_iot_model",
        "d_iot_serial",
    }
)
