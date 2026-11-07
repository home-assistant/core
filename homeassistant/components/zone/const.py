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

PREVIEW_FEATURE_IMPROVED_PRESENCE_DETECTION = "improved_presence_detection"


class ZoneRelation(StrEnum):
    """Relation between a location's accuracy circle and a zone."""

    CONTAINED = "contained"
    """The accuracy circle fits fully inside the zone."""
    OVERLAPPING = "overlapping"
    """The accuracy circle partly overlaps the zone."""
    SEPARATED = "separated"
    """The accuracy circle does not overlap the zone."""


class ZoneEntityStateAttribute(StrEnum):
    """State attributes for zone entities."""

    RADIUS = "radius"
    PASSIVE = "passive"
    PERSONS = "persons"
    DEVICE_TRACKERS = "device_trackers"
    EDITABLE = "editable"


ATTR_PASSIVE = "passive"
ATTR_RADIUS = "radius"
