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

# Maps the stored dsmr_version token to the label shown in the config-flow
# version picker. The label is where the meter/grid is disambiguated: notably
# the Luxembourg Smarty IS a Sagemcom T210-D, so a Luxembourg user should pick
# MSn, not the Austrian SAGEMCOM_T210_D_R option.
DSMR_VERSIONS = {
    "5": "DSMR 5",
    "MSn": "Luxembourg Smarty / Sagemcom T210-D, encrypted (Creos)",
    "SAGEMCOM_T210_D_R": "Sagemcom T210-D-R, encrypted (Austria, Energienetze Steiermark)",
    "5B": "DSMR 5B (Belgium, Fluvius)",
    "5L": "DSMR 5L (Luxembourg, unencrypted)",
    "5S": "DSMR 5S (Sweden)",
    "Q3D": "Q3D (Austria)",
    "5EONHU": "DSMR 5 (E.ON Hungary)",
    "4": "DSMR 4",
    "2.2": "DSMR 2.2",
}

# Versions that use AES-128-GCM encrypted (DLMS general-global-cipher) telegrams
# and therefore require an encryption key. The GCM authentication tag is not
# verified (integrity comes from the telegram CRC), so only the encryption key
# is ever needed, no authentication key.
ENCRYPTED_DSMR_VERSIONS = {"MSn", "SAGEMCOM_T210_D_R"}

# Versions whose telegrams carry no equipment identifier; validation falls back
# to the telegram timestamp to confirm communication.
DSMR_VERSIONS_WITHOUT_EQUIPMENT_ID = {"5S", "SAGEMCOM_T210_D_R"}

DSMR_PROTOCOL = "dsmr_protocol"
RFXTRX_DSMR_PROTOCOL = "rfxtrx_dsmr_protocol"
