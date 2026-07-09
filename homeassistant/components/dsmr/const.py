"""Constants for the DSMR integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "dsmr"

LOGGER = logging.getLogger(__package__)

PLATFORMS = [Platform.SENSOR]
CONF_DSMR_VERSION = "dsmr_version"
CONF_TIME_BETWEEN_UPDATE = "time_between_update"
CONF_ENCRYPTION_KEY = "encryption_key"

CONF_SERIAL_ID = "serial_id"
CONF_SERIAL_ID_GAS = "serial_id_gas"

DEFAULT_DSMR_VERSION = "2.2"
DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_PRECISION = 3
DEFAULT_RECONNECT_INTERVAL = 30
DEFAULT_TIME_BETWEEN_UPDATE = 30

DEVICE_NAME_ELECTRICITY = "Electricity Meter"
DEVICE_NAME_GAS = "Gas Meter"
DEVICE_NAME_WATER = "Water Meter"
DEVICE_NAME_HEAT = "Heat Meter"

DSMR_VERSIONS = {"2.2", "4", "5", "5B", "5L", "5S", "Q3D", "5EONHU", "MSn"}

# Versions that use AES-128-GCM encrypted (DLMS general-global-cipher) telegrams
# and therefore require an encryption key. The GCM authentication tag is not
# verified (integrity comes from the telegram CRC), so only the encryption key
# is ever needed, no authentication key.
ENCRYPTED_DSMR_VERSIONS = {"MSn"}

DSMR_PROTOCOL = "dsmr_protocol"
RFXTRX_DSMR_PROTOCOL = "rfxtrx_dsmr_protocol"
