"""Constants for the person entity platform."""

from enum import StrEnum

DOMAIN = "person"


class PersonEntityStateAttribute(StrEnum):
    """State attributes for person entities."""

    EDITABLE = "editable"
    ID = "id"
    DEVICE_TRACKERS = "device_trackers"
    IN_ZONES = "in_zones"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    GPS_ACCURACY = "gps_accuracy"
    SOURCE = "source"
    USER_ID = "user_id"
