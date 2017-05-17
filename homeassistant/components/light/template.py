"""
Support for Template lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.template/
"""
import logging
import asyncio

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ENTITY_ID_FORMAT, Light, SUPPORT_BRIGHTNESS)
from homeassistant.const import (
    CONF_VALUE_TEMPLATE, ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, STATE_ON,
    STATE_OFF, EVENT_HOMEASSISTANT_START
)
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.restore_state import async_get_last_state
from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [STATE_ON, STATE_OFF, 'true', 'false']

CONF_LIGHTS = 'lights'
ON_ACTION = 'turn_on'
OFF_ACTION = 'turn_off'
LEVEL_ACTION = 'set_level'
LEVEL_TEMPLATE = 'level_template'


LIGHT_SCHEMA = vol.Schema({
    vol.Required(ON_ACTION): cv.SCRIPT_SCHEMA,
    vol.Required(OFF_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_VALUE_TEMPLATE, default=None): cv.template,
    vol.Optional(LEVEL_ACTION, default=None): cv.SCRIPT_SCHEMA,
    vol.Optional(LEVEL_TEMPLATE, default=None): cv.template,
    vol.Optional(ATTR_FRIENDLY_NAME, default=None): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LIGHTS): vol.Schema({cv.slug: LIGHT_SCHEMA}),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up Template Lights."""
    lights = []

    for device, device_config in config[CONF_LIGHTS].items():
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        state_template = device_config[CONF_VALUE_TEMPLATE]
        on_action = device_config[ON_ACTION]
        off_action = device_config[OFF_ACTION]
        level_action = device_config[LEVEL_ACTION]
        level_template = device_config[LEVEL_TEMPLATE]
        entity_ids = []
        
        if state_template is not None:
            entity_ids = (device_config.get(ATTR_ENTITY_ID) or
                          state_template.extract_entities())
            state_template.hass = hass

        lights.append(
            LightTemplate(
                hass, device, friendly_name, state_template,
                on_action, off_action, level_action, level_template,
                entity_ids)
        )

    if not lights:
        _LOGGER.error("No lights added")
        return False

    async_add_devices(lights, True)
    return True


class LightTemplate(Light):
    """Representation of a templated Light, including dimmable."""

    def __init__(self, hass, device_id, friendly_name, state_template,
                 on_action, off_action, level_action, level_template,
                 entity_ids):
        """Initialize the light."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass)
        self._name = friendly_name
        self._template = state_template
        self._on_script = Script(hass, on_action)
        self._off_script = Script(hass, off_action)
        self._level_script = Script(hass, level_action)
        self._level_template = level_template
        
        self._state = False
        self._brightness = 0
        self._entities = entity_ids

        if self._template is not None:
            self._template.hass = self.hass
        if self._level_template is not None:
            self._level_template.hass = self.hass

    @property
    def brightness(self):
        """Return the brightness of the light."""
        if self._level_template is None:
            return None
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._level_script is not None:
            return SUPPORT_BRIGHTNESS

        return 0

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        state = yield from async_get_last_state(self.hass, self.entity_id)
        _LOGGER.error("Previous state thawed " + str(state))
        if state:
            self._state = state.state == STATE_ON

        @callback
        def template_light_state_listener(entity, old_state, new_state):
            """Handle target device state changes."""
            _LOGGER.error("state listener callback")
            self.hass.async_add_job(self.async_update_ha_state(True))

        @callback
        def template_light_startup(event):
            """Update template on startup."""
            _LOGGER.error("startup callback")
            async_track_state_change(
                self.hass, self._entities, template_light_state_listener)

            self.hass.async_add_job(self.async_update_ha_state(True))

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_light_startup)

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the light on."""
        _LOGGER.error(str(kwargs))
        _LOGGER.error(str(self._level_script))
        if ATTR_BRIGHTNESS in kwargs and self._level_script:
            self.hass.async_add_job(self._level_script.async_run(
                {"brightness": kwargs[ATTR_BRIGHTNESS]}))
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            self.hass.async_add_job(self._on_script.async_run())

        self._state = True

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the light off."""
        self.hass.async_add_job(self._off_script.async_run())
        self._state = False

    @asyncio.coroutine
    def async_update(self):
        """Update the state from the template."""
        try:
            if self._template is not None:
                state = self._template.async_render().lower()

                if state in _VALID_STATES:
                    self._state = state in ('true', STATE_ON)
                else:
                    _LOGGER.error(
                        'Received invalid light is_on state: %s. ' +
                        'Expected: %s',
                        state, ', '.join(_VALID_STATES))
                    self._state = None

            if self._level_template is not None:
                self._brightness = self._level_template.async_render()

        except TemplateError as ex:
            _LOGGER.error(ex)
            self._state = None

