"""
Support for Xiaomi Aqara Lock.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.xiaomi_aqara/
"""
import logging
from homeassistant.components.xiaomi_aqara import (PY_XIAOMI_GATEWAY,
                                                   XiaomiDevice)
from homeassistant.components.lock import LockDevice

_LOGGER = logging.getLogger(__name__)

FINGER_KEY = 'fing_verified'
PASSWORD_KEY = 'psw_verified'
CARD_KEY = 'card_verified'
VERIFIED_WRONG_KEY = 'verified_wrong'

ATTR_VERIFIED_WRONG_TIMES = 'verified_wrong_times'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Perform the setup for Xiaomi devices."""
    devices = []

    for gateway in hass.data[PY_XIAOMI_GATEWAY].gateways.values():
        for device in gateway.devices['lock']:
            model = device['model']
            if model == 'lock.aq1':
                devices.append(XiaomiAqaraLock(device, 'Lock', gateway))
    add_devices(devices)


class XiaomiAqaraLock(LockDevice, XiaomiDevice):
    """Representation of a XiaomiAqaraLock."""

    def __init__(self, device, name, xiaomi_hub):
        """Initialize the XiaomiAqaraLock."""
        self._changed_by = 0
        self._verified_wrong_times = 0

        super().__init__(device, name, xiaomi_hub)

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return True

    @property
    def changed_by(self) -> int:
        """Last change triggered by."""
        return self._changed_by

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        attributes = {
            ATTR_VERIFIED_WRONG_TIMES: self._verified_wrong_times,
        }
        return attributes

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        value = data.get(VERIFIED_WRONG_KEY)
        if value is not None:
            self._verified_wrong_times = int(value)
            return True

        for key in (FINGER_KEY, PASSWORD_KEY, CARD_KEY):
            value = data.get(key)
            if value is not None:
                self._changed_by = int(value)
                self._verified_wrong_times = 0
                return True

        return False
