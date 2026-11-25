"""Constants for the KACO RS485 integration."""

import logging
from typing import Final

DOMAIN: Final = "kaco_rs485"
LOGGER: Final = logging.getLogger(__package__)

CONF_ADDRESSES: Final = "addresses"

# What each address reported at setup, keyed by address string (data is JSON).
# Recorded then, not polled: at night there is nothing to read.
CONF_INVERTERS: Final = "inverters"
CONF_SW_VERSION: Final = "sw_version"

MANUFACTURER: Final = "KACO new energy"

# The bus reports a bare type ("6400xi"); the xi range is all Powador.
SERIES_PREFIX: Final = "KACO Powador"
