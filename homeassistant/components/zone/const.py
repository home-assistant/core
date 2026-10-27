"""Constants for the zone component."""

from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import ZoneData

CONF_PASSIVE = "passive"
DOMAIN = "zone"
HOME_ZONE = "home"

DATA_ZONE: HassKey[ZoneData] = HassKey(DOMAIN)


class ZoneEntityStateAttribute(StrEnum):
    """State attributes for zone entities."""

    RADIUS = "radius"
    PASSIVE = "passive"
    PERSONS = "persons"
    DEVICE_TRACKERS = "device_trackers"
    EDITABLE = "editable"


ATTR_PASSIVE = "passive"
ATTR_RADIUS = "radius"
