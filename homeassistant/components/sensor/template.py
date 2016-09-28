"""
Allows the creation of a sensor that breaks out state_attributes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.template/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import ENTITY_ID_FORMAT, PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE,
    ATTR_ENTITY_ID, CONF_SENSORS)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.helpers.event import track_state_change
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(ATTR_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): vol.Schema({cv.slug: SENSOR_SCHEMA}),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the template sensors."""
    sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        state_template = device_config[CONF_VALUE_TEMPLATE]
        entity_ids = (device_config.get(ATTR_ENTITY_ID) or
                      state_template.extract_entities())
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        unit_of_measurement = device_config.get(ATTR_UNIT_OF_MEASUREMENT)

        state_template.hass = hass

        sensors.append(
            SensorTemplate(
                hass,
                device,
                friendly_name,
                unit_of_measurement,
                state_template,
                entity_ids)
            )
    if not sensors:
        _LOGGER.error("No sensors added")
        return False
    add_devices(sensors)
    return True


class SensorTemplate(Entity):
    """Representation of a Template Sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, hass, device_id, friendly_name, unit_of_measurement,
                 state_template, entity_ids):
        """Initialize the sensor."""
        self.hass = hass
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, device_id,
                                            hass=hass)
        self._name = friendly_name
        self._unit_of_measurement = unit_of_measurement
        self._template = state_template
        self._state = None

        self.update()

        def template_sensor_state_listener(entity, old_state, new_state):
            """Called when the target device changes state."""
            self.update_ha_state(True)

        track_state_change(hass, entity_ids, template_sensor_state_listener)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    def update(self):
        """Get the latest data and update the states."""
        try:
            self._state = self._template.render()
        except TemplateError as ex:
            if ex.args and ex.args[0].startswith(
                    "UndefinedError: 'None' has no attribute"):
                # Common during HA startup - so just a warning
                _LOGGER.warning(ex)
                return
            self._state = None
            _LOGGER.error(ex)
