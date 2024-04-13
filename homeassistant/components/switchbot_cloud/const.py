"""Constants for the SwitchBot Cloud integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "switchbot_cloud"
ENTRY_TITLE = "SwitchBot Cloud"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=600)
DEVICE_SCAN_INTERVAL = {"MeterPlus": timedelta(seconds=60)}
