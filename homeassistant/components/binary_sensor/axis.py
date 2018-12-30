"""
Support for Axis binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.axis/
"""
from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import (
    ATTR_LOCATION, CONF_EVENT, CONF_NAME, CONF_TRIGGER_TIME)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

DEPENDENCIES = ['axis']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Axis binary devices."""
    add_entities([AxisBinarySensor(discovery_info)], True)


class AxisBinarySensor(BinarySensorDevice):
    """Representation of a binary Axis event."""

    def __init__(self, event_config):
        """Initialize the Axis binary sensor."""
        self.axis_event = event_config[CONF_EVENT]
        self.device_name = event_config[CONF_NAME]
        self.location = event_config[ATTR_LOCATION]
        self.delay = event_config[CONF_TRIGGER_TIME]
        self.remove_timer = None

    async def async_added_to_hass(self):
        """Subscribe sensors events."""
        self.axis_event.callback = self._update_callback

    def _update_callback(self):
        """Update the sensor's state, if needed."""
        if self.remove_timer is not None:
            self.remove_timer()
            self.remove_timer = None

        if self.delay == 0 or self.is_on:
            self.schedule_update_ha_state()
        else:  # Run timer to delay updating the state
            @callback
            def _delay_update(now):
                """Timer callback for sensor update."""
                _LOGGER.debug("%s called delayed (%s sec) update",
                              self.name, self.delay)
                self.async_schedule_update_ha_state()
                self.remove_timer = None

            self.remove_timer = async_track_point_in_utc_time(
                self.hass, _delay_update,
                utcnow() + timedelta(seconds=self.delay))

    @property
    def is_on(self):
        """Return true if event is active."""
        return self.axis_event.is_tripped

    @property
    def name(self):
        """Return the name of the event."""
        return '{}_{}_{}'.format(
            self.device_name, self.axis_event.event_type, self.axis_event.id)

    @property
    def device_class(self):
        """Return the class of the event."""
        return self.axis_event.event_class

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the event."""
        attr = {}

        attr[ATTR_LOCATION] = self.location

        return attr
