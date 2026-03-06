"""Constants for the Homewizard integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homewizard_energy.const import Model

from homeassistant.const import Platform

DOMAIN = "homewizard"
PLATFORMS = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

LOGGER = logging.getLogger(__package__)

# Platform config.
CONF_PRODUCT_NAME = "product_name"
CONF_PRODUCT_TYPE = "product_type"
CONF_SERIAL = "serial"
CONF_USAGE = "usage"

UPDATE_INTERVAL = timedelta(seconds=5)

ENERGY_MONITORING_DEVICES = (
    Model.ENERGY_SOCKET,
    Model.ENERGY_METER_1_PHASE,
    Model.ENERGY_METER_3_PHASE,
    Model.ENERGY_METER_EASTRON_SDM230,
    Model.ENERGY_METER_EASTRON_SDM630,
)
