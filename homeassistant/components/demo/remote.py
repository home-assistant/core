"""Demo platform that has two fake remotes."""
from homeassistant.components.remote import RemoteDevice
from homeassistant.const import DEVICE_DEFAULT_NAME


def setup_platform(hass, config, add_entities_callback, discovery_info=None):
    """Set up the demo remotes."""
    add_entities_callback([
        DemoRemote('Remote One', False, None),
        DemoRemote('Remote Two', True, 'mdi:remote'),
    ])


class DemoRemote(RemoteDevice):
    """Representation of a demo remote."""

    def __init__(self, name, state, icon):
        """Initialize the Demo Remote."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = state
        self._icon = icon
        self._last_command_sent = None

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
    def is_on(self):
        """Return true if remote is on."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return device state attributes."""
        if self._last_command_sent is not None:
            return {'last_command_sent': self._last_command_sent}

    def turn_on(self, **kwargs):
        """Turn the remote on."""
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the remote off."""
        self._state = False
        self.schedule_update_ha_state()

    def send_command(self, command, **kwargs):
        """Send a command to a device."""
        for com in command:
            self._last_command_sent = com
        self.schedule_update_ha_state()
