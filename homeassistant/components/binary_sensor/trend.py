"""
A sensor that monitors trands in other components.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.trend/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, ENTITY_ID_FORMAT, PLATFORM_SCHEMA,
    DEVICE_CLASSES_SCHEMA)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, ATTR_ENTITY_ID, CONF_SENSOR_CLASS,
    CONF_DEVICE_CLASS, STATE_UNKNOWN,)
from homeassistant.helpers.deprecation import get_deprecated
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.event import track_state_change

_LOGGER = logging.getLogger(__name__)
CONF_SENSORS = 'sensors'
CONF_ATTRIBUTE = 'attribute'
CONF_INVERT = 'invert'

SENSOR_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_ATTRIBUTE): cv.string,
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_INVERT, default=False): cv.boolean,
    vol.Optional(CONF_SENSOR_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
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
        device_class = get_deprecated(
            device_config, CONF_DEVICE_CLASS, CONF_SENSOR_CLASS)
        invert = device_config[CONF_INVERT]

        sensors.append(
            SensorTrend(
                hass, device, friendly_name, entity_id, attribute,
                device_class, invert)
            )
    if not sensors:
        _LOGGER.error("No sensors added")
        return False
    add_devices(sensors)
    return True


class SensorTrend(BinarySensorDevice):
    """Representation of a trend Sensor."""

    def __init__(self, hass, device_id, friendly_name,
                 target_entity, attribute, device_class, invert):
        """Initialize the sensor."""
        self._hass = hass
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass)
        self._name = friendly_name
        self._target_entity = target_entity
        self._attribute = attribute
        self._device_class = device_class
        self._invert = invert
        self._state = None
        self.from_state = None
        self.to_state = None

        @callback
        def trend_sensor_state_listener(entity, old_state, new_state):
            """Handle the target device state changes."""
            self.from_state = old_state
            self.to_state = new_state
            hass.async_add_job(self.async_update_ha_state(True))

        track_state_change(hass, target_entity,
                           trend_sensor_state_listener)

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
    def should_poll(self):
        """No polling needed."""
        return False

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and update the states."""
        if self.from_state is None or self.to_state is None:
            return
        if (self.from_state.state == STATE_UNKNOWN or
                self.to_state.state == STATE_UNKNOWN):
            return
        try:
            if self._attribute:
                from_value = float(
                    self.from_state.attributes.get(self._attribute))
                to_value = float(
                    self.to_state.attributes.get(self._attribute))
            else:
                from_value = float(self.from_state.state)
                to_value = float(self.to_state.state)

            self._state = to_value > from_value
            if self._invert:
                self._state = not self._state

        except (ValueError, TypeError) as ex:
            self._state = None
            _LOGGER.error(ex)
