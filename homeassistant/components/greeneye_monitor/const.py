"""Shared constants for the greeneye_monitor integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from greeneye import Monitors

CONF_CHANNELS = "channels"
CONF_COUNTED_QUANTITY = "counted_quantity"
CONF_COUNTED_QUANTITY_PER_PULSE = "counted_quantity_per_pulse"
CONF_MONITOR_SERIAL_NUMBER = "monitor"
CONF_MONITORS = "monitors"
CONF_NET_METERING = "net_metering"
CONF_NUMBER = "number"
CONF_PULSE_COUNTERS = "pulse_counters"
CONF_SERIAL_NUMBER = "serial_number"
CONF_TEMPERATURE_SENSORS = "temperature_sensors"
CONF_TIME_UNIT = "time_unit"
CONF_VOLTAGE_SENSORS = "voltage"

DOMAIN = "greeneye_monitor"
DATA_GREENEYE_MONITOR: HassKey[Monitors] = HassKey(DOMAIN)

SENSOR_TYPE_CURRENT = "current_sensor"
SENSOR_TYPE_PULSE_COUNTER = "pulse_counter"
SENSOR_TYPE_TEMPERATURE = "temperature_sensor"
SENSOR_TYPE_VOLTAGE = "voltage_sensor"

TEMPERATURE_UNIT_CELSIUS = "C"
