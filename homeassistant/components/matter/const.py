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

# WaterHeaterManagement.Commands.Boost
ATTR_DURATION = "duration"
ATTR_EMERGENCY_BOOST = "emergency_boost"
ATTR_TEMPORARY_SETPOINT = "temporary_setpoint"
SERVICE_WATER_HEATER_BOOST = "water_heater_boost"
