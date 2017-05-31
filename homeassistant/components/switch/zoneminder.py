"""
Support for ZoneMinder switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.zoneminder/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_COMMAND_ON, CONF_COMMAND_OFF)
import homeassistant.components.zoneminder as zoneminder
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zoneminder']

DEFAULT_CAUSE = "Home Assistant Triggered Event"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COMMAND_ON): cv.string,
    vol.Required(CONF_COMMAND_OFF): cv.string,
    vol.Optional('ext_trigger_time', default=60): cv.time,
    vol.Optional('ext_trigger_enable', default=False): cv.boolean,
    vol.Optional('ext_trigger_cause', default=DEFAULT_CAUSE): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the ZoneMinder switch platform."""
    on_state = config.get(CONF_COMMAND_ON)
    off_state = config.get(CONF_COMMAND_OFF)

    switches = []

    monitors = zoneminder.get_state('api/monitors.json')
    for i in monitors['monitors']:
        switches.append(
            ZMSwitchMonitors(
                int(i['Monitor']['Id']),
                i['Monitor']['Name'],
                on_state,
                off_state
            )
        )
        if config.get('ext_trigger_enable'):
            switches.append(
                ZMTriggerMonitors(
                    int(i['Monitor']['Id']),
                    i['Monitor']['Name'],
                    config.get('ext_trigger_cause'),
                    config.get('ext_trigger_time')
                )
            )

    add_devices(switches)


class ZMSwitchMonitors(SwitchDevice):
    """Representation of a ZoneMinder switch."""

    icon = 'mdi:record-rec'

    def __init__(self, monitor_id, monitor_name, on_state, off_state):
        """Initialize the switch."""
        self._monitor_id = monitor_id
        self._monitor_name = monitor_name
        self._on_state = on_state
        self._off_state = off_state
        self._state = None

    @property
    def name(self):
        """Return the name of the switch."""
        return "%s State" % self._monitor_name

    def update(self):
        """Update the switch value."""
        monitor = zoneminder.get_state(
            'api/monitors/%i.json' % self._monitor_id
        )
        current_state = monitor['monitor']['Monitor']['Function']
        self._state = True if current_state == self._on_state else False

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._state

    def turn_on(self):
        """Turn the entity on."""
        zoneminder.change_state(
            'api/monitors/%i.json' % self._monitor_id,
            {'Monitor[Function]': self._on_state}
        )

    def turn_off(self):
        """Turn the entity off."""
        zoneminder.change_state(
            'api/monitors/%i.json' % self._monitor_id,
            {'Monitor[Function]': self._off_state}
        )


class ZMTriggerMonitors(SwitchDevice):
    """Representation of External Trigger."""

    def __init__(self, monitor_id, monitor_name, cause, timeout):
        """Initialize the switch."""
        self._monitor_id = monitor_id
        self._monitor_name = monitor_name
        self._ison = None
        self._cause = cause
        self._timeout = timeout

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._ison

    def turn_on(self):
        """Turn the entity on."""
        zoneminder.zm_trigger(
            self._monitor_id, "on", self._cause, self._timeout)
        self._ison = True

    def turn_off(self):
        """Turn the entity off."""
        zoneminder.zm_trigger(
            self._monitor_id, "off", self._cause, self._timeout)
        self._ison = False

    @property
    def name(self):
        """Return the name of the switch."""
        return "%s Trigger" % self._monitor_name
