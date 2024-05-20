"""Const for TP-Link."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN = "tplink"

DISCOVERY_TIMEOUT = 5  # Home Assistant will complain if startup takes > 10s
CONNECT_TIMEOUT = 5

# Identifier used for primary control state.
PRIMARY_STATE_ID = "state"

ATTR_CURRENT_A: Final = "current_a"
ATTR_CURRENT_POWER_W: Final = "current_power_w"
ATTR_TODAY_ENERGY_KWH: Final = "today_energy_kwh"
ATTR_TOTAL_ENERGY_KWH: Final = "total_energy_kwh"

CONF_DEVICE_CONFIG: Final = "device_config"

PLATFORMS: Final = [Platform.LIGHT, Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]
