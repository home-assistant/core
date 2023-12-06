"""Const for TP-Link."""
from __future__ import annotations

from typing import Final

import voluptuous as vol

from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)

DOMAIN = "tplink"
STORAGE_KEY: Final = DOMAIN
STORAGE_VERSION: Final = 1
STORAGE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTHENTICATION): {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }
    }
)

ATTR_CURRENT_A: Final = "current_a"
ATTR_CURRENT_POWER_W: Final = "current_power_w"
ATTR_TODAY_ENERGY_KWH: Final = "today_energy_kwh"
ATTR_TOTAL_ENERGY_KWH: Final = "total_energy_kwh"

CONF_CONNECTION_PARAMS: Final = "connection_params"
CONF_DEVICE_TYPE: Final = "device_type"
CONF_DIMMER: Final = "dimmer"
CONF_DISCOVERY: Final = "discovery"
CONF_LIGHT: Final = "light"
CONF_STRIP: Final = "strip"
CONF_SWITCH: Final = "switch"
CONF_SENSOR: Final = "sensor"

PLATFORMS: Final = [Platform.LIGHT, Platform.SENSOR, Platform.SWITCH]
