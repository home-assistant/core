"""
Support for pulse counters in a GreenEye Monitor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensors.greeneye_monitor_pulse/
"""
import logging

from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

from ..greeneye_monitor import (
    CONF_COUNTED_QUANTITY,
    CONF_COUNTED_QUANTITY_PER_PULSE,
    CONF_MONITOR_SERIAL_NUMBER,
    CONF_NUMBER,
    CONF_TIME_UNIT,
    DATA_GREENEYE_MONITOR,
    TIME_UNIT_HOUR,
    TIME_UNIT_MINUTE,
    TIME_UNIT_SECOND,
)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['greeneye_monitor']

DATA_PULSES = 'pulses'

COUNTER_ICON = 'mdi:counter'


async def async_setup_platform(
        hass,
        config,
        async_add_devices,
        discovery_info=None):
    """Set up a single GEM pulse counter."""
    async_add_devices([
        PulseCounter(
            discovery_info[CONF_MONITOR_SERIAL_NUMBER],
            discovery_info[CONF_NUMBER],
            discovery_info[CONF_NAME],
            discovery_info[CONF_COUNTED_QUANTITY],
            discovery_info.get(CONF_TIME_UNIT, TIME_UNIT_SECOND),
            discovery_info.get(CONF_COUNTED_QUANTITY_PER_PULSE, 1.0))])


class PulseCounter(Entity):
    """Entity showing rate of change in one pulse counter of the monitor."""

    should_poll = False

    def __init__(
            self,
            monitor_serial_number,
            number,
            name,
            counted_quantity,
            time_unit,
            counted_quantity_per_pulse):
        """Construct the entity."""
        self._monitor_serial_number = monitor_serial_number
        self._number = number
        self._counter = None
        self._name = name
        self._counted_quantity = counted_quantity
        self._counted_quantity_per_pulse = counted_quantity_per_pulse
        self._time_unit = time_unit

    async def async_added_to_hass(self):
        """Wait for and connect to the pulse counter."""
        monitors = self.hass.data[DATA_GREENEYE_MONITOR]

        if not self._try_connect_to_monitor(monitors):
            monitors.add_listener(self._on_new_monitor)

    def _on_new_monitor(self, *args):
        monitors = self.hass.data[DATA_GREENEYE_MONITOR]
        if self._try_connect_to_monitor(monitors):
            monitors.remove_listener(self._on_new_monitor)

    async def async_will_remove_from_hass(self):
        """Remove listener from the channel."""
        if self._counter:
            self._counter.remove_listener(self._schedule_update)
        else:
            monitors = self.hass.data[DATA_GREENEYE_MONITOR]
            monitors.remove_listener(self._on_new_monitor)

    def _try_connect_to_monitor(self, monitors):
        monitor = monitors.monitors.get(self._monitor_serial_number, None)
        if not monitor:
            return False

        self._counter = monitor.pulse_counters[self._number - 1]
        self._counter.add_listener(self._schedule_update)

        return True

    def _schedule_update(self):
        self.async_schedule_update_ha_state(False)

    @property
    def unique_id(self):
        """Return a unique identifier for this pulse counter."""
        return "{serial}-{number}".format(
            serial=self._monitor_serial_number,
            number=self._number)

    @property
    def name(self):
        """Return the name of the pulse counter."""
        return self._name

    @property
    def state(self):
        """Return the current rate of change for the given pulse counter."""
        if not self._counter or self._counter.pulses_per_second is None:
            return None

        return (self._counter.pulses_per_second *
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
    def icon(self):
        """Return the icon to use for this entity."""
        return COUNTER_ICON

    @property
    def device_state_attributes(self):
        """Return total pulses in the data dictionary."""
        if not self._counter:
            return None

        return {
            DATA_PULSES: self._counter.pulses
        }
