"""Constants used by PG LAB Electronics integration."""

import logging

from homeassistant.const import Platform

# The domain of the integration
DOMAIN = "pglab"

# The message logger
_LOGGER = logging.getLogger(__name__)

# Used to de-register the component create callback
DISCONNECT_COMPONENT = {
    Platform.SWITCH: "pglab_disconnect_component_switch",
}

# Used to create a new component entity
CREATE_NEW_ENTITY = {
    Platform.SWITCH: "pglab_create_new_entity_switch",
}

# The discovery instance
DISCOVERY_INSTANCE = "pglab_discovery_instance"

# All discoperd PG LAB devices
DEVICE_ALREADY_DISCOVERED = "pglab_discovered_device"

# The mqtt message to be subscribe to get new PG LAB device
DISCOVERY_TOPIC = "pglab/discovery"

CONF_DISCOVERY_PREFIX = "discovery_prefix"
CONF_DISCOVERY_PAYLOAD = "payload"

# Supperted platforms
PLATFORMS = [
    Platform.SWITCH,
]
