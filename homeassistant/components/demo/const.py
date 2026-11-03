"""Constants for the Demo component."""

from enum import StrEnum

DOMAIN = "demo"


class DemoService(StrEnum):
    """Store keys for Demo services."""

    RANDOMIZE_DEVICE_TRACKER_DATA = "randomize_device_tracker_data"
