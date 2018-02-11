"""
Support for Axis binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.axis/
"""
from datetime import timedelta
import logging

from homeassistant.components.axis import AxisDeviceEvent
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import CONF_TRIGGER_TIME
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.util.dt import utcnow

DEPENDENCIES = ['axis']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Axis binary devices."""
    add_devices([AxisBinarySensor(hass, discovery_info)], True)


class AxisBinarySensor(AxisDeviceEvent, BinarySensorDevice):
    """Representation of a binary Axis event."""

    def __init__(self, hass, event_config):
        """Initialize the Axis binary sensor."""
        self.hass = hass
        self._state = False
        self._delay = event_config[CONF_TRIGGER_TIME]
        self._timer = None
        AxisDeviceEvent.__init__(self, event_config)

    @property
    def is_on(self):
        """Return true if event is active."""
        return self._state

    def update(self):
        """Get the latest data and update the state."""
        self._state = self.axis_event.is_tripped

    def _update_callback(self):
        """Update the sensor's state, if needed."""
        self.update()

        if self._timer is not None:
            self._timer()
            self._timer = None

        if self._delay > 0 and not self.is_on:
            # Set timer to wait until updating the state
            def _delay_update(now):
                """Timer callback for sensor update."""
                _LOGGER.debug("%s called delayed (%s sec) update",
                              self._name, self._delay)
                self.schedule_update_ha_state()
                self._timer = None

            self._timer = track_point_in_utc_time(
                self.hass, _delay_update,
                utcnow() + timedelta(seconds=self._delay))
        else:
            self.schedule_update_ha_state()
