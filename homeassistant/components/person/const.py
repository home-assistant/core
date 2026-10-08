"""Constants for the person entity platform."""

from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import PersonData

DOMAIN = "person"

CONF_USER_ID = "user_id"

DATA_PERSON: HassKey[PersonData] = HassKey(DOMAIN)


class PersonEntityStateAttribute(StrEnum):
    """State attributes for person entities."""

    EDITABLE = "editable"
    ID = "id"
    DEVICE_TRACKERS = "device_trackers"
    IN_ZONES = "in_zones"
    GPS_ACCURACY = "gps_accuracy"
    SOURCE = "source"
    USER_ID = "user_id"
