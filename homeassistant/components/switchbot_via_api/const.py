"""Constants for the Switchbot via API integration."""
from datetime import timedelta
from typing import Final

DOMAIN: Final = "switchbot_via_api"
API: Final = "switchbot-api"
ENTRY_TITLE = "Switchbot API"
SCAN_INTERVAL = timedelta(seconds=600)
