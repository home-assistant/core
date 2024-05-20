"""Constants used by PG LAB Electronics integration."""

import logging

# The domain of the integration
DOMAIN = "pglab"

# The message logger
_LOGGER = logging.getLogger(__name__)

# The mqtt message to be subscribe to get new PG LAB device
DISCOVERY_TOPIC = "pglab/discovery"
