"""
Z-Wave platform that handles simple door locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.zwave/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.lock import DOMAIN, LockDevice
from homeassistant.components import zwave
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_NOTIFICATION = 'notification'
ATTR_LOCK_STATUS = 'lock_status'
ATTR_CODE_SLOT = 'code_slot'
ATTR_USERCODE = 'usercode'
CONFIG_ADVANCED = 'Advanced'

SERVICE_SET_USERCODE = 'set_usercode'
SERVICE_GET_USERCODE = 'get_usercode'
SERVICE_CLEAR_USERCODE = 'clear_usercode'

POLYCONTROL = 0x10E
DANALOCK_V2_BTZE = 0x2
POLYCONTROL_DANALOCK_V2_BTZE_LOCK = (POLYCONTROL, DANALOCK_V2_BTZE)
WORKAROUND_V2BTZE = 'v2btze'

DEVICE_MAPPINGS = {
    POLYCONTROL_DANALOCK_V2_BTZE_LOCK: WORKAROUND_V2BTZE
}

LOCK_NOTIFICATION = {
    '1': 'Manual Lock',
    '2': 'Manual Unlock',
    '3': 'RF Lock',
    '4': 'RF Unlock',
    '5': 'Keypad Lock',
    '6': 'Keypad Unlock',
    '11': 'Lock Jammed',
    '254': 'Unknown Event'
}

LOCK_ALARM_TYPE = {
    '9': 'Deadbolt Jammed',
    '16': 'Unlocked by Bluetooth ',
    '18': 'Locked with Keypad by user ',
    '19': 'Unlocked with Keypad by user ',
    '21': 'Manually Locked ',
    '22': 'Manually Unlocked ',
    '24': 'Locked by RF',
    '25': 'Unlocked by RF',
    '27': 'Auto re-lock',
    '33': 'User deleted: ',
    '112': 'Master code changed or User added: ',
    '113': 'Duplicate Pin-code: ',
    '130': 'RF module, power restored',
    '144': 'Unlocked by NFC Tag or Card by user ',
    '161': 'Tamper Alarm: ',
    '167': 'Low Battery',
    '168': 'Critical Battery Level',
    '169': 'Battery too low to operate'
}

MANUAL_LOCK_ALARM_LEVEL = {
    '1': 'by Key Cylinder or Inside thumb turn',
    '2': 'by Touch function (lock and leave)'
}

TAMPER_ALARM_LEVEL = {
    '1': 'Too many keypresses',
    '2': 'Cover removed'
}

LOCK_STATUS = {
    '1': True,
    '2': False,
    '3': True,
    '4': False,
    '5': True,
    '6': False,
    '9': False,
    '18': True,
    '19': False,
    '21': True,
    '22': False,
    '24': True,
    '25': False,
    '27': True
}

ALARM_TYPE_STD = [
    '18',
    '19',
    '33',
    '112',
    '113',
    '144'
]

SET_USERCODE_SCHEMA = vol.Schema({
    vol.Required(zwave.const.ATTR_NODE_ID): vol.Coerce(int),
    vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
    vol.Required(ATTR_USERCODE): cv.string,
})

GET_USERCODE_SCHEMA = vol.Schema({
    vol.Required(zwave.const.ATTR_NODE_ID): vol.Coerce(int),
    vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
})

CLEAR_USERCODE_SCHEMA = vol.Schema({
    vol.Required(zwave.const.ATTR_NODE_ID): vol.Coerce(int),
    vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Set up the Z-Wave Lock platform."""
    yield from zwave.async_setup_platform(
        hass, config, async_add_entities, discovery_info)

    network = hass.data[zwave.const.DATA_NETWORK]

    def set_usercode(service):
        """Set the usercode to index X on the lock."""
        node_id = service.data.get(zwave.const.ATTR_NODE_ID)
        lock_node = network.nodes[node_id]
        code_slot = service.data.get(ATTR_CODE_SLOT)
        usercode = service.data.get(ATTR_USERCODE)

        for value in lock_node.get_values(
                class_id=zwave.const.COMMAND_CLASS_USER_CODE).values():
            if value.index != code_slot:
                continue
            if len(str(usercode)) < 4:
                _LOGGER.error("Invalid code provided: (%s) "
                              "usercode must be atleast 4 and at most"
                              " %s digits",
                              usercode, len(value.data))
                break
            value.data = str(usercode)
            break

    def get_usercode(service):
        """Get a usercode at index X on the lock."""
        node_id = service.data.get(zwave.const.ATTR_NODE_ID)
        lock_node = network.nodes[node_id]
        code_slot = service.data.get(ATTR_CODE_SLOT)

        for value in lock_node.get_values(
                class_id=zwave.const.COMMAND_CLASS_USER_CODE).values():
            if value.index != code_slot:
                continue
            _LOGGER.info("Usercode at slot %s is: %s", value.index, value.data)
            break

    def clear_usercode(service):
        """Set usercode to slot X on the lock."""
        node_id = service.data.get(zwave.const.ATTR_NODE_ID)
        lock_node = network.nodes[node_id]
        code_slot = service.data.get(ATTR_CODE_SLOT)
        data = ''

        for value in lock_node.get_values(
                class_id=zwave.const.COMMAND_CLASS_USER_CODE).values():
            if value.index != code_slot:
                continue
            for i in range(len(value.data)):
                data += '\0'
                i += 1
            _LOGGER.debug('Data to clear lock: %s', data)
            value.data = data
            _LOGGER.info("Usercode at slot %s is cleared", value.index)
            break

    hass.services.async_register(
        DOMAIN, SERVICE_SET_USERCODE, set_usercode,
        schema=SET_USERCODE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_GET_USERCODE, get_usercode,
        schema=GET_USERCODE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_USERCODE, clear_usercode,
        schema=CLEAR_USERCODE_SCHEMA)


