"""Constants for the Avocent Direct PDU integration."""

import logging
from typing import Final

DOMAIN = "avocent_dpdu"


DEFAULT_NUM_OUTLETS: Final = 8
DEFAULT_USERNAME: Final = "snmp"
DEFAULT_PASSWORD: Final = "1234"

LOGGER = logging.getLogger(__package__)
