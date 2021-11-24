"""Constants for the Nina integration."""

from datetime import timedelta
from logging import Logger, getLogger

_LOGGER: Logger = getLogger(__package__)

SCAN_INTERVAL: timedelta = timedelta(minutes=5)

DOMAIN: str = "nina"

CONF_REGIONS: str = "regions"
CONF_MESSAGE_SLOTS: str = "slots"
CONF_FILTER_CORONA: str = "corona_filter"

ATTR_HEADLINE: str = "Headline"
ATTR_ID: str = "ID"
ATTR_SENT: str = "Sent"
ATTR_START: str = "Start"
ATTR_EXPIRES: str = "Expires"

CORONA_FILTER: str = "Corona Filter"
