"""Constants for the geo_location component."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.helpers.deprecation import EnumWithDeprecatedMembers
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import GeolocationEvent


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
    LATITUDE = "latitude"  # Deprecated, replaced with EntityStateAttribute.LATITUDE
    LONGITUDE = "longitude"  # Deprecated, replaced with EntityStateAttribute.LONGITUDE


DOMAIN: Final = "geo_location"

DATA_COMPONENT: HassKey[EntityComponent[GeolocationEvent]] = HassKey(DOMAIN)
