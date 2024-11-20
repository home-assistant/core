"""Constants for the AirNow integration."""

ATTR_API_AQI = "AQI"
ATTR_API_AQI_LEVEL = "Category.Number"
ATTR_API_AQI_DESCRIPTION = "Category.Name"
ATTR_API_AQI_PARAM = "ParameterName"
ATTR_API_CATEGORY = "Category"
ATTR_API_CAT_LEVEL = "Number"
ATTR_API_CAT_DESCRIPTION = "Name"
ATTR_API_O3 = "O3"
ATTR_API_PM10 = "PM10"
ATTR_API_PM25 = "PM2.5"
ATTR_API_POLLUTANT = "Pollutant"
ATTR_API_REPORT_DATE = "DateObserved"
ATTR_API_REPORT_HOUR = "HourObserved"
ATTR_API_REPORT_TZ = "LocalTimeZone"
ATTR_API_STATE = "StateCode"
ATTR_API_STATION = "ReportingArea"
ATTR_API_STATION_LATITUDE = "Latitude"
ATTR_API_STATION_LONGITUDE = "Longitude"
DEFAULT_NAME = "AirNow"
DOMAIN = "airnow"

SECONDS_PER_HOUR = 3600

# AirNow seems to only use standard time zones,
# but we include daylight savings for completeness/futureproofing.
US_TZ_OFFSETS = {
    "HST": -10 * SECONDS_PER_HOUR,
    "HDT": -9 * SECONDS_PER_HOUR,
    # AirNow returns AKT instead of AKST or AKDT, use standard
    "AKT": -9 * SECONDS_PER_HOUR,
    "AKST": -9 * SECONDS_PER_HOUR,
    "AKDT": -8 * SECONDS_PER_HOUR,
    "PST": -8 * SECONDS_PER_HOUR,
    "PDT": -7 * SECONDS_PER_HOUR,
    "MST": -7 * SECONDS_PER_HOUR,
    "MDT": -6 * SECONDS_PER_HOUR,
    "CST": -6 * SECONDS_PER_HOUR,
    "CDT": -5 * SECONDS_PER_HOUR,
    "EST": -5 * SECONDS_PER_HOUR,
    "EDT": -4 * SECONDS_PER_HOUR,
    "AST": -4 * SECONDS_PER_HOUR,
    "ADT": -3 * SECONDS_PER_HOUR,
}
