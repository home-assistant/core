"""Constants for the USGS Earthquakes Feed integration."""

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform, UnitOfLength

DOMAIN: Final = "usgs_earthquakes_feed"
PLATFORMS: Final = [Platform.GEO_LOCATION]

ATTR_ALERT: Final = "alert"
ATTR_EXTERNAL_ID: Final = "external_id"
ATTR_MAGNITUDE: Final = "magnitude"
ATTR_PLACE: Final = "place"
ATTR_STATUS: Final = "status"
ATTR_TYPE: Final = "type"
ATTR_UPDATED: Final = "updated"

CONF_FEED_TYPE: Final = "feed_type"
CONF_MINIMUM_MAGNITUDE: Final = "minimum_magnitude"

DEFAULT_MINIMUM_MAGNITUDE: Final = 0.0
DEFAULT_RADIUS_IN_KM: Final = 50.0
DEFAULT_UNIT_OF_MEASUREMENT: Final = UnitOfLength.KILOMETERS

SCAN_INTERVAL: Final = timedelta(minutes=5)

SIGNAL_DELETE_ENTITY: Final = "usgs_earthquakes_feed_delete_{}"
SIGNAL_UPDATE_ENTITY: Final = "usgs_earthquakes_feed_update_{}"

SOURCE: Final = DOMAIN

VALID_FEED_TYPES: Final = [
    "past_hour_significant_earthquakes",
    "past_hour_m45_earthquakes",
    "past_hour_m25_earthquakes",
    "past_hour_m10_earthquakes",
    "past_hour_all_earthquakes",
    "past_day_significant_earthquakes",
    "past_day_m45_earthquakes",
    "past_day_m25_earthquakes",
    "past_day_m10_earthquakes",
    "past_day_all_earthquakes",
    "past_week_significant_earthquakes",
    "past_week_m45_earthquakes",
    "past_week_m25_earthquakes",
    "past_week_m10_earthquakes",
    "past_week_all_earthquakes",
    "past_month_significant_earthquakes",
    "past_month_m45_earthquakes",
    "past_month_m25_earthquakes",
    "past_month_m10_earthquakes",
    "past_month_all_earthquakes",
]
