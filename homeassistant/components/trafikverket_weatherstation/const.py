"""Adds constants for Trafikverket Weather integration."""
from homeassistant.const import Platform

DOMAIN = "trafikverket_weatherstation"
CONF_STATION = "station"
PLATFORMS = [Platform.SENSOR]
ATTRIBUTION = "Data provided by Trafikverket"

NONE_IS_ZERO_SENSORS = {
    "air_temp",
    "road_temp",
    "wind_direction",
    "wind_speed",
    "wind_speed_max",
    "humidity",
    "precipitation_amount",
}
