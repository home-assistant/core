"""Const for TP-Link."""
from __future__ import annotations

from typing import Final

DOMAIN = "tplink"

ATTR_CURRENT_A: Final = "current_a"
ATTR_CURRENT_POWER_W: Final = "current_power_w"
ATTR_TODAY_ENERGY_KWH: Final = "today_energy_kwh"
ATTR_TOTAL_ENERGY_KWH: Final = "total_energy_kwh"

CONF_DIMMER: Final = "dimmer"
CONF_DISCOVERY: Final = "discovery"
CONF_LIGHT: Final = "light"
CONF_STRIP: Final = "strip"
CONF_SWITCH: Final = "switch"
CONF_SENSOR: Final = "sensor"

PLATFORMS: Final = [CONF_LIGHT, CONF_SENSOR, CONF_SWITCH]
