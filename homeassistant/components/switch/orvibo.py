"""
Support for Orvibo S20 Wifi Smart Switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.orvibo/
"""
import logging

from homeassistant.components.switch import SwitchDevice

DEFAULT_NAME = "Orvibo S20 Switch"
REQUIREMENTS = ['orvibo==1.1.1']
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Find and return S20 switches."""
    from orvibo.s20 import S20, S20Exception

    switches = []
    switch_conf = config.get('switches', [config])

    for switch in switch_conf:
        if switch.get('host') is None:
            _LOGGER.error("Missing required variable: host")
            continue
        host = switch.get('host')
        mac = switch.get('mac')
        try:
            switches.append(S20Switch(switch.get('name', DEFAULT_NAME),
                                      S20(host, mac=mac)))
            _LOGGER.info("Initialized S20 at %s", host)
        except S20Exception:
            _LOGGER.exception("S20 at %s couldn't be initialized",
                              host)

    add_devices_callback(switches)


class S20Switch(SwitchDevice):
    """Representsation of an S20 switch."""

    def __init__(self, name, s20):
        """Initialize the S20 device."""
        from orvibo.s20 import S20Exception

        self._name = name
        self._s20 = s20
        self._state = False
        self._exc = S20Exception

    @property
    def should_poll(self):
        """Polling is needed."""
        return True

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Update device state."""
        try:
            self._state = self._s20.on
        except self._exc:
            _LOGGER.exception("Error while fetching S20 state")

    def turn_on(self, **kwargs):
        """Turn the device on."""
        try:
            self._s20.on = True
        except self._exc:
            _LOGGER.exception("Error while turning on S20")

    def turn_off(self, **kwargs):
        """Turn the device off."""
        try:
            self._s20.on = False
        except self._exc:
            _LOGGER.exception("Error while turning off S20")
