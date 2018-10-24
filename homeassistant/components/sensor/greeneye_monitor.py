"""
Support for the sensors in a GreenEye Monitor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensors.greeneye_monitor_temperature/
"""
import logging

from homeassistant.const import CONF_NAME, CONF_TEMPERATURE_UNIT
from homeassistant.helpers.entity import Entity

from ..greeneye_monitor import (
    CONF_COUNTED_QUANTITY,
    CONF_COUNTED_QUANTITY_PER_PULSE,
    CONF_MONITOR_SERIAL_NUMBER,
    CONF_NET_METERING,
    CONF_NUMBER,
    CONF_SENSOR_TYPE,
    CONF_TIME_UNIT,
    DATA_GREENEYE_MONITOR,
    SENSOR_TYPE_CURRENT,
    SENSOR_TYPE_PULSE_COUNTER,
    SENSOR_TYPE_TEMPERATURE,
    TIME_UNIT_HOUR,
    TIME_UNIT_MINUTE,
    TIME_UNIT_SECOND,
)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['greeneye_monitor']

DATA_PULSES = 'pulses'
DATA_WATT_SECONDS = 'watt_seconds'

UNIT_WATTS = 'W'

COUNTER_ICON = 'mdi:counter'
CURRENT_SENSOR_ICON = 'mdi:flash'
TEMPERATURE_ICON = 'mdi:thermometer'


async def async_setup_platform(
        hass,
        config,
        async_add_devices,
        discovery_info=None):
    """Set up a single GEM temperature sensor."""
    sensor_type = discovery_info[CONF_SENSOR_TYPE]
    if sensor_type == SENSOR_TYPE_CURRENT:
        async_add_devices([
            CurrentSensor(
                discovery_info[CONF_MONITOR_SERIAL_NUMBER],
                discovery_info[CONF_NUMBER],
                discovery_info[CONF_NAME],
                discovery_info.get(CONF_NET_METERING, False))])
    elif sensor_type == SENSOR_TYPE_PULSE_COUNTER:
        async_add_devices([
            PulseCounter(
                discovery_info[CONF_MONITOR_SERIAL_NUMBER],
                discovery_info[CONF_NUMBER],
                discovery_info[CONF_NAME],
                discovery_info[CONF_COUNTED_QUANTITY],
                discovery_info.get(CONF_TIME_UNIT, TIME_UNIT_SECOND),
                discovery_info.get(CONF_COUNTED_QUANTITY_PER_PULSE, 1.0))])
    elif sensor_type == SENSOR_TYPE_TEMPERATURE:
        async_add_devices([
            TemperatureSensor(
                discovery_info[CONF_MONITOR_SERIAL_NUMBER],
                discovery_info[CONF_NUMBER],
                discovery_info[CONF_NAME],
                discovery_info[CONF_TEMPERATURE_UNIT])])


class GEMSensor(Entity):
    """Base class for GreenEye Monitor sensors."""

    should_poll = False

    def __init__(
            self,
            monitor_serial_number,
            name):
        """Construct the entity."""
        self._monitor_serial_number = monitor_serial_number
        self._name = name
        self._sensor = None

    @property
    def name(self):
        """Return the name of the channel."""
        return self._name

    async def async_added_to_hass(self):
        """Wait for and connect to the sensor."""
        monitors = self.hass.data[DATA_GREENEYE_MONITOR]

        if not self._try_connect_to_monitor(monitors):
            monitors.add_listener(self._on_new_monitor)

    def _on_new_monitor(self, *args):
        monitors = self.hass.data[DATA_GREENEYE_MONITOR]
        if self._try_connect_to_monitor(monitors):
            monitors.remove_listener(self._on_new_monitor)

    async def async_will_remove_from_hass(self):
        """Remove listener from the sensor."""
        if self._sensor:
            self._sensor.remove_listener(self._schedule_update)
        else:
            monitors = self.hass.data[DATA_GREENEYE_MONITOR]
            monitors.remove_listener(self._on_new_monitor)

    def _try_connect_to_monitor(self, monitors):
        monitor = monitors.monitors.get(self._monitor_serial_number, None)
        if not monitor:
            return False

        self._sensor = self._get_sensor(monitor)
        self._sensor.add_listener(self._schedule_update)

        return True

    def _get_sensor(self, monitor):
        raise NotImplementedError()

    def _schedule_update(self):
        self.async_schedule_update_ha_state(False)


