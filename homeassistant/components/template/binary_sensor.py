"""
Support for exposing a templated binary sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.template/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, ENTITY_ID_FORMAT, PLATFORM_SCHEMA,
    DEVICE_CLASSES_SCHEMA)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, CONF_VALUE_TEMPLATE,
    CONF_ICON_TEMPLATE, CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_SENSORS, CONF_DEVICE_CLASS)
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import (
    async_call_later, async_track_template_result)
from homeassistant.util import str_to_bool

_LOGGER = logging.getLogger(__name__)

CONF_DELAY_ON = 'delay_on'
CONF_DELAY_OFF = 'delay_off'

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_ICON_TEMPLATE): cv.template,
    vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_DELAY_ON):
        vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_DELAY_OFF):
        vol.All(cv.time_period, cv.positive_timedelta),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up template binary sensors."""
    sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        value_template = device_config[CONF_VALUE_TEMPLATE]
        value_template.hass = hass
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        if icon_template:
            icon_template.hass = hass
        entity_picture_template = device_config.get(
            CONF_ENTITY_PICTURE_TEMPLATE)
        if entity_picture_template:
            entity_picture_template.hass = hass

        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        device_class = device_config.get(CONF_DEVICE_CLASS)
        delay_on = device_config.get(CONF_DELAY_ON)
        delay_off = device_config.get(CONF_DELAY_OFF)

        sensors.append(
            BinarySensorTemplate(
                hass, device, friendly_name, device_class, value_template,
                icon_template, entity_picture_template,
                delay_on, delay_off)
            )
    if not sensors:
        _LOGGER.error("No sensors added")
        return False

    async_add_entities(sensors)
    return True


class BinarySensorTemplate(BinarySensorDevice):
    """A virtual binary sensor that triggers from another sensor."""

    def __init__(self, hass, device, friendly_name, device_class,
                 value_template, icon_template, entity_picture_template,
                 delay_on, delay_off):
        """Initialize the Template binary sensor."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device, hass=hass)
        self._name = friendly_name
        self._device_class = device_class
        self._template = value_template
        self._state = None
        self._icon_template = icon_template
        self._entity_picture_template = entity_picture_template
        self._icon = None
        self._entity_picture = None
        self._delay_on = delay_on
        self._delay_off = delay_off
        self._delay_cancel = None
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
    def _async_state_template_changed(
            self, event, template, last_result, result):
        self._update_state(result)

    def _update_state(self, result):
        if self._delay_cancel:
            self._delay_cancel()
            self._delay_cancel = None

        if isinstance(result, TemplateError):
            self._template_error('_state', result)
            self._state = None
            self.async_schedule_update_ha_state()
            return

        state = str_to_bool(result)
        if state == self._state:
            return

        @callback
        def set_state(now):
            """Set state of template binary sensor."""
            self._state = state
            self.async_schedule_update_ha_state()

        # state without delay
        if (state and not self._delay_on) or \
                (not state and not self._delay_off):
            set_state(None)
            return

        delay = (self._delay_on if state else self._delay_off).seconds
        # state with delay. Cancelled if template result changes.
        self._delay_cancel = async_call_later(
            self.hass, delay,
            set_state)

    @callback
    def _async_template_changed(self, event, template, last_result, result):
        prop = ('_icon' if template == self._icon_template
                else '_entity_picture')
        if isinstance(result, TemplateError):
            self._template_error(prop, result)
            return
        setattr(self, prop, result)
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Register callbacks."""
        info = async_track_template_result(
            self.hass, self._template,
            self._async_state_template_changed)
        self._callbacks.append(info)

        if self._icon_template:
            info = async_track_template_result(
                self.hass, self._icon_template,
                self._async_template_changed)
            self._callbacks.append(info)
        if self._entity_picture_template:
            info = async_track_template_result(
                self.hass, self._entity_picture_template,
                self._async_template_changed)
            self._callbacks.append(info)

    async def async_update(self):
        """Force update of the state from the template."""
        for call in self._callbacks:
            call.async_refresh()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def entity_picture(self):
        """Return the entity_picture to use in the frontend, if any."""
        return self._entity_picture

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
