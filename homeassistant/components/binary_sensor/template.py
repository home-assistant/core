"""
Support for exposing a templated binary sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.template/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, ENTITY_ID_FORMAT, PLATFORM_SCHEMA,
    SENSOR_CLASSES_SCHEMA)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, ATTR_ENTITY_ID, CONF_VALUE_TEMPLATE,
    CONF_SENSOR_CLASS, CONF_SENSORS)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.event import track_state_change
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(CONF_SENSOR_CLASS, default=None): SENSOR_CLASSES_SCHEMA
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): vol.Schema({cv.slug: SENSOR_SCHEMA}),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup template binary sensors."""
    sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        value_template = device_config[CONF_VALUE_TEMPLATE]
        entity_ids = (device_config.get(ATTR_ENTITY_ID) or
                      value_template.extract_entities())
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        sensor_class = device_config.get(CONF_SENSOR_CLASS)

        if value_template is not None:
            value_template.hass = hass

        sensors.append(
            BinarySensorTemplate(
                hass,
                device,
                friendly_name,
                sensor_class,
                value_template,
                entity_ids)
            )
    if not sensors:
        _LOGGER.error('No sensors added')
        return False
    add_devices(sensors)

    return True


class BinarySensorTemplate(BinarySensorDevice):
    """A virtual binary sensor that triggers from another sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, hass, device, friendly_name, sensor_class,
                 value_template, entity_ids):
        """Initialize the Template binary sensor."""
        self.hass = hass
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, device,
                                            hass=hass)
        self._name = friendly_name
        self._sensor_class = sensor_class
        self._template = value_template
        self._state = None

        self.update()

        @callback
        def template_bsensor_state_listener(entity, old_state, new_state):
            """Called when the target device changes state."""
            hass.loop.create_task(self.async_update_ha_state(True))

        track_state_change(hass, entity_ids, template_bsensor_state_listener)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def sensor_class(self):
        """Return the sensor class of the sensor."""
        return self._sensor_class

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and update the state."""
        try:
            self._state = self._template.async_render().lower() == 'true'
        except TemplateError as ex:
            if ex.args and ex.args[0].startswith(
                    "UndefinedError: 'None' has no attribute"):
                # Common during HA startup - so just a warning
                _LOGGER.warning(ex)
                return
            _LOGGER.error(ex)
            self._state = False
