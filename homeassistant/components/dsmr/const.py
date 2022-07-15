"""Constants for the DSMR integration."""
from __future__ import annotations

import logging

from homeassistant.const import Platform

DOMAIN = "dsmr"

LOGGER = logging.getLogger(__package__)

PLATFORMS = [Platform.SENSOR]
CONF_DSMR_VERSION = "dsmr_version"
CONF_PROTOCOL = "protocol"
CONF_RECONNECT_INTERVAL = "reconnect_interval"
CONF_PRECISION = "precision"
CONF_TIME_BETWEEN_UPDATE = "time_between_update"

CONF_SERIAL_ID = "serial_id"
CONF_SERIAL_ID_GAS = "serial_id_gas"

DEFAULT_DSMR_VERSION = "2.2"
DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_PRECISION = 3
DEFAULT_RECONNECT_INTERVAL = 30
DEFAULT_TIME_BETWEEN_UPDATE = 30

DATA_TASK = "task"

DEVICE_NAME_ELECTRICITY = "Electricity Meter"
DEVICE_NAME_GAS = "Gas Meter"

DSMR_VERSIONS = {"2.2", "4", "5", "5B", "5L", "5S", "Q3D"}

DSMR_PROTOCOL = "dsmr_protocol"
RFXTRX_DSMR_PROTOCOL = "rfxtrx_dsmr_protocol"
