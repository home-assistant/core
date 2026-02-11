"""Constants used by PG LAB Electronics integration."""

import logging

# The domain of the integration.
DOMAIN = "pglab"

# The message logger.
LOGGER = logging.getLogger(__package__)

# The MQTT message used to subscribe to get a new PG LAB device.
DISCOVERY_TOPIC = "pglab/discovery"
