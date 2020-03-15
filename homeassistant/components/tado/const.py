"""Constant values for the Tado component."""

# Configuration
CONF_FALLBACK = "fallback"
DATA = "data"

# Types
TYPE_AIR_CONDITIONING = "AIR_CONDITIONING"
TYPE_HEATING = "HEATING"
TYPE_HOT_WATER = "HOT_WATER"

# Base modes
CONST_MODE_SMART_SCHEDULE = "SMART_SCHEDULE"  # Use the schedule
CONST_MODE_OFF = "OFF"  # Switch off heating in a zone

# When we change the temperature setting, we need an overlay mode
CONST_OVERLAY_TADO_MODE = "TADO_MODE"  # wait until tado changes the mode automatic
CONST_OVERLAY_MANUAL = "MANUAL"  # the user has change the temperature or mode manually
CONST_OVERLAY_TIMER = "TIMER"  # the temperature will be reset after a timespan
