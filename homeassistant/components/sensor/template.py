"""
homeassistant.components.sensor.template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows the creation of a sensor that breaks out state_attributes
from other entities.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.template/
"""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_state_change
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, CONF_VALUE_TEMPLATE, ATTR_UNIT_OF_MEASUREMENT)

from homeassistant.util import template

_LOGGER = logging.getLogger(__name__)

CONF_SENSORS = 'sensors'
CONF_ENTITIES = 'entities'

DOT = '.'
QUOTED_DOT = '__________'


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the sensors. """

    sensors = []
    if config.get(CONF_SENSORS) is None:
        _LOGGER.error("Missing configuration data for sensor platfoprm")
        return False

    for device in config[CONF_SENSORS]:
        device_config = config[CONF_SENSORS].get(device)
        if device_config is None:
            _LOGGER.error("Missing configuration data for sensor %s", device)
            continue
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        unit_of_measurement = device_config.get(ATTR_UNIT_OF_MEASUREMENT)
        state_template = device_config.get(CONF_VALUE_TEMPLATE)
        if state_template is None:
            _LOGGER.error(
                "Missing %s for sensor %s", CONF_VALUE_TEMPLATE, device)
            continue
        dependencies = device_config.get(CONF_ENTITIES, [])
        sensors.append(
            SensorTemplate(
                hass,
                device,
                friendly_name,
                unit_of_measurement,
                state_template,
                dependencies)
            )
    if sensors is None:
        _LOGGER.error("No sensors added.")
        return False
    add_devices(sensors)
    return True


class SensorTemplate(Entity):
    """ Represents a Template Sensor. """

    # pylint: disable=too-many-arguments
    def __init__(self,
                 hass,
                 entity_name,
                 friendly_name,
                 unit_of_measurement,
                 state_template,
                 dependencies):
        self.hass = hass
        # self.entity_id = entity_name
        self._name = entity_name
        self._friendly_name = friendly_name
        self._unit_of_measurement = unit_of_measurement
        self._template = state_template
        self._entities = dependencies
        self._state = ''

        # Quote entity names in template. So replace sun.sun with sunQUOTEsun
        # the template engine uses dots!
        for entity in self._entities:
            self._template = self._template.replace(
                entity, entity.replace(DOT, QUOTED_DOT))

        def _update_callback(_entity_id, _old_state, _new_state):
            """ Called when the target device changes state. """
            self.update_ha_state(True)

        for target in dependencies:
            track_state_change(hass, target, _update_callback)
        self.update()

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def unit_of_measurement(self):
        """ Returns the unit_of_measurement of the device. """
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """ Tells Home Assistant not to poll this entity. """
        return False

    @property
    def state_attributes(self):
        attr = {}

        if self._friendly_name:
            attr[ATTR_FRIENDLY_NAME] = self._friendly_name

        return attr

    def update(self):
        self._state = self._renderer()

    def _renderer(self):
        """Render sensor value."""
        render_dictionary = {}
        for entity in self._entities:
            hass_entity = self.hass.states.get(entity)
            if hass_entity is None:
                continue
            key = entity.replace(DOT, QUOTED_DOT)
            render_dictionary[key] = hass_entity

        return template.render(self.hass, self._template, render_dictionary)
