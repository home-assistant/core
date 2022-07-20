"""Const for LIFX."""

import logging

DOMAIN = "lifx"

TARGET_ANY = "00:00:00:00:00:00"

DISCOVERY_INTERVAL = 10
MESSAGE_TIMEOUT = 1.65
MESSAGE_RETRIES = 5
OVERALL_TIMEOUT = 9
UNAVAILABLE_GRACE = 90

CONF_SERIAL = "serial"

DATA_LIFX_MANAGER = "lifx_manager"

_LOGGER = logging.getLogger(__name__)