def get_device(node, values, **kwargs):
    """Create Z-Wave entity device."""
    return ZwaveLock(values)


class ZwaveLock(zwave.ZWaveDeviceEntity, LockDevice):
    """Representation of a Z-Wave Lock."""

    def __init__(self, values):
        """Initialize the Z-Wave lock device."""
        zwave.ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self._state = None
        self._notification = None
        self._lock_status = None
        self._v2btze = None

        # Enable appropriate workaround flags for our device
        # Make sure that we have values for the key before converting to int
        if (self.node.manufacturer_id.strip() and
                self.node.product_id.strip()):
            specific_sensor_key = (int(self.node.manufacturer_id, 16),
                                   int(self.node.product_id, 16))
            if specific_sensor_key in DEVICE_MAPPINGS:
                if DEVICE_MAPPINGS[specific_sensor_key] == WORKAROUND_V2BTZE:
                    self._v2btze = 1
                    _LOGGER.debug("Polycontrol Danalock v2 BTZE "
                                  "workaround enabled")
        self.update_properties()

    def update_properties(self):
        """Handle data changes for node values."""
        self._state = self.values.primary.data
        _LOGGER.debug("Lock state set from Bool value and is %s", self._state)
        if self.values.access_control:
            notification_data = self.values.access_control.data
            self._notification = LOCK_NOTIFICATION.get(str(notification_data))

            if self._v2btze:
                if self.values.v2btze_advanced and \
                        self.values.v2btze_advanced.data == CONFIG_ADVANCED:
                    self._state = LOCK_STATUS.get(str(notification_data))
                    _LOGGER.debug(
                        "Lock state set from Access Control value and is %s, "
                        "get=%s", str(notification_data), self.state)

        if not self.values.alarm_type:
            return

        alarm_type = self.values.alarm_type.data
        _LOGGER.debug("Lock alarm_type is %s", str(alarm_type))
        if self.values.alarm_level:
            alarm_level = self.values.alarm_level.data
        else:
            alarm_level = None
        _LOGGER.debug("Lock alarm_level is %s", str(alarm_level))

        if not alarm_type:
            return
        if alarm_type == 21:
            self._lock_status = '{}{}'.format(
                LOCK_ALARM_TYPE.get(str(alarm_type)),
                MANUAL_LOCK_ALARM_LEVEL.get(str(alarm_level)))
            return
        if str(alarm_type) in ALARM_TYPE_STD:
            self._lock_status = '{}{}'.format(
                LOCK_ALARM_TYPE.get(str(alarm_type)), str(alarm_level))
            return
        if alarm_type == 161:
            self._lock_status = '{}{}'.format(
                LOCK_ALARM_TYPE.get(str(alarm_type)),
                TAMPER_ALARM_LEVEL.get(str(alarm_level)))
            return
        if alarm_type != 0:
            self._lock_status = LOCK_ALARM_TYPE.get(str(alarm_type))
            return

    @property
    def is_locked(self):
        """Return true if device is locked."""
        return self._state

    def lock(self, **kwargs):
        """Lock the device."""
        self.values.primary.data = True

    def unlock(self, **kwargs):
        """Unlock the device."""
        self.values.primary.data = False

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        data = super().device_state_attributes
        if self._notification:
            data[ATTR_NOTIFICATION] = self._notification
        if self._lock_status:
            data[ATTR_LOCK_STATUS] = self._lock_status
        return data
