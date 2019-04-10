"""
Allows the creation of a sensor that breaks out state_attributes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.template/
"""
import logging
from typing import Optional

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.sensor import ENTITY_ID_FORMAT, \
    PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE,
    CONF_ICON_TEMPLATE, CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_SENSORS, CONF_FRIENDLY_NAME_TEMPLATE,
    CONF_DEVICE_CLASS)
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import async_track_template_result

_LOGGER = logging.getLogger(__name__)

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_ICON_TEMPLATE): cv.template,
    vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
    vol.Optional(CONF_FRIENDLY_NAME_TEMPLATE): cv.template,
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(ATTR_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the template sensors."""
    sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        state_template = device_config[CONF_VALUE_TEMPLATE]
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        entity_picture_template = device_config.get(
            CONF_ENTITY_PICTURE_TEMPLATE)
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        friendly_name_template = device_config.get(CONF_FRIENDLY_NAME_TEMPLATE)
        unit_of_measurement = device_config.get(ATTR_UNIT_OF_MEASUREMENT)
        device_class = device_config.get(CONF_DEVICE_CLASS)

        for template in (
                state_template,
                icon_template,
                entity_picture_template,
                friendly_name_template,
        ):
            if template is None:
                continue
            template.hass = hass

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
                device_class)
            )
    if not sensors:
        _LOGGER.error("No sensors added")
        return False

    async_add_entities(sensors)
    return True


class SensorTemplate(Entity):
    """Representation of a Template Sensor."""

    def __init__(self, hass, device_id, friendly_name, friendly_name_template,
                 unit_of_measurement, state_template, icon_template,
                 entity_picture_template, device_class):
        """Initialize the sensor."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, device_id,
                                                  hass=hass)
        self._unit_of_measurement = unit_of_measurement
        self._device_class = device_class

        self._state = None
        self._templates = {
            state_template: '_state',
        }
        self._name = friendly_name
        if friendly_name_template is not None:
            self._templates[friendly_name_template] = '_name'
        self._icon = None
        if icon_template is not None:
            self._templates[icon_template] = '_icon'
        self._entity_picture = None
        if entity_picture_template is not None:
            self._templates[entity_picture_template] = '_entity_picture'
        self._callbacks = []

    def _template_error(self, prop, error):
        friendly_property_name = prop[1:].replace('_', ' ')
        if error.args and error.args[0].startswith(
                "UndefinedError: 'None' has no attribute"):
            # Common during HA startup - so just a warning
            _LOGGER.warning('Could not render %s template %s,'
                            ' the state is unknown.',
                            friendly_property_name, self._name)
        else:
            _LOGGER.error('Could not render %s template %s',
                          friendly_property_name, self._name,
                          exc_info=error)

    @callback
    def _template_changed(self, event, template, last_result, result):
        prop = self._templates[template]
        if isinstance(result, TemplateError):
            self._template_error(prop, result)
            return
        setattr(self, prop, result)
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Register callbacks."""
        for template in self._templates:
            info = async_track_template_result(
                self.hass, template,
                self._template_changed)
            self._callbacks.append(info)

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
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._device_class

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

    async def async_update(self):
        """Force update of the state from the template."""
        for call in self._callbacks:
            call.async_refresh()
