from datetime import timedelta
from typing import Final

from homeassistant.const import (
    ATTR_NAME as ATTR_NAME,
    CONF_API_KEY as CONF_API_KEY,
    CONF_ID as CONF_ID,
    CONF_NAME as CONF_NAME,
    UnitOfTime as UnitOfTime,
)

ATTRIBUTION: Final[str] = "Data provided by WSDOT"

ATTR_ACCESS_CODE: Final[str] = "AccessCode"
ATTR_AVG_TIME: Final[str] = "AverageTime"
ATTR_CURRENT_TIME: Final[str] = "CurrentTime"
ATTR_DESCRIPTION: Final[str] = "Description"
ATTR_TIME_UPDATED: Final[str] = "TimeUpdated"
ATTR_TRAVEL_TIME_ID: Final[str] = "TravelTimeID"
ATTR_TRAVEL_TIME_NAME: Final[str] = "Name"

CONF_TRAVEL_TIMES: Final[str] = "travel_time"
CONF_TRAVEL_TIMES_ID: Final[str] = "id"
CONF_TRAVEL_TIMES_NAME: Final[str] = "name"

DIALOG_API_KEY: Final[str] = "API Key"
DIALOG_NAME: Final[str] = "Name"

DOMAIN: Final[str] = "wsdot"

ICON: Final[str] = "mdi:car"

RESOURCE: Final[str] = (
    "http://www.wsdot.wa.gov/Traffic/api/TravelTimes/"
    "TravelTimesREST.svc/GetTravelTimeAsJson"
)

SCAN_INTERVAL: Final = timedelta(minutes=3)
