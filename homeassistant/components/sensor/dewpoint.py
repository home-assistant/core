"""
Allows the creation of a sensor that breaks out state_attributes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.template/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT, CONF_TEMPERATURE_TEMPLATE,
    CONF_HUMIDITY_TEMPLATE, ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_START)
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change
from homeassistant.util.temperature import calculate_dewpoint

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TEMPERATURE_TEMPLATE): cv.template,
    vol.Required(CONF_HUMIDITY_TEMPLATE): cv.template,
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(ATTR_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids
})


@asyncio.coroutine
# pylint: disable=unused-argument
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the sensor."""
    temperature_template = config[CONF_TEMPERATURE_TEMPLATE]
    humidity_template = config[CONF_HUMIDITY_TEMPLATE]
    entity_ids = (config.get(ATTR_ENTITY_ID) or
                  temperature_template.extract_entities() +
                  humidity_template.extract_entities())
    friendly_name = config.get(ATTR_FRIENDLY_NAME, 'Dewpoint')
    unit_of_measurement = config.get(ATTR_UNIT_OF_MEASUREMENT,
                                     hass.config.units.temperature_unit)

    temperature_template.hass = hass
    humidity_template.hass = hass

    async_add_devices([
        DewpointSensorTemplate(
            hass,
            friendly_name,
            unit_of_measurement,
            temperature_template,
            humidity_template,
            entity_ids)
    ])
    return True


class DewpointSensorTemplate(Entity):
    """Representation of a Template Sensor."""

    def __init__(self, hass, friendly_name, unit_of_measurement,
                 temperature_template, humidity_template, entity_ids):
        """Initialize the sensor."""
        self.hass = hass
        self._name = friendly_name
        self._unit_of_measurement = unit_of_measurement
        self._temperature_template = temperature_template
        self._humidity_template = humidity_template
        self._state = None
        self._entities = entity_ids

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def template_sensor_state_listener(entity, old_state, new_state):
            """Handle device state changes."""
            self.async_schedule_update_ha_state(True)

        @callback
        def template_sensor_startup(event):
            """Update template on startup."""
            async_track_state_change(
                self.hass, self._entities, template_sensor_state_listener)

            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_sensor_startup)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the default icon."""
        return 'mdi:water-percent'

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @asyncio.coroutine
    def _get_value_from_template(self, template_name, template):
        if template is not None:
            try:
                return template.async_render()
            except TemplateError as ex:
                friendly_name = template_name.replace('_', ' ').strip(' _')
                if ex.args and ex.args[0].startswith(
                        "UndefinedError: 'None' has no attribute"):
                    # Common during HA startup - so just a warning
                    _LOGGER.warning('Could not render %s template %s,'
                                    ' the state is unknown.',
                                    friendly_name, self._name)
                    return

                try:
                    return getattr(super(), template_name)
                except AttributeError:
                    _LOGGER.error('Could not render %s template %s: %s',
                                  template_name, self._name, ex)

    @asyncio.coroutine
    def _update_property_from_template(self, property_name, template):
        if template is not None:
            setattr(self, property_name,
                    self._get_value_from_template(property_name, template))

    @asyncio.coroutine
    def async_update(self):
        """Update the state from the templates."""
        temperature = yield from self._get_value_from_template(
            'temperature', self._temperature_template)
        humidity = yield from self._get_value_from_template(
            'humidity', self._humidity_template)
        dewpoint = calculate_dewpoint(float(temperature),
                                      float(humidity),
                                      self.unit_of_measurement)
        self._state = round(dewpoint, 1)
