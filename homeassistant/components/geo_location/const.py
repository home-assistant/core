"""Constants for the geo_location component."""

from enum import StrEnum

from homeassistant.helpers.deprecation import EnumWithDeprecatedMembers


class GeolocationEntityStateAttribute(
    StrEnum,
    metaclass=EnumWithDeprecatedMembers,
    deprecated={
        "LATITUDE": ("EntityStateAttribute.LATITUDE", "2027.2.0"),
        "LONGITUDE": ("EntityStateAttribute.LONGITUDE", "2027.2.0"),
    },
):
    """State attributes for geolocation entities."""

    SOURCE = "source"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
