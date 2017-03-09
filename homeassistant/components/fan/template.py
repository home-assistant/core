"""
Support for fans which integrates with other components.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/fan/template
"""

from homeassistant.components.fan import (SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH,
                                          FanEntity, SUPPORT_SET_SPEED,
                                          SUPPORT_OSCILLATE, SUPPORT_DIRECTION)
from homeassistant.const import STATE_OFF


FAN_NAME = 'Living Room Fan'
FAN_ENTITY_ID = 'fan.living_room_fan'

DEMO_SUPPORT = SUPPORT_SET_SPEED | SUPPORT_OSCILLATE | SUPPORT_DIRECTION


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup demo fan platform."""
    add_devices_callback([
        DemoFan(hass, FAN_NAME, STATE_OFF),
    ])


class DemoFan(FanEntity):
    """A demonstration fan component."""

    def __init__(self, hass, name: str, initial_state: str) -> None:
        """Initialize the entity."""
        self.hass = hass
        self._speed = initial_state
        self.oscillating = False
        self.direction = "forward"
        self._name = name

    @property
    def name(self) -> str:
        """Get entity name."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed for a demo fan."""
        return False

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return self._speed

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [STATE_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    def turn_on(self, speed: str=None) -> None:
        """Turn on the entity."""
        if speed is None:
            speed = SPEED_MEDIUM
        self.set_speed(speed)

    def turn_off(self) -> None:
        """Turn off the entity."""
        self.oscillate(False)
        self.set_speed(STATE_OFF)

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        self._speed = speed
        self.schedule_update_ha_state()

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        self.direction = direction
        self.schedule_update_ha_state()

    def oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        self.oscillating = oscillating
        self.schedule_update_ha_state()

    @property
    def current_direction(self) -> str:
        """Fan direction."""
        return self.direction

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return DEMO_SUPPORT

"""
Support for switches which integrates with other components.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.template/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.switch import (
    ENTITY_ID_FORMAT, SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, CONF_VALUE_TEMPLATE, STATE_OFF, STATE_ON,
    ATTR_ENTITY_ID, CONF_SWITCHES, EVENT_HOMEASSISTANT_START)
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.restore_state import async_get_last_state
from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [STATE_ON, STATE_OFF, 'true', 'false']

ON_ACTION = 'turn_on'
OFF_ACTION = 'turn_off'

SWITCH_SCHEMA = vol.Schema({
    vol.Required(CONF_VALUE_TEMPLATE): cv.template,
    vol.Required(ON_ACTION): cv.SCRIPT_SCHEMA,
    vol.Required(OFF_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SWITCHES): vol.Schema({cv.slug: SWITCH_SCHEMA}),
})


@asyncio.coroutine
# pylint: disable=unused-argument
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Template switch."""
    switches = []

    for device, device_config in config[CONF_SWITCHES].items():
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        state_template = device_config[CONF_VALUE_TEMPLATE]
        on_action = device_config[ON_ACTION]
        off_action = device_config[OFF_ACTION]
        entity_ids = (device_config.get(ATTR_ENTITY_ID) or
                      state_template.extract_entities())

        state_template.hass = hass

        switches.append(
            SwitchTemplate(
                hass,
                device,
                friendly_name,
                state_template,
                on_action,
                off_action,
                entity_ids)
            )
    if not switches:
        _LOGGER.error("No switches added")
        return False

    async_add_devices(switches, True)
    return True


class SwitchTemplate(SwitchDevice):
    """Representation of a Template switch."""

    def __init__(self, hass, device_id, friendly_name, state_template,
                 on_action, off_action, entity_ids):
        """Initialize the Template switch."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, device_id,
                                                  hass=hass)
        self._name = friendly_name
        self._template = state_template
        self._on_script = Script(hass, on_action)
        self._off_script = Script(hass, off_action)
        self._state = False
        self._entities = entity_ids

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        state = yield from async_get_last_state(self.hass, self.entity_id)
        if state:
            self._state = state.state == STATE_ON

        @callback
        def template_switch_state_listener(entity, old_state, new_state):
            """Called when the target device changes state."""
            self.hass.async_add_job(self.async_update_ha_state(True))

        @callback
        def template_switch_startup(event):
            """Update template on startup."""
            async_track_state_change(
                self.hass, self._entities, template_switch_state_listener)

            self.hass.async_add_job(self.async_update_ha_state(True))

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_switch_startup)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def available(self):
        """If switch is available."""
        return self._state is not None

    def turn_on(self, **kwargs):
        """Fire the on action."""
        self._on_script.run()

    def turn_off(self, **kwargs):
        """Fire the off action."""
        self._off_script.run()

    @asyncio.coroutine
    def async_update(self):
        """Update the state from the template."""
        try:
            state = self._template.async_render().lower()

            if state in _VALID_STATES:
                self._state = state in ('true', STATE_ON)
            else:
                _LOGGER.error(
                    'Received invalid switch is_on state: %s. Expected: %s',
                    state, ', '.join(_VALID_STATES))
                self._state = None

        except TemplateError as ex:
            _LOGGER.error(ex)
            self._state = None
