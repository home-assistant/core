"""Constants for the geo_location component."""

from enum import StrEnum


class GeolocationEntityStateAttribute(StrEnum):
    """State attributes for geolocation entities."""

    SOURCE = "source"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
