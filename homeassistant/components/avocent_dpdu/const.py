"""Constants for the Avocent Direct PDU integration."""

import logging
from typing import Final

DOMAIN = "avocent_dpdu"

DEFAULT_USERNAME: Final = "snmp"
DEFAULT_PASSWORD: Final = "1234"

LOGGER = logging.getLogger(__package__)
