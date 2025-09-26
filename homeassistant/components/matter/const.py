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

SERVICE_SET_UNOCCUPIED_COOLING_TEMPERATURE = "set_unoccupied_cooling_target_temperature"
SERVICE_SET_UNOCCUPIED_HEATING_TEMPERATURE = "set_unoccupied_heating_target_temperature"

ATTR_OCCUPANCY = "occupancy"
ATTR_UNOCCUPIED_COOLING_TARGET_TEMP = "unoccupied_cooling_target_temp"
ATTR_UNOCCUPIED_HEATING_TARGET_TEMP = "unoccupied_heating_target_temp"
