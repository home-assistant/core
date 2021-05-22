"""Yale integration constants."""
import logging

CONF_AREA_ID = "area_id"
DEFAULT_NAME = "Yale Smart Alarm"
DEFAULT_AREA_ID = "1"

MANUFACTURER = "Yale"
MODEL = "main"

DOMAIN = "yale_smart_alarm"

DEFAULT_SCAN_INTERVAL = 15

LOGGER = logging.getLogger(__package__)

ATTR_ONLINE = "online"
ATTR_STATUS = "status"
