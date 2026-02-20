"""Constants for the Smart Meter B Route integration."""

from datetime import timedelta

DOMAIN = "route_b_smart_meter"
ENTRY_TITLE = "Route B Smart Meter"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=300)

ATTR_API_INSTANTANEOUS_POWER = "instantaneous_power"
ATTR_API_TOTAL_CONSUMPTION = "total_consumption"
ATTR_API_INSTANTANEOUS_CURRENT_T_PHASE = "instantaneous_current_t_phase"
ATTR_API_INSTANTANEOUS_CURRENT_R_PHASE = "instantaneous_current_r_phase"
ATTR_API_FAULT_STATUS = "fault_status"
ATTR_API_SERIAL_NUMBER = "serial_number"
ATTR_API_MANUFACTURER_CODE = "manufacturer_code"
ATTR_API_ECHONET_VERSION = "echonet_version"
