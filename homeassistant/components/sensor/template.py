"""
Allows the creation of a sensor that breaks out state_attributes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.template/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.sensor import ENTITY_ID_FORMAT, PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE,
    CONF_ICON_TEMPLATE, CONF_ENTITY_PICTURE_TEMPLATE, ATTR_ENTITY_ID,
    CONF_SENSORS, EVENT_HOMEASSISTANT_START, CONF_FRIENDLY_NAME_TEMPLATE)
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_ICON_TEMPLATE): cv.template,
    vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
    vol.Optional(CONF_FRIENDLY_NAME_TEMPLATE): cv.template,
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(ATTR_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): vol.Schema({cv.slug: SENSOR_SCHEMA}),
})


@asyncio.coroutine
# pylint: disable=unused-argument
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the template sensors."""
    sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        state_template = device_config[CONF_VALUE_TEMPLATE]
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        entity_picture_template = device_config.get(
            CONF_ENTITY_PICTURE_TEMPLATE)
        entity_ids = (device_config.get(ATTR_ENTITY_ID) or
                      state_template.extract_entities())
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        friendly_name_template = device_config.get(CONF_FRIENDLY_NAME_TEMPLATE)
        unit_of_measurement = device_config.get(ATTR_UNIT_OF_MEASUREMENT)

        state_template.hass = hass

        if icon_template is not None:
            icon_template.hass = hass

        if entity_picture_template is not None:
            entity_picture_template.hass = hass

        if friendly_name_template is not None:
            friendly_name_template.hass = hass

        sensors.append(
            SensorTemplate(
                hass,
                device,
                friendly_name,
                friendly_name_template,
                unit_of_measurement,
                state_template,
                icon_template,
                entity_picture_template,
                entity_ids)
            )
    if not sensors:
        _LOGGER.error("No sensors added")
        return False

    async_add_devices(sensors)
    return True


class SensorTemplate(Entity):
    """Representation of a Template Sensor."""

    def __init__(self, hass, device_id, friendly_name, friendly_name_template,
                 unit_of_measurement, state_template, icon_template,
                 entity_picture_template, entity_ids):
        """Initialize the sensor."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, device_id,
                                                  hass=hass)
        self._name = friendly_name
        self._friendly_name_template = friendly_name_template
        self._unit_of_measurement = unit_of_measurement
        self._template = state_template
        self._state = None
        self._icon_template = icon_template
        self._entity_picture_template = entity_picture_template
        self._icon = None
        self._entity_picture = None
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
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def entity_picture(self):
        """Return the entity_picture to use in the frontend, if any."""
        return self._entity_picture

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @asyncio.coroutine
    def async_update(self):
        """Update the state from the template."""
        try:
            self._state = self._template.async_render()
        except TemplateError as ex:
            if ex.args and ex.args[0].startswith(
                    "UndefinedError: 'None' has no attribute"):
                # Common during HA startup - so just a warning
                _LOGGER.warning('Could not render template %s,'
                                ' the state is unknown.', self._name)
                return
            self._state = None
            _LOGGER.error('Could not render template %s: %s', self._name, ex)

        for property_name, template in (
                ('_icon', self._icon_template),
                ('_entity_picture', self._entity_picture_template),
                ('_name', self._friendly_name_template)):
            if template is None:
                continue

            try:
                setattr(self, property_name, template.async_render())
            except TemplateError as ex:
                friendly_property_name = property_name[1:].replace('_', ' ')
                if ex.args and ex.args[0].startswith(
                        "UndefinedError: 'None' has no attribute"):
                    # Common during HA startup - so just a warning
                    _LOGGER.warning('Could not render %s template %s,'
                                    ' the state is unknown.',
                                    friendly_property_name, self._name)
                    return

                try:
                    setattr(self, property_name,
                            getattr(super(), property_name))
                except AttributeError:
                    _LOGGER.error('Could not render %s template %s: %s',
                                  friendly_property_name, self._name, ex)
