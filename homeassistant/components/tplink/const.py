"""Const for TP-Link."""

from __future__ import annotations

from typing import Final, TypedDict

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import ATTR_VOLTAGE, Platform

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

PLATFORMS: Final = [Platform.LIGHT, Platform.SENSOR, Platform.SWITCH]


class EntityExtras(TypedDict):
    """Class to define additional properties to be set on feature based entities."""

    key: str | None
    device_class: str | None
    state_class: str | None


ENTITY_EXTRAS: Final = {
    "current_consumption": EntityExtras(
        key=ATTR_CURRENT_POWER_W,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "consumption_total": EntityExtras(
        key=ATTR_TOTAL_ENERGY_KWH,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "consumption_today": EntityExtras(
        key=ATTR_TODAY_ENERGY_KWH,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "voltage": EntityExtras(
        key=ATTR_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "current": EntityExtras(
        key=ATTR_CURRENT_A,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "temperature": EntityExtras(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}
