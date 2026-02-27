"""Constants for the Matter integration."""

import logging

ADDON_SLUG = "core_matter_server"

CONF_INTEGRATION_CREATED_ADDON = "integration_created_addon"
CONF_USE_ADDON = "use_addon"

DOMAIN = "matter"
LOGGER = logging.getLogger(__package__)

# prefixes to identify device identifier id types
ID_TYPE_DEVICE_ID = "deviceid"
ID_TYPE_SERIAL = "serial"

FEATUREMAP_ATTRIBUTE_ID = 65532

# Cluster IDs relevant for direct device-to-device bindings.
# Derived from the Matter Device Library Specification -- each ID corresponds
# to a cluster for which a standard controller device type with the Binding
# cluster exists (e.g. On/Off Light Switch, Door Lock Controller, etc.).
BINDABLE_CLUSTER_IDS: frozenset[int] = frozenset(
    {
        6,  # OnOff
        8,  # LevelControl
        257,  # DoorLock
        258,  # WindowCovering
        512,  # PumpConfigurationAndControl
        513,  # Thermostat
        768,  # ColorControl
    }
)
