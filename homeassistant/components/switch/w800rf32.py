"""
Support for X10 rf switches and keypads via the W800RF32 receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.w800rf32/

"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA, SwitchDevice)
from homeassistant.components.w800rf32 import (W800RF32_DEVICE, CONF_FIRE_EVENT)
from homeassistant.const import (ATTR_NAME, CONF_DEVICES, CONF_NAME)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (async_dispatcher_connect)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['w800rf32']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {
        cv.string: vol.Schema({
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean
        })
    },
}, extra=vol.ALLOW_EXTRA)


async def async_setup_platform(hass, config,
                               add_entities, discovery_info=None):
    """Set up the Switch platform to w800rf32."""
    switches = []

    # device_id --> "c1 or a3" X10 device. entity (type dictionary) -->
    # name, device_class etc
    for device_id, entity in config[CONF_DEVICES].items():

        _LOGGER.debug("Add %s w800rf32.switch",
                      entity[ATTR_NAME])

        # event = None  # None until an event happens
        device = W800rf32Switch(
            hass, device_id, entity.get(CONF_NAME), entity[CONF_FIRE_EVENT],)

        switches.append(device)

    add_entities(switches)


class W800rf32Switch(SwitchDevice):
    """A representation of a w800rf32 switch."""

    def __init__(self, hass, device_id, name, should_fire=False,):
        """Initialize the w800rf32 switch."""
        self._hass = hass
        self._device_id = device_id.lower()
        self._signal = W800RF32_DEVICE.format(self._device_id)
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

    def switch_update(self, event):
        """Call for control updates from the w800rf32 gateway."""
        import W800rf32 as w800rf32mod
        if not isinstance(event, w800rf32mod.W800rf32Event):
            return

        dev_id = event.device.lower()
        command = event.command

        _LOGGER.debug(
            "Switch update (Device ID: %s Command %s ...)",
            dev_id, command)

        # Update the w800rf32 device state
        if command in ('On', 'Off'):
            is_on = command == 'On'
            self.update_state(is_on)

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

    async def async_added_to_hass(self):
        """Register update callback."""
        async_dispatcher_connect(self._hass, self._signal,
                                 self.switch_update)
