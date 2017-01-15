"""
Zwave platform that handles simple door locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
import logging

from homeassistant.components.lock import DOMAIN, LockDevice
from homeassistant.components import zwave

_LOGGER = logging.getLogger(__name__)

ATTR_NOTIFICATION = 'notification'

LOCK_NOTIFICATION = {
    1: 'Manual Lock',
    2: 'Manual Unlock',
    3: 'RF Lock',
    4: 'RF Unlock',
    5: 'Keypad Lock',
    6: 'Keypad Unlock',
    254: 'Unknown Event'
}

LOCK_STATUS = {
    1: True,
    2: False,
    3: True,
    4: False,
    5: True,
    6: False
}


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return Z-Wave switches."""
    if discovery_info is None or zwave.NETWORK is None:
        return

    node = zwave.NETWORK.nodes[discovery_info[zwave.const.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.const.ATTR_VALUE_ID]]

    if value.command_class != zwave.const.COMMAND_CLASS_DOOR_LOCK:
        return
    if value.type != zwave.const.TYPE_BOOL:
        return
    if value.genre != zwave.const.GENRE_USER:
        return

    value.set_change_verified(False)
    add_devices([ZwaveLock(value)])


class ZwaveLock(zwave.ZWaveDeviceEntity, LockDevice):
    """Representation of a Z-Wave switch."""

    def __init__(self, value):
        """Initialize the Z-Wave switch device."""
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher

        zwave.ZWaveDeviceEntity.__init__(self, value, DOMAIN)

        self._node = value.node
        self._state = None
        self._notification = None
        dispatcher.connect(
            self._value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)
        self.update_properties()

    def _value_changed(self, value):
        """Called when a value has changed on the network."""
        if self._value.value_id == value.value_id or \
           self._value.node == value.node:
            _LOGGER.debug('Value changed for label %s', self._value.label)
            self.update_properties()
            self.schedule_update_ha_state()

    def update_properties(self):
        """Callback on data change for the registered node/value pair."""
        for value in self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_ALARM).values():
            if value.label != "Access Control":
                continue
            self._notification = LOCK_NOTIFICATION.get(value.data)
            if self._notification:
                self._state = LOCK_STATUS.get(value.data)
            break
        if not self._notification:
            self._state = self._value.data

    @property
    def is_locked(self):
        """Return true if device is locked."""
        return self._state

    def lock(self, **kwargs):
        """Lock the device."""
        self._value.data = True

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._value.data = False

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        data = super().device_state_attributes
        if self._notification:
            data[ATTR_NOTIFICATION] = self._notification
        return data
