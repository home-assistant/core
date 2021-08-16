"""Const for TP-Link."""
from __future__ import annotations

import datetime

DOMAIN = "tplink"
COORDINATORS = "coordinators"
UNAVAILABLE_DEVICES = "unavailable_devices"
UNAVAILABLE_RETRY_DELAY = datetime.timedelta(seconds=300)

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=8)
MAX_DISCOVERY_RETRIES = 4

ATTR_CONFIG = "config"
ATTR_TOTAL_ENERGY_KWH = "total_energy_kwh"
ATTR_CURRENT_A = "current_a"

CONF_MODEL = "model"
CONF_SW_VERSION = "sw_ver"
CONF_EMETER_PARAMS = "emeter_params"
CONF_DIMMER = "dimmer"
CONF_DISCOVERY = "discovery"
CONF_LIGHT = "light"
CONF_STRIP = "strip"
CONF_SWITCH = "switch"
CONF_SENSOR = "sensor"

PLATFORMS = [CONF_LIGHT, CONF_SENSOR, CONF_SWITCH]
