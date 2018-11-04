"""
Support for X10 rf switches and keypads via the W800RF32 receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.w800rf32/

"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA, SwitchDevice)
from homeassistant.components.w800rf32 import (DOMAIN, CONF_FIRE_EVENT)
from homeassistant.const import (ATTR_NAME, CONF_DEVICES, CONF_NAME)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (dispatcher_connect)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['w800rf32']
DEVICE_TYPE = 'W800rf32Switch'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {
        cv.string: vol.Schema({
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean
        })
    },
}, extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Switch platform to w800rf32."""
    import W800rf32 as w800rf32mod
    switches = []

    # device_id --> "c1 or a3" X10 device. entity (type dictionary) -->
    # name, device_class etc
    for device_id, entity in config[CONF_DEVICES].items():

        if device_id in hass.data[DOMAIN]['entities']:
            continue

        _LOGGER.debug("Add %s w800rf32.switch",
                      entity[ATTR_NAME])

        # event = None  # None until an event happens
        device = W800rf32Switch(
            device_id, entity.get(CONF_NAME), entity[CONF_FIRE_EVENT],)
        # Hold device_id
        hass.data[DOMAIN]['entities'][device_id] = device

        switches.append(device)

    add_entities(switches)

    def switch_update(event):
        """Call for control updates from the w800rf32 gateway."""
        switch = None

        if not isinstance(event, w800rf32mod.W800rf32Event):
            return

        dev_id = event.device.lower()
        command = event.command

        if dev_id in hass.data[DOMAIN]['entities']:
            switch = hass.data[DOMAIN]['entities'][dev_id]

        if switch is None:
            return

        if not isinstance(switch, W800rf32Switch):
            return

        _LOGGER.debug(
            "Switch update (Device ID: %s Command %s ...)",
            dev_id, command)

        # Update the w800rf32 device state
        if command in ('On', 'Off'):
            is_on = command == 'On'
            switch.update_state(is_on)

    # Subscribe to main w800rf32 events
    dispatcher_connect(hass, DEVICE_TYPE, switch_update)


class W800rf32Switch(SwitchDevice):
    """A representation of a w800rf32 switch."""

    def __init__(self, device_id, name, should_fire=False,):
        """Initialize the w800rf32 switch."""
        # self._event = event
        self._device_id = device_id
        self._name = name
        self._should_fire_event = should_fire
        self._state = False

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if the sensor state is True."""
        return self._state

    @property
    def should_fire_event(self):
        """Return if the device must fire event."""
        return self._should_fire_event

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._state = False
        self.schedule_update_ha_state()

    def update_state(self, state):
        """Update the state of the device."""
        self._state = state
        self.schedule_update_ha_state()