class CurrentSensor(GEMSensor):
    """Entity showing power usage on one channel of the monitor."""

    icon = CURRENT_SENSOR_ICON
    unit_of_measurement = UNIT_WATTS

    def __init__(
            self,
            monitor_serial_number,
            number,
            name,
            net_metering):
        """Construct the entity."""
        super().__init__(monitor_serial_number, name)
        self._number = number
        self._net_metering = net_metering

    def _get_sensor(self, monitor):
        return monitor.channels[self._number - 1]

    @property
    def unique_id(self):
        """Return a unique identifier for this channel."""
        return "{serial}-current-{number}".format(
            serial=self._monitor_serial_number,
            number=self._number)

    @property
    def state(self):
        """Return the current number of watts being used by the channel."""
        if not self._sensor:
            return None

        return self._sensor.watts

    @property
    def device_state_attributes(self):
        """Return total wattseconds in the state dictionary."""
        if not self._sensor:
            return None

        if self._net_metering:
            watt_seconds = self._sensor.polarized_watt_seconds
        else:
            watt_seconds = self._sensor.absolute_watt_seconds

        return {
            DATA_WATT_SECONDS: watt_seconds
        }


class PulseCounter(GEMSensor):
    """Entity showing rate of change in one pulse counter of the monitor."""

    icon = COUNTER_ICON

    def __init__(
            self,
            monitor_serial_number,
            number,
            name,
            counted_quantity,
            time_unit,
            counted_quantity_per_pulse):
        """Construct the entity."""
        super().__init__(monitor_serial_number, name)
        self._number = number
        self._counted_quantity = counted_quantity
        self._counted_quantity_per_pulse = counted_quantity_per_pulse
        self._time_unit = time_unit

    def _get_sensor(self, monitor):
        return monitor.pulse_counters[self._number - 1]

    @property
    def unique_id(self):
        """Return a unique identifier for this pulse counter."""
        return "{serial}-pulse-{number}".format(
            serial=self._monitor_serial_number,
            number=self._number)

    @property
    def state(self):
        """Return the current rate of change for the given pulse counter."""
        if not self._sensor or self._sensor.pulses_per_second is None:
            return None

        return (self._sensor.pulses_per_second *
                self._counted_quantity_per_pulse *
                self._seconds_per_time_unit)

    @property
    def _seconds_per_time_unit(self):
        """Return the number of seconds in the given display time unit."""
        if self._time_unit == TIME_UNIT_SECOND:
            return 1
        if self._time_unit == TIME_UNIT_MINUTE:
            return 60
        if self._time_unit == TIME_UNIT_HOUR:
            return 3600

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for this pulse counter."""
        return self._counted_quantity + '/' + self._time_unit

    @property
    def device_state_attributes(self):
        """Return total pulses in the data dictionary."""
        if not self._sensor:
            return None

        return {
            DATA_PULSES: self._sensor.pulses
        }


class TemperatureSensor(GEMSensor):
    """Entity showing temperature from one temperature sensor."""

    icon = TEMPERATURE_ICON

    def __init__(self, monitor_serial_number, number, name, unit):
        """Construct the entity."""
        super().__init__(monitor_serial_number, name)
        self._number = number
        self._unit = unit

    def _get_sensor(self, monitor):
        return monitor.temperature_sensors[self._number - 1]

    @property
    def unique_id(self):
        """Return a unique identifier for this temperature sensor."""
        return "{serial}-temp-{number}".format(
            serial=self._monitor_serial_number,
            number=self._number)

    @property
    def state(self):
        """Return the current temperature being reported by this sensor."""
        if not self._sensor:
            return None

        return self._sensor.temperature

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for this sensor (user specified)."""
        return self._unit
