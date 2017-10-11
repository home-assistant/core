"""
A sensor that monitors trends in other components.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.trend/
"""
import asyncio
from datetime import datetime, timezone
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, ENTITY_ID_FORMAT, PLATFORM_SCHEMA,
    DEVICE_CLASSES_SCHEMA)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME,
    CONF_DEVICE_CLASS, CONF_ENTITY_ID, CONF_FRIENDLY_NAME,
    STATE_UNKNOWN)
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.event import track_state_change

REQUIREMENTS = ['numpy==1.13.3']

_LOGGER = logging.getLogger(__name__)

ATTR_ATTRIBUTE = 'attribute'
ATTR_GRADIENT = 'gradient'
ATTR_MIN_GRADIENT = 'min_gradient'
ATTR_INVERT = 'invert'
ATTR_SAMPLE_DURATION = 'sample_duration'
ATTR_SAMPLE_COUNT = 'sample_count'

CONF_SENSORS = 'sensors'
CONF_ATTRIBUTE = 'attribute'
CONF_MIN_GRADIENT = 'min_gradient'
CONF_INVERT = 'invert'
CONF_SAMPLE_DURATION = 'sample_duration'

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_ATTRIBUTE): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_MIN_GRADIENT, default=0.0): vol.Coerce(float),
    vol.Optional(CONF_INVERT, default=False): cv.boolean,
    vol.Optional(CONF_SAMPLE_DURATION, default=0): cv.positive_int,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): vol.Schema({cv.slug: SENSOR_SCHEMA}),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the trend sensors."""
    sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        entity_id = device_config[ATTR_ENTITY_ID]
        attribute = device_config.get(CONF_ATTRIBUTE)
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        device_class = device_config.get(CONF_DEVICE_CLASS)
        invert = device_config[CONF_INVERT]
        sample_duration = device_config[CONF_SAMPLE_DURATION]
        min_gradient = device_config[CONF_MIN_GRADIENT]

        sensors.append(
            SensorTrend(
                hass, device, friendly_name, entity_id, attribute,
                device_class, invert, sample_duration, min_gradient)
            )
    if not sensors:
        _LOGGER.error("No sensors added")
        return False
    add_devices(sensors)
    return True


class SensorTrend(BinarySensorDevice):
    """Representation of a trend Sensor."""

    def __init__(self, hass, device_id, friendly_name, entity_id,
                 attribute, device_class, invert, sample_duration,
                 min_gradient):
        """Initialize the sensor."""
        self._hass = hass
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass)
        self._name = friendly_name
        self._entity_id = entity_id
        self._attribute = attribute
        self._device_class = device_class
        self._invert = invert
        self._sample_duration = sample_duration
        self._min_gradient = min_gradient
        self._gradient = None
        self._state = None
        self.samples = []

        @callback
        def trend_sensor_state_listener(entity, old_state, new_state):
            """Handle the target device state changes."""
            try:
                if self._attribute:
                    state = new_state.attributes.get(self._attribute)
                else:
                    state = new_state.state
                if state != STATE_UNKNOWN:
                    now = datetime.now(timezone.utc).timestamp()
                    self.samples.append((now, float(state)))
                    hass.async_add_job(self.async_update_ha_state(True))
            except (ValueError, TypeError) as ex:
                _LOGGER.error(ex)

        track_state_change(hass, entity_id, trend_sensor_state_listener)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the sensor class of the sensor."""
        return self._device_class

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ENTITY_ID: self._entity_id,
            ATTR_FRIENDLY_NAME: self._name,
            ATTR_INVERT: self._invert,
            ATTR_GRADIENT: self._gradient,
            ATTR_MIN_GRADIENT: self._min_gradient,
            ATTR_SAMPLE_DURATION: self._sample_duration,
            ATTR_SAMPLE_COUNT: len(self.samples),
        }

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and update the states."""
        import math
        import numpy as np

        # Remove outdated samples
        if self._sample_duration == 0:
            self.samples = self.samples[-2:]
        else:
            now = datetime.now(timezone.utc).timestamp()
            cutoff = now - self._sample_duration
            self.samples = [(t, v) for t, v in self.samples if t >= cutoff]

        if len(self.samples) < 2:
            return

        # Calculate gradient of linear trend
        timestamps = np.array([t for t, _ in self.samples])
        values = np.array([s for _, s in self.samples])
        coeffs = np.polyfit(timestamps, values, 1)
        self._gradient = coeffs[0]

        # Update state
        self._state = (
            abs(self._gradient) > abs(self._min_gradient) and
            math.copysign(self._gradient, self._min_gradient) == self._gradient
        )

        if self._invert:
            self._state = not self._state
