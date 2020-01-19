"""Constants for the Bose Soundtouch component."""
from enum import Enum

DOMAIN = "soundtouch"
SERVICE_PLAY_EVERYWHERE = "play_everywhere"
SERVICE_CREATE_ZONE = "create_zone"
SERVICE_ADD_ZONE_SLAVE = "add_zone_slave"
SERVICE_REMOVE_ZONE_SLAVE = "remove_zone_slave"
BLUETOOTH_SOURCE = "BLUETOOTH"


class Source(Enum):
    """sources supported by bose soundtouch."""

    AUX = "AUX"
    BLUETOOTH = "BLUETOOTH"
    PRODUCT_SOURCE = "PRODUCT"
