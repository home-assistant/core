"""Constants for Airly integration."""
from __future__ import annotations

from typing import Final

ATTR_API_ADVICE: Final = "ADVICE"
ATTR_API_CAQI: Final = "CAQI"
ATTR_API_CAQI_DESCRIPTION: Final = "DESCRIPTION"
ATTR_API_CAQI_LEVEL: Final = "LEVEL"
ATTR_API_HUMIDITY: Final = "HUMIDITY"
ATTR_API_PM10: Final = "PM10"
ATTR_API_PM1: Final = "PM1"
ATTR_API_PM25: Final = "PM25"
ATTR_API_PRESSURE: Final = "PRESSURE"
ATTR_API_TEMPERATURE: Final = "TEMPERATURE"

ATTR_ADVICE: Final = "advice"
ATTR_DESCRIPTION: Final = "description"
ATTR_LEVEL: Final = "level"
ATTR_LIMIT: Final = "limit"
ATTR_PERCENT: Final = "percent"

SUFFIX_PERCENT: Final = "PERCENT"
SUFFIX_LIMIT: Final = "LIMIT"

ATTRIBUTION: Final = "Data provided by Airly"
CONF_USE_NEAREST: Final = "use_nearest"
DOMAIN: Final = "airly"
LABEL_ADVICE: Final = "advice"
MANUFACTURER: Final = "Airly sp. z o.o."
MAX_UPDATE_INTERVAL: Final = 90
MIN_UPDATE_INTERVAL: Final = 5
NO_AIRLY_SENSORS: Final = "There are no Airly sensors in this area yet."
URL = "https://airly.org/map/#{latitude},{longitude}"
