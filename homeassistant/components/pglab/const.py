"""Constants used by PG LAB Electronics integration."""

import logging

from homeassistant.const import Platform

# The domain of the integration
DOMAIN = "pglab"

# The message logger
_LOGGER = logging.getLogger(__name__)

# Used to create a new component entity
CREATE_NEW_ENTITY = {
    Platform.SWITCH: "pglab_create_new_entity_switch",
}

# All discoperd PG LAB devices
DEVICE_ALREADY_DISCOVERED = "pglab_discovered_device"

# The mqtt message to be subscribe to get new PG LAB device
DISCOVERY_TOPIC = "pglab/discovery"
