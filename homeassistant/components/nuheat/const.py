"""Constants for NuHeat thermostats."""
from homeassistant.const import Platform

DOMAIN = "nuheat"

PLATFORMS = [Platform.CLIMATE]

CONF_SERIAL_NUMBER = "serial_number"

MANUFACTURER = "NuHeat"

NUHEAT_API_STATE_SHIFT_DELAY = 2

TEMP_HOLD_TIME_SEC = 43200

NUHEAT_KEY_SET_POINT_TEMP = "SetPointTemp"
NUHEAT_KEY_SCHEDULE_MODE = "ScheduleMode"
NUHEAT_KEY_HOLD_SET_POINT_DATE_TIME = "HoldSetPointDateTime"
NUHEAT_DATETIME_FORMAT = "%a, %d %b %Y %H:%M:%S GMT"
