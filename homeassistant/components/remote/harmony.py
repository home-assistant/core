"""
Support for Harmony activities represented as a switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/harmony/
"""

#will change once testing is over
#from homeassistant.const import ATTR_DEVICE, ATTR_COMMAND, ATTR_ACTIVITY
import homeassistant.components.remote as remote
import homeassistant.components.harmony as harmony
import pyharmony
import logging


DEPENDENCIES = ['harmony']
_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE = 'device'
ATTR_COMMAND = 'command'
ATTR_ACTIVITY = 'activity'

def setup_platform(hass, config, add_devices_callback, configData, discovery_info=None):
    for hub in harmony.HARMONY:
        add_devices_callback([HarmonyRemote(harmony.HARMONY[hub]['device'])])
    return True


class HarmonyRemote(remote.RemoteDevice):
    """Remote representation used expose services to control a Harmony device"""

    def __init__(self, harmony_device):
        self._harmony_device = harmony_device
        self._name = 'harmony_' + self._harmony_device.name


    @property
    def name(self):
        """Return the Harmony device's name"""
        return self._harmony_device._name


    @property
    def state(self):
        """Return the state of the Harmony device."""
        return self.get_status()


    @property
    def state_attributes(self):
        """Overwrite inherited attributes"""
        return {}


    def get_status(self):
        """Return current activity"""
        return str(self._harmony_device.state)


    def turn_on(self, **kwargs):
        """Start an activity from the Harmony device"""
        pyharmony.ha_start_activity(self._harmony_device._email,
                                    self._harmony_device._password,
                                    self._harmony_device._ip,
                                    self._harmony_device._port,
                                    kwargs[ATTR_ACTIVITY])


    def turn_off(self):
        """Start the PowerOff activity"""
        pyharmony.ha_power_off(self._harmony_device._email,
                               self._harmony_device._password,
                               self._harmony_device._ip,
                               self._harmony_device._port)


    def send_command(self, **kwargs):
        """Send a command to one device"""
        pyharmony.ha_send_command(self._harmony_device._email,
                                  self._harmony_device._password,
                                  self._harmony_device._ip,
                                  self._harmony_device._port,
                                  kwargs[ATTR_DEVICE],
                                  kwargs[ATTR_COMMAND])


    def sync(self):
        """Sync the Harmony device with the web service"""
        pyharmony.ha_sync(self._harmony_device._email,
                               self._harmony_device._password,
                               self._harmony_device._ip,
                               self._harmony_device._port)