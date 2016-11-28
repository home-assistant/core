"""
Demo platform that has two fake remotes.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.remote import RemoteDevice
from homeassistant.const import DEVICE_DEFAULT_NAME


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the demo remotes."""
    add_devices_callback([
        DemoRemote('Remote One', False, None, False),
        DemoRemote('Remote Two', True, 'mdi:remote', False),
    ])


class DemoRemote(RemoteDevice):
    """Representation of a demo switch."""

    def __init__(self, name, state, icon, assumed):
        """Initialize the Demo Remote."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = state
        self._icon = icon
        self._assumed = assumed

    @property
    def should_poll(self):
        """No polling needed for a demo remote."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def assumed_state(self):
        """Return if the state is based on assumptions."""
        return self._assumed

    @property
    def is_on(self):
        """Return true if remote is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the remote on."""
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the remote off."""
        self._state = False
        self.schedule_update_ha_state()
