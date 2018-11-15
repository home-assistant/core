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
    CONF_ICON_TEMPLATE, CONF_ENTITY_PICTURE_TEMPLATE, ATTR_ENTITY_ID,
    CONF_SENSORS, EVENT_HOMEASSISTANT_START, CONF_FRIENDLY_NAME_TEMPLATE,
    MATCH_ALL, CONF_DEVICE_CLASS)
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
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): vol.Schema({cv.slug: SENSOR_SCHEMA}),
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

        entity_ids = set()
        manual_entity_ids = device_config.get(ATTR_ENTITY_ID)
        invalid_templates = []

        for tpl_name, template in (
                (CONF_VALUE_TEMPLATE, state_template),
                (CONF_ICON_TEMPLATE, icon_template),
                (CONF_ENTITY_PICTURE_TEMPLATE, entity_picture_template),
                (CONF_FRIENDLY_NAME_TEMPLATE, friendly_name_template),
        ):
            if template is None:
                continue
            template.hass = hass

            if manual_entity_ids is not None:
                continue

            template_entity_ids = template.extract_entities()
            if template_entity_ids == MATCH_ALL:
                entity_ids = MATCH_ALL
                # Cut off _template from name
                invalid_templates.append(tpl_name[:-9])
            elif entity_ids != MATCH_ALL:
                entity_ids |= set(template_entity_ids)

        if invalid_templates:
            _LOGGER.warning(
                'Template sensor %s has no entity ids configured to track nor'
                ' were we able to extract the entities to track from the %s '
                'template(s). This entity will only be able to be updated '
                'manually.', device, ', '.join(invalid_templates))

        if manual_entity_ids is not None:
            entity_ids = manual_entity_ids
        elif entity_ids != MATCH_ALL:
            entity_ids = list(entity_ids)

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
                entity_ids,
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
                 entity_picture_template, entity_ids, device_class):
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
        self._device_class = device_class

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def template_sensor_state_listener(entity, old_state, new_state):
            """Handle device state changes."""
            self.async_schedule_update_ha_state(True)

        @callback
        def template_sensor_startup(event):
            """Update template on startup."""
            if self._entities != MATCH_ALL:
                # Track state change only for valid templates
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
        """Update the state from the template."""
        try:
            self._state = self._template.async_render()
        except TemplateError as ex:
            if ex.args and ex.args[0].startswith(
                    "UndefinedError: 'None' has no attribute"):
                # Common during HA startup - so just a warning
                _LOGGER.warning('Could not render template %s,'
                                ' the state is unknown.', self._name)
            else:
                self._state = None
                _LOGGER.error('Could not render template %s: %s', self._name,
                              ex)
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
                    continue

                try:
                    setattr(self, property_name,
                            getattr(super(), property_name))
                except AttributeError:
                    _LOGGER.error('Could not render %s template %s: %s',
                                  friendly_property_name, self._name, ex)
