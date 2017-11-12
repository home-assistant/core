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
    DEVICE_CLASSES_SCHEMA)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, ATTR_ENTITY_ID, CONF_VALUE_TEMPLATE,
    CONF_SENSORS, CONF_DEVICE_CLASS, EVENT_HOMEASSISTANT_START)
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import (
    async_track_state_change, async_track_same_state)

_LOGGER = logging.getLogger(__name__)

CONF_DELAY_ON = 'delay_on'
CONF_DELAY_OFF = 'delay_off'

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_DELAY_ON):
        vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_DELAY_OFF):
        vol.All(cv.time_period, cv.positive_timedelta),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): vol.Schema({cv.slug: SENSOR_SCHEMA}),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up template binary sensors."""
    sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        value_template = device_config[CONF_VALUE_TEMPLATE]
        entity_ids = (device_config.get(ATTR_ENTITY_ID) or
                      value_template.extract_entities())
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        device_class = device_config.get(CONF_DEVICE_CLASS)
        delay_on = device_config.get(CONF_DELAY_ON)
        delay_off = device_config.get(CONF_DELAY_OFF)

        if value_template is not None:
            value_template.hass = hass

        sensors.append(
            BinarySensorTemplate(
                hass, device, friendly_name, device_class, value_template,
                entity_ids, delay_on, delay_off)
            )
    if not sensors:
        _LOGGER.error("No sensors added")
        return False

    async_add_devices(sensors)
    return True


class BinarySensorTemplate(BinarySensorDevice):
    """A virtual binary sensor that triggers from another sensor."""

    def __init__(self, hass, device, friendly_name, device_class,
                 value_template, entity_ids, delay_on, delay_off):
        """Initialize the Template binary sensor."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device, hass=hass)
        self._name = friendly_name
        self._device_class = device_class
        self._template = value_template
        self._state = None
        self._entities = entity_ids
        self._delay_on = delay_on
        self._delay_off = delay_off

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def template_bsensor_state_listener(entity, old_state, new_state):
            """Handle the target device state changes."""
            self.async_check_state()

        @callback
        def template_bsensor_startup(event):
            """Update template on startup."""
            async_track_state_change(
                self.hass, self._entities, template_bsensor_state_listener)

            self.hass.async_add_job(self.async_check_state)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_bsensor_startup)

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

    @callback
    def _async_render(self):
        """Get the state of template."""
        try:
            return self._template.async_render().lower() == 'true'
        except TemplateError as ex:
            if ex.args and ex.args[0].startswith(
                    "UndefinedError: 'None' has no attribute"):
                # Common during HA startup - so just a warning
                _LOGGER.warning("Could not render template %s, "
                                "the state is unknown", self._name)
                return
            _LOGGER.error("Could not render template %s: %s", self._name, ex)

    @callback
    def async_check_state(self):
        """Update the state from the template."""
        state = self._async_render()

        # return if the state don't change or is invalid
        if state is None or state == self.state:
            return

        @callback
        def set_state():
            """Set state of template binary sensor."""
            self._state = state
            self.async_schedule_update_ha_state()

        # state without delay
        if (state and not self._delay_on) or \
                (not state and not self._delay_off):
            set_state()
            return

        period = self._delay_on if state else self._delay_off
        async_track_same_state(
            self.hass, period, set_state, entity_ids=self._entities,
            async_check_same_func=lambda *args: self._async_render() == state)
