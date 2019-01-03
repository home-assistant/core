"""
Support for Verisure Smartplugs.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.verisure/
"""
import logging
from time import time

from homeassistant.components.verisure import HUB as hub
from homeassistant.components.verisure import CONF_SMARTPLUGS
from homeassistant.components.switch import SwitchDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Verisure switch platform."""
    if not int(hub.config.get(CONF_SMARTPLUGS, 1)):
        return False

    hub.update_overview()
    switches = []
    switches.extend([
        VerisureSmartplug(device_label)
        for device_label in hub.get('$.smartPlugs[*].deviceLabel')])
    add_entities(switches)


class VerisureSmartplug(SwitchDevice):
    """Representation of a Verisure smartplug."""

    def __init__(self, device_id):
        """Initialize the Verisure device."""
        self._device_label = device_id
        self._change_timestamp = 0
        self._state = False

    @property
    def name(self):
        """Return the name or location of the smartplug."""
        return hub.get_first(
            "$.smartPlugs[?(@.deviceLabel == '%s')].area",
            self._device_label)

    @property
    def is_on(self):
        """Return true if on."""
        if time() - self._change_timestamp < 10:
            return self._state
        self._state = hub.get_first(
            "$.smartPlugs[?(@.deviceLabel == '%s')].currentState",
            self._device_label) == "ON"
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return hub.get_first(
            "$.smartPlugs[?(@.deviceLabel == '%s')]",
            self._device_label) is not None

    def turn_on(self, **kwargs):
        """Set smartplug status on."""
        hub.session.set_smartplug_state(self._device_label, True)
        self._state = True
        self._change_timestamp = time()

    def turn_off(self, **kwargs):
        """Set smartplug status off."""
        hub.session.set_smartplug_state(self._device_label, False)
        self._state = False
        self._change_timestamp = time()

    # pylint: disable=no-self-use
    def update(self):
        """Get the latest date of the smartplug."""
        hub.update_overview()
