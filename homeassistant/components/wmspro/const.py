"""Constants for the WMS WebControl pro API integration."""

from datetime import timedelta
from typing import Final

DOMAIN = "wmspro"
SUGGESTED_HOST = "webcontrol"

ATTRIBUTION = "Data provided by WMS WebControl pro API"
MANUFACTURER = "WAREMA Renkhoff SE"

BRIGHTNESS_SCALE = (1, 100)
MIN_TIME_BETWEEN_UPDATES: Final = timedelta(milliseconds=500)
