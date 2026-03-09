"""Define constants for the USGS Earthquakes Feed integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "usgs_earthquakes_feed"

PLATFORMS = [Platform.GEO_LOCATION]

CONF_FEED_TYPE = "feed_type"
CONF_MINIMUM_MAGNITUDE = "minimum_magnitude"

DEFAULT_MINIMUM_MAGNITUDE = 0.0
DEFAULT_RADIUS = 50.0
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

VALID_FEED_TYPES = [
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
