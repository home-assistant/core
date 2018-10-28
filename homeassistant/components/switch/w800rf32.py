"""
Support for X10 rf switches and keypads via the W800RF32 receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.w800rf32/

```yaml
# Example configuration.yaml entry

switch:
  - platform: w800rf32
    devices:
      c1:
        name: keypad_1_1
      c2:
        name: keypad_1_2

```
"""
import logging

import voluptuous as vol


from homeassistant.components import w800rf32
from homeassistant.components.switch import (
    PLATFORM_SCHEMA, SwitchDevice)
from homeassistant.components.w800rf32 import (CONF_FIRE_EVENT)
from homeassistant.const import (ATTR_NAME, CONF_DEVICES, CONF_NAME)
from homeassistant.helpers import config_validation as cv


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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Switch platform to w800rf32."""
    import W800rf32 as w800rf32mod
    switches = []

    # device_id --> "c1 or a3" X10 device. entity (type dictionary) --> name, device_class etc
    for device_id, entity in config[CONF_DEVICES].items():

        if device_id in w800rf32.W800_DEVICES:
            continue

        _LOGGER.debug("Add %s w800rf32.switch",
                      entity[ATTR_NAME])

        event = None  # None until an event happens
        device = W800rf32Switch(event, entity.get(CONF_NAME), entity[CONF_FIRE_EVENT],)

        switches.append(device)
        w800rf32.W800_DEVICES[device_id] = device

    add_entities(switches)

    def switch_update(event):
        """Call for control updates from the w800rf32 gateway."""
        switch = None

        if not isinstance(event, w800rf32mod.W800rf32Event):
            return

        # make sure it's lowercase
        device_id = event.device.lower()

        # get the name, ex: motion_hall
        if device_id in w800rf32.W800_DEVICES:
            switch = w800rf32.W800_DEVICES[device_id]

        if switch is None:
            return

        if not isinstance(switch, W800rf32Switch):
            return
        else:
            _LOGGER.debug(
                "Binary sensor update (Device ID: %s Class: %s)",
                event.device,
                event.device.__class__.__name__)

        w800rf32.apply_received_command(event)

    # Subscribe to main w800rf32 events
    if switch_update not in w800rf32.RECEIVED_EVT_SUBSCRIBERS:
        w800rf32.RECEIVED_EVT_SUBSCRIBERS.append(switch_update)


class W800rf32Switch(SwitchDevice):
    """A representation of a w800rf32 switch."""

    def __init__(self, event, name, should_fire=False,):
        """Initialize the w800rf32 switch."""
        self.event = event
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
        """Return is the device must fire event."""
        return self._should_fire_event

    def turn_on(self, **kwargs):
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        self._state = False
        self.schedule_update_ha_state()

    def update_state(self, state):
        """Update the state of the device."""
        self._state = state
        self.schedule_update_ha_state()
