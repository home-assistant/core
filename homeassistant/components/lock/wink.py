"""
Support for Wink locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.wink/
"""
import logging

from homeassistant.components.lock import LockDevice
from homeassistant.const import CONF_ACCESS_TOKEN

REQUIREMENTS = ['python-wink==0.6.2']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wink platform."""
    import pywink

    if discovery_info is None:
        token = config.get(CONF_ACCESS_TOKEN)

        if token is None:
            logging.getLogger(__name__).error(
                "Missing wink access_token. "
                "Get one at https://winkbearertoken.appspot.com/")
            return

        pywink.set_bearer_token(token)

    add_devices(WinkLockDevice(lock) for lock in pywink.get_locks())


class WinkLockDevice(LockDevice):
    """Representation of a Wink lock."""

    def __init__(self, wink):
        """Initialize the lock."""
        self.wink = wink

    @property
    def unique_id(self):
        """Return the id of this wink lock."""
        return "{}.{}".format(self.__class__, self.wink.device_id())

    @property
    def name(self):
        """Return the name of the lock if any."""
        return self.wink.name()

    def update(self):
        """Update the state of the lock."""
        self.wink.update_state()

    @property
    def is_locked(self):
        """Return true if device is locked."""
        return self.wink.state()

    def lock(self, **kwargs):
        """Lock the device."""
        self.wink.set_state(True)

    def unlock(self, **kwargs):
        """Unlock the device."""
        self.wink.set_state(False)
