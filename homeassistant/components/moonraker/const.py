"""Constants for the moonraker integration."""

BACKOFF_TIME_UPPER_LIMIT = 120
BACKOFF_TIME_LOWER_LIMIT = 30
BACKOFF_MAX_COUNT = 10

DATA_CONNECTOR = "moonraker_data_connector"

DOMAIN = "moonraker"

SIGNAL_UPDATE_TOOLHEAD = "moonraker_update_toolhead"
SIGNAL_UPDATE_EXTRUDER = "moonraker_update_extruder"
SIGNAL_UPDATE_HEAT_BED = "moonraker_update_heater_bed"
SIGNAL_UPDATE_FAN = "moonraker_update_fan"
SIGNAL_UPDATE_VIRTUAL_SDCARD = "moonraker_update_virtual_sdcard"
SIGNAL_UPDATE_PRINT_STATUS = "moonraker_update_print_stats"
SIGNAL_UPDATE_DISPLAY_STATUS = "moonraker_update_display_status"
SIGNAL_UPDATE_MODULE = "moonraker_update_%s"

SIGNAL_STATE_AVAILABLE = "moonraker_state_available"

SIGNAL_UPDATE_RATE_LIMIT = 1.0
