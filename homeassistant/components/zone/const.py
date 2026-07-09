"""Constants for the zone component."""

from enum import StrEnum

CONF_PASSIVE = "passive"
DOMAIN = "zone"
HOME_ZONE = "home"


class ZoneEntityStateAttribute(StrEnum):
    """State attributes for zone entities."""

    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    RADIUS = "radius"
    PASSIVE = "passive"
    PERSONS = "persons"
    EDITABLE = "editable"


ATTR_PASSIVE = "passive"
ATTR_RADIUS = "radius"
