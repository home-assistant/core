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

#: The WITS schedules behind the forecast are republished about twice an hour.
FORECAST_SCAN_INTERVAL: Final = timedelta(minutes=30)

#: How far ahead to ask for. The server answers with whatever is published,
#: which is usually far less -- read ``covered_hours``, not this.
FORECAST_HORIZON_HOURS: Final = 48

#: Cents per kilowatt hour: the unit New Zealand power bills are written in.
UNIT_CENTS_PER_KWH: Final = "c/kWh"
