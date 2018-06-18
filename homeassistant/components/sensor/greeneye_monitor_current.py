"""
Support for current sensors in a GreenEye Monitor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensors.greeneye_monitor_current/
"""
import logging

from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

from ..greeneye_monitor import (
    CONF_MONITOR_SERIAL_NUMBER,
    CONF_NET_METERING,
    CONF_NUMBER,
    DATA_GREENEYE_MONITOR,
)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['greeneye_monitor']

DATA_WATT_SECONDS = 'watt_seconds'

CURRENT_SENSOR_ICON = 'mdi:flash'

UNIT_WATTS = 'W'


async def async_setup_platform(
        hass,
        config,
        async_add_devices,
        discovery_info=None):
    """Set up a single GEM current sensor."""
    async_add_devices([
        CurrentSensor(
            discovery_info[CONF_MONITOR_SERIAL_NUMBER],
            discovery_info[CONF_NUMBER],
            discovery_info[CONF_NAME],
            discovery_info.get(CONF_NET_METERING, False))])


class CurrentSensor(Entity):
    """Entity showing power usage on one channel of the monitor."""

    should_poll = False

    def __init__(
            self,
            monitor_serial_number,
            number,
            name,
            net_metering):
        """Construct the entity."""
        self._monitor_serial_number = monitor_serial_number
        self._number = number
        self._channel = None
        self._name = name
        self._net_metering = net_metering

    async def async_added_to_hass(self):
        """Wait for and connect to the channel."""
        monitors = self.hass.data[DATA_GREENEYE_MONITOR]

        if not self._try_connect_to_monitor(monitors):
            monitors.add_listener(self._on_new_monitor)

    def _on_new_monitor(self, *args):
        monitors = self.hass.data[DATA_GREENEYE_MONITOR]
        if self._try_connect_to_monitor(monitors):
            monitors.remove_listener(self._on_new_monitor)

    async def async_will_remove_from_hass(self):
        """Remove listener from the channel."""
        if self._channel:
            self._channel.remove_listener(self._schedule_update)
        else:
            monitors = self.hass.data[DATA_GREENEYE_MONITOR]
            monitors.remove_listener(self._on_new_monitor)

    def _try_connect_to_monitor(self, monitors):
        monitor = monitors.monitors.get(self._monitor_serial_number, None)
        if not monitor:
            return False

        self._channel = monitor.channels[self._number - 1]
        self._channel.add_listener(self._schedule_update)

        return True

    def _schedule_update(self):
        self.async_schedule_update_ha_state(False)

    @property
    def unique_id(self):
        """Return a unique identifier for this channel."""
        return "{serial}-{number}".format(
            serial=self._monitor_serial_number,
            number=self._number)

    @property
    def name(self):
        """Return the name of the channel."""
        return self._name

    @property
    def state(self):
        """Return the current number of watts being used by the channel."""
        if not self._channel:
            return None

        return self._channel.watts

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for this channel (Watts)."""
        return UNIT_WATTS

    @property
    def icon(self):
        """Return the icon to use for this entity."""
        return CURRENT_SENSOR_ICON

    @property
    def device_state_attributes(self):
        """Return total wattseconds in the state dictionary."""
        if not self._channel:
            return None

        if self._net_metering:
            watt_seconds = self._channel.polarized_watt_seconds
        else:
            watt_seconds = self._channel.absolute_watt_seconds

        return {
            DATA_WATT_SECONDS: watt_seconds
        }
