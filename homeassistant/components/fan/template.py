"""
Support for Template fans.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/fan.template/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (
    CONF_FRIENDLY_NAME, CONF_VALUE_TEMPLATE, CONF_ENTITY_ID,
    STATE_ON, STATE_OFF, MATCH_ALL, EVENT_HOMEASSISTANT_START,
    STATE_UNKNOWN)

from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.components.fan import (SPEED_LOW, SPEED_MEDIUM,
                                          SPEED_HIGH, SUPPORT_SET_SPEED,
                                          SUPPORT_OSCILLATE, FanEntity,
                                          ATTR_SPEED, ATTR_OSCILLATING,
                                          ENTITY_ID_FORMAT)

from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)

CONF_FANS = 'fans'
CONF_SPEED_LIST = 'speeds'
CONF_SPEED_TEMPLATE = 'speed_template'
CONF_OSCILLATING_TEMPLATE = 'oscillating_template'
CONF_ON_ACTION = 'turn_on'
CONF_OFF_ACTION = 'turn_off'
CONF_SET_SPEED_ACTION = 'set_speed'
CONF_SET_OSCILLATING_ACTION = 'set_oscillating'

_VALID_STATES = [STATE_ON, STATE_OFF]
_VALID_OSC = [True, False]

FAN_SCHEMA = vol.Schema({
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Required(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_SPEED_TEMPLATE): cv.template,
    vol.Optional(CONF_OSCILLATING_TEMPLATE): cv.template,

    vol.Required(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
    vol.Required(CONF_OFF_ACTION): cv.SCRIPT_SCHEMA,

    vol.Optional(CONF_SET_SPEED_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_SET_OSCILLATING_ACTION): cv.SCRIPT_SCHEMA,

    vol.Optional(
        CONF_SPEED_LIST,
        default=[SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]
    ): cv.ensure_list,

    vol.Optional(CONF_ENTITY_ID): cv.entity_ids
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FANS): vol.Schema({cv.slug: FAN_SCHEMA}),
})


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None
):
    """Set up the Template Fans."""
    fans = []

    for device, device_config in config[CONF_FANS].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)

        state_template = device_config[CONF_VALUE_TEMPLATE]
        speed_template = device_config.get(CONF_SPEED_TEMPLATE)
        oscillating_template = device_config.get(
            CONF_OSCILLATING_TEMPLATE
        )

        on_action = device_config[CONF_ON_ACTION]
        off_action = device_config[CONF_OFF_ACTION]
        set_speed_action = device_config.get(CONF_SET_SPEED_ACTION)
        set_oscillating_action = device_config.get(CONF_SET_OSCILLATING_ACTION)

        speed_list = device_config[CONF_SPEED_LIST]

        entity_ids = set()
        manual_entity_ids = device_config.get(CONF_ENTITY_ID)

        for template in (state_template, speed_template, oscillating_template):
            if template is None:
                continue
            template.hass = hass

            if entity_ids == MATCH_ALL or manual_entity_ids is not None:
                continue

            template_entity_ids = template.extract_entities()
            if template_entity_ids == MATCH_ALL:
                entity_ids = MATCH_ALL
            else:
                entity_ids |= set(template_entity_ids)

        if manual_entity_ids is not None:
            entity_ids = manual_entity_ids
        elif entity_ids != MATCH_ALL:
            entity_ids = list(entity_ids)

        fans.append(
            TemplateFan(
                hass, device, friendly_name,
                state_template, speed_template, oscillating_template,
                on_action, off_action, set_speed_action,
                set_oscillating_action, speed_list, entity_ids
            )
        )

    async_add_devices(fans)


class TemplateFan(FanEntity):
    """A template fan component."""

    def __init__(self, hass, device_id, friendly_name,
                 state_template, speed_template, oscillating_template,
                 on_action, off_action, set_speed_action,
                 set_oscillating_action, speed_list, entity_ids):
        """Initialize the fan."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass)
        self._name = friendly_name

        self._template = state_template
        self._speed_template = speed_template
        self._oscillating_template = oscillating_template
        self._supported_features = 0

        self._on_script = Script(hass, on_action)
        self._off_script = Script(hass, off_action)

        self._set_speed_script = None
        if set_speed_action:
            self._set_speed_script = Script(hass, set_speed_action)

        self._set_oscillating_script = None
        if set_oscillating_action:
            self._set_oscillating_script = Script(hass, set_oscillating_action)

        self._state = STATE_OFF
        self._speed = None
        self._oscillating = None

        self._template.hass = self.hass
        if self._speed_template:
            self._speed_template.hass = self.hass
            self._supported_features |= SUPPORT_SET_SPEED
        if self._oscillating_template:
            self._oscillating_template.hass = self.hass
            self._supported_features |= SUPPORT_OSCILLATE

        self._entities = entity_ids
        # List of valid speeds
        self._speed_list = speed_list

    @property
    def name(self):
        """Return the display name of this fan."""
        return self._name

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def speed_list(self: ToggleEntity) -> list:
        """Get the list of available speeds."""
        return self._speed_list

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    @property
    def speed(self):
        """Return the current speed."""
        return self._speed

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._oscillating

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    # pylint: disable=arguments-differ
    async def async_turn_on(self, speed: str = None) -> None:
        """Turn on the fan."""
        await self._on_script.async_run()
        self._state = STATE_ON

        if speed is not None:
            await self.async_set_speed(speed)

    # pylint: disable=arguments-differ
    async def async_turn_off(self) -> None:
        """Turn off the fan."""
        await self._off_script.async_run()
        self._state = STATE_OFF

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if self._set_speed_script is None:
            return

        if speed in self._speed_list:
            self._speed = speed
            await self._set_speed_script.async_run({ATTR_SPEED: speed})
        else:
            _LOGGER.error(
                'Received invalid speed: %s. ' +
                'Expected: %s.',
                speed, self._speed_list)

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation of the fan."""
        if self._set_oscillating_script is None:
            return

        await self._set_oscillating_script.async_run(
            {ATTR_OSCILLATING: oscillating}
        )
        self._oscillating = oscillating

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def template_fan_state_listener(entity, old_state, new_state):
            """Handle target device state changes."""
            self.async_schedule_update_ha_state(True)

        @callback
        def template_fan_startup(event):
            """Update template on startup."""
            self.hass.helpers.event.async_track_state_change(
                self._entities, template_fan_state_listener)

            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_fan_startup)

    async def async_update(self):
        """Update the state from the template."""
        # Update state
        try:
            state = self._template.async_render()
        except TemplateError as ex:
            _LOGGER.error(ex)
            state = None
            self._state = None

        # Validate state
        if state in _VALID_STATES:
            self._state = state
        elif state == STATE_UNKNOWN:
            self._state = None
        else:
            _LOGGER.error(
                'Received invalid fan is_on state: %s. ' +
                'Expected: %s.',
                state, ', '.join(_VALID_STATES))
            self._state = None

        # Update speed if 'speed_template' is configured
        if self._speed_template is not None:
            try:
                speed = self._speed_template.async_render()
            except TemplateError as ex:
                _LOGGER.error(ex)
                speed = None
                self._state = None

            # Validate speed
            if speed in self._speed_list:
                self._speed = speed
            elif speed == STATE_UNKNOWN:
                self._speed = None
            else:
                _LOGGER.error(
                    'Received invalid speed: %s. ' +
                    'Expected: %s.',
                    speed, self._speed_list)
                self._speed = None

        # Update oscillating if 'oscillating_template' is configured
        if self._oscillating_template is not None:
            try:
                oscillating = self._oscillating_template.async_render()
            except TemplateError as ex:
                _LOGGER.error(ex)
                self._state = None

            # Validate osc
            if oscillating == 'True' or oscillating is True:
                self._oscillating = True
            elif oscillating == 'False' or oscillating is False:
                self._oscillating = False
            elif oscillating == STATE_UNKNOWN:
                self._oscillating = None
            else:
                _LOGGER.error(
                    'Received invalid oscillating: %s. ' +
                    'Expected: True/False.', oscillating)
                self._oscillating = None
