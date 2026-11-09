"""Constants for the ecosmart integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "ecosmart"

LOGGER = logging.getLogger(__package__)

ATTRIBUTION: Final = "Data provided by ecosmart"
CONFIGURATION_URL: Final = "https://my.ecosmart.co.nz"
MANUFACTURER: Final = "ecosmart"

#: Fallback title when the API key carries no label.
DEFAULT_TITLE: Final = "ecosmart"

#: The live dispatch price is republished every five minutes.
SPOT_SCAN_INTERVAL: Final = timedelta(seconds=300)

#: How far ahead the forecast action asks for: the API's own maximum. The
#: published schedules usually reach far less.
FORECAST_HOURS: Final = 168

#: Cents per kilowatt hour: the unit New Zealand power bills are written in.
UNIT_CENTS_PER_KWH: Final = "c/kWh"
