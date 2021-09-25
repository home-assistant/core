"""Const for TP-Link."""
from __future__ import annotations

DOMAIN = "tplink"

ATTR_CURRENT_A = "current_a"
ATTR_CURRENT_POWER_W = "current_power_w"
ATTR_TODAY_ENERGY_KWH = "today_energy_kwh"
ATTR_TOTAL_ENERGY_KWH = "total_energy_kwh"

MAC_ADDRESS_LEN = 17
CONF_LEGACY_ENTRY_ID = "legacy_entry_id"
DISCOVERED_DEVICES = "discovered_devices"

CONF_EMETER_PARAMS = "emeter_params"
CONF_DIMMER = "dimmer"
CONF_DISCOVERY = "discovery"
CONF_LIGHT = "light"
CONF_STRIP = "strip"
CONF_SWITCH = "switch"
CONF_SENSOR = "sensor"

PLATFORMS = [CONF_LIGHT, CONF_SENSOR, CONF_SWITCH]
