"""
Support for Verisure Smartplugs.

For more details about this platform, please refer to the documentation at
documentation at https://home-assistant.io/components/verisure/
"""
import logging

from homeassistant.components.verisure import HUB as hub
from homeassistant.components.switch import SwitchDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Verisure platform."""
    if not int(hub.config.get('smartplugs', '1')):
        return False

    hub.update_smartplugs()
    switches = []
    switches.extend([
        VerisureSmartplug(value.deviceLabel)
        for value in hub.smartplug_status.values()])
    add_devices(switches)


class VerisureSmartplug(SwitchDevice):
    """Representation of a Verisure smartplug."""

    def __init__(self, device_id):
        """Initialize the Verisure device."""
        self._id = device_id

    @property
    def name(self):
        """Return the name or location of the smartplug."""
        return hub.smartplug_status[self._id].location

    @property
    def is_on(self):
        """Return true if on."""
        return hub.smartplug_status[self._id].status == 'on'

    @property
    def available(self):
        """Return True if entity is available."""
        return hub.available

    def turn_on(self):
        """Set smartplug status on."""
        hub.my_pages.smartplug.set(self._id, 'on')
        hub.my_pages.smartplug.wait_while_updating(self._id, 'on')
        self.update()

    def turn_off(self):
        """Set smartplug status off."""
        hub.my_pages.smartplug.set(self._id, 'off')
        hub.my_pages.smartplug.wait_while_updating(self._id, 'off')
        self.update()

    def update(self):
        """Get the latest date of the smartplug."""
        hub.update_smartplugs()
