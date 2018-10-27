"""
Support for w800rf32 binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.w800rf32/

# Example configuration.yaml entry

binary_sensor:
  - platform: w800rf32
    devices:
      c1:
        name: motion_hall
        off_delay: 5
        device_class: Motion
      c2:
        name: motion_kitchen
        device_class: Motion
        fire_event: True

"""
import logging

import voluptuous as vol

from homeassistant.components import w800rf32
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA, PLATFORM_SCHEMA, BinarySensorDevice)
from homeassistant.components.w800rf32 import (CONF_FIRE_EVENT, CONF_OFF_DELAY)
from homeassistant.const import (CONF_DEVICE_CLASS, CONF_NAME, ATTR_NAME, CONF_DEVICES)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import event as evt
from homeassistant.util import dt as dt_util


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['w800rf32']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {
        cv.string: vol.Schema({
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean,
            vol.Optional(CONF_OFF_DELAY):
            vol.Any(cv.time_period, cv.positive_timedelta)
        })
    },
}, extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Binary Sensor platform to w800rf32."""
    import W800rf32 as w800rf32mod
    sensors = []

    # device_id --> "c1 or a3" X10 device. entity (type dictionary) --> name, device_class etc
    for device_id, entity in config[CONF_DEVICES].items():

        if device_id in w800rf32.W800_DEVICES:
            continue

        _LOGGER.debug("Add %s w800rf32.binary_sensor (class %s)",
                      entity[ATTR_NAME], entity.get(CONF_DEVICE_CLASS))

        event = None  # None until an event happens
        device = w800rf32BinarySensor(
            event, entity.get(CONF_NAME), entity.get(CONF_DEVICE_CLASS),
            entity[CONF_FIRE_EVENT], entity.get(CONF_OFF_DELAY))

        sensors.append(device)
        w800rf32.W800_DEVICES[device_id] = device

    add_entities(sensors)

    def binary_sensor_update(event):
        """Call for control updates from the w800rf32 gateway."""
        sensor = None

        if not isinstance(event, w800rf32mod.W800rf32Event):
            return

        # make sure it's lowercase
        device_id = event.device.lower()

        # get the name, ex: motion_hall
        if device_id in w800rf32.W800_DEVICES:
            sensor = w800rf32.W800_DEVICES[device_id]

        if sensor is None:
            return
        elif not isinstance(sensor, w800rf32BinarySensor):
            return
        else:
            _LOGGER.debug(
                "Binary sensor update (Device ID: %s Class: %s)",
                event.device,
                event.device.__class__.__name__)

        w800rf32.apply_received_command(event)

        if (sensor.is_on and sensor.off_delay is not None and
                sensor.delay_listener is None):

            def off_delay_listener(now):
                """Switch device off after a delay."""
                sensor.delay_listener = None
                sensor.update_state(False)

            sensor.delay_listener = evt.track_point_in_time(
                hass, off_delay_listener, dt_util.utcnow() + sensor.off_delay)

    # Subscribe to main w800rf32 events
    if binary_sensor_update not in w800rf32.RECEIVED_EVT_SUBSCRIBERS:
        w800rf32.RECEIVED_EVT_SUBSCRIBERS.append(binary_sensor_update)


class w800rf32BinarySensor(BinarySensorDevice):
    """A representation of a w800rf32 binary sensor."""

    def __init__(self, event, name, device_class=None,
                 should_fire=False, off_delay=None):
        """Initialize the w800rf32 sensor."""
        self.event = event
        self._name = name
        self._should_fire_event = should_fire
        self._device_class = device_class
        self._off_delay = off_delay
        self._state = False
        self.delay_listener = None


    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def should_fire_event(self):
        """Return is the device must fire event."""
        return self._should_fire_event

    @property
    def device_class(self):
        """Return the sensor class."""
        return self._device_class

    @property
    def off_delay(self):
        """Return the off_delay attribute value."""
        return self._off_delay

    @property
    def is_on(self):
        """Return true if the sensor state is True."""
        return self._state

    def update_state(self, state):
        """Update the state of the device."""
        self._state = state
        self.schedule_update_ha_state()
