"""Constants for the Mammotion Luba integration."""

import logging
from typing import Final

DOMAIN: Final = "mammotion"

DEFAULT_RETRY_COUNT = 3
CONF_RETRY_COUNT = "retry_count"
LOGGER: Final = logging.getLogger(__package__)
