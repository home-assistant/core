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
ATTR_LOCK_STATUS = 'lock_status'
LOCK_NOTIFICATION = {
    1: 'Manual Lock',
    2: 'Manual Unlock',
    3: 'RF Lock',
    4: 'RF Unlock',
    5: 'Keypad Lock',
    6: 'Keypad Unlock',
    11: 'Lock Jammed',
    254: 'Unknown Event'
}

LOCK_ALARM_TYPE = {
    9: 'Deadbolt Jammed',
    18: 'Locked with Keypad by user',
    19: 'Unlocked with Keypad by user ',
    21: 'Manually Locked by',
    22: 'Manually Unlocked by Key or Inside thumb turn',
    24: 'Locked by RF',
    25: 'Unlocked by RF',
    27: 'Auto re-lock',
    33: 'User deleted: ',
    112: 'Master code changed or User added: ',
    113: 'Duplicate Pin-code: ',
    130: 'RF module, power restored',
    161: 'Tamper Alarm: ',
    167: 'Low Battery',
    168: 'Critical Battery Level',
    169: 'Battery too low to operate'
}

MANUAL_LOCK_ALARM_LEVEL = {
    1: 'Key Cylinder or Inside thumb turn',
    2: 'Touch function (lock and leave)'
}

TAMPER_ALARM_LEVEL = {
    1: 'Too many keypresses',
    2: 'Cover removed'
}

LOCK_STATUS = {
    1: True,
    2: False,
    3: True,
    4: False,
    5: True,
    6: False,
    9: False,
    18: True,
    19: False,
    21: True,
    22: False,
    24: True,
    25: False,
    27: True
}

ALARM_TYPE_STD = [
    18,
    19,
    33,
    112,
    113
]


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
        self._lock_status = None
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
                _LOGGER.debug('Lock state set from Access Control value and'
                              ' is %s', value.data)
            break

        for value in self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_ALARM).values():
            if value.label != "Alarm Type":
                continue
            alarm_type = LOCK_ALARM_TYPE.get(value.data)
            if alarm_type:
                self._state = LOCK_STATUS.get(value.data)
                _LOGGER.debug('Lock state set from Alarm Type value and'
                              ' is %s', value.data)
            break

        for value in self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_ALARM).values():
            if value.label != "Alarm Level":
                continue
            alarm_level = value.data
            _LOGGER.debug('Lock alarm_level is %s', alarm_level)
            if alarm_type is 21:
                self._lock_status = '{}{}'.format(
                    LOCK_ALARM_TYPE.get(alarm_type),
                    MANUAL_LOCK_ALARM_LEVEL.get(alarm_level))
            if alarm_type in ALARM_TYPE_STD:
                self._lock_status = '{}{}'.format(
                    LOCK_ALARM_TYPE.get(alarm_type), alarm_level)
                break
            if alarm_type is 161:
                self._lock_status = '{}{}'.format(
                    LOCK_ALARM_TYPE.get(alarm_type),
                    TAMPER_ALARM_LEVEL.get(alarm_level))
                break
            if alarm_type != 0:
                self._lock_status = LOCK_ALARM_TYPE.get(alarm_type)
                break

        if self._notification or self._lock_status:
            for value in self._node.get_values(
                    class_id=zwave.const.COMMAND_CLASS_DOOR_LOCK).values():
                if value.type == zwave.const.TYPE_BOOL:
                    if value.genre != zwave.const.GENRE_USER:
                        self._state = value.data
                        _LOGGER.debug('Lock state set from Bool value and'
                                      ' is %s', value.data)
                        break

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
        if self._lock_status:
            data[ATTR_LOCK_STATUS] = self._lock_status
        return data
