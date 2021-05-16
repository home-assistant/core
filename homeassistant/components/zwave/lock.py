"""Support for Z-Wave door locks."""
import logging

import voluptuous as vol

from homeassistant.components.lock import DOMAIN, LockEntity
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import ZWaveDeviceEntity, const

_LOGGER = logging.getLogger(__name__)

ATTR_NOTIFICATION = "notification"
ATTR_LOCK_STATUS = "lock_status"
ATTR_CODE_SLOT = "code_slot"
ATTR_USERCODE = "usercode"
CONFIG_ADVANCED = "Advanced"

SERVICE_SET_USERCODE = "set_usercode"
SERVICE_GET_USERCODE = "get_usercode"
SERVICE_CLEAR_USERCODE = "clear_usercode"

POLYCONTROL = 0x10E
DANALOCK_V2_BTZE = 0x2
POLYCONTROL_DANALOCK_V2_BTZE_LOCK = (POLYCONTROL, DANALOCK_V2_BTZE)
WORKAROUND_V2BTZE = 1
WORKAROUND_DEVICE_STATE = 2
WORKAROUND_TRACK_MESSAGE = 4
WORKAROUND_ALARM_TYPE = 8

DEVICE_MAPPINGS = {
    POLYCONTROL_DANALOCK_V2_BTZE_LOCK: WORKAROUND_V2BTZE,
    # Kwikset 914TRL ZW500 99100-078
    (0x0090, 0x440): WORKAROUND_DEVICE_STATE,
    (0x0090, 0x446): WORKAROUND_DEVICE_STATE,
    (0x0090, 0x238): WORKAROUND_DEVICE_STATE,
    # Kwikset 888ZW500-15S Smartcode 888
    (0x0090, 0x541): WORKAROUND_DEVICE_STATE,
    # Kwikset 916
    (0x0090, 0x0001): WORKAROUND_DEVICE_STATE,
    # Kwikset Obsidian
    (0x0090, 0x0742): WORKAROUND_DEVICE_STATE,
    # Yale Locks
    # Yale YRD210, YRD220, YRL220
    (0x0129, 0x0000): WORKAROUND_DEVICE_STATE | WORKAROUND_ALARM_TYPE,
    # Yale YRD210, YRD220
    (0x0129, 0x0209): WORKAROUND_DEVICE_STATE | WORKAROUND_ALARM_TYPE,
    # Yale YRL210, YRL220
    (0x0129, 0x0409): WORKAROUND_DEVICE_STATE | WORKAROUND_ALARM_TYPE,
    # Yale YRD256
    (0x0129, 0x0600): WORKAROUND_DEVICE_STATE | WORKAROUND_ALARM_TYPE,
    # Yale YRD110, YRD120
    (0x0129, 0x0800): WORKAROUND_DEVICE_STATE | WORKAROUND_ALARM_TYPE,
    # Yale YRD446
    (0x0129, 0x1000): WORKAROUND_DEVICE_STATE | WORKAROUND_ALARM_TYPE,
    # Yale YRL220
    (0x0129, 0x2132): WORKAROUND_DEVICE_STATE | WORKAROUND_ALARM_TYPE,
    (0x0129, 0x3CAC): WORKAROUND_DEVICE_STATE | WORKAROUND_ALARM_TYPE,
    # Yale YRD210, YRD220
    (0x0129, 0xAA00): WORKAROUND_DEVICE_STATE | WORKAROUND_ALARM_TYPE,
    # Yale YRD220
    (0x0129, 0xFFFF): WORKAROUND_DEVICE_STATE | WORKAROUND_ALARM_TYPE,
    # Yale YRL256
    (0x0129, 0x0F00): WORKAROUND_DEVICE_STATE | WORKAROUND_ALARM_TYPE,
    # Yale YRD220 (Older Yale products with incorrect vendor ID)
    (0x0109, 0x0000): WORKAROUND_DEVICE_STATE | WORKAROUND_ALARM_TYPE,
    # Schlage BE469
    (0x003B, 0x5044): WORKAROUND_DEVICE_STATE | WORKAROUND_TRACK_MESSAGE,
    # Schlage FE599NX
    (0x003B, 0x504C): WORKAROUND_DEVICE_STATE,
}

LOCK_NOTIFICATION = {
    "1": "Manual Lock",
    "2": "Manual Unlock",
    "5": "Keypad Lock",
    "6": "Keypad Unlock",
    "11": "Lock Jammed",
    "254": "Unknown Event",
}
NOTIFICATION_RF_LOCK = "3"
NOTIFICATION_RF_UNLOCK = "4"
LOCK_NOTIFICATION[NOTIFICATION_RF_LOCK] = "RF Lock"
LOCK_NOTIFICATION[NOTIFICATION_RF_UNLOCK] = "RF Unlock"

LOCK_ALARM_TYPE = {
    "9": "Deadbolt Jammed",
    "16": "Unlocked by Bluetooth ",
    "18": "Locked with Keypad by user ",
    "19": "Unlocked with Keypad by user ",
    "21": "Manually Locked ",
    "22": "Manually Unlocked ",
    "27": "Auto re-lock",
    "33": "User deleted: ",
    "112": "Master code changed or User added: ",
    "113": "Duplicate PIN code: ",
    "130": "RF module, power restored",
    "144": "Unlocked by NFC Tag or Card by user ",
    "161": "Tamper Alarm: ",
    "167": "Low Battery",
    "168": "Critical Battery Level",
    "169": "Battery too low to operate",
}
ALARM_RF_LOCK = "24"
ALARM_RF_UNLOCK = "25"
LOCK_ALARM_TYPE[ALARM_RF_LOCK] = "Locked by RF"
LOCK_ALARM_TYPE[ALARM_RF_UNLOCK] = "Unlocked by RF"

MANUAL_LOCK_ALARM_LEVEL = {
    "1": "by Key Cylinder or Inside thumb turn",
    "2": "by Touch function (lock and leave)",
}

TAMPER_ALARM_LEVEL = {"1": "Too many keypresses", "2": "Cover removed"}

LOCK_STATUS = {
    "1": True,
    "2": False,
    "3": True,
    "4": False,
    "5": True,
    "6": False,
    "9": False,
    "18": True,
    "19": False,
    "21": True,
    "22": False,
    "24": True,
    "25": False,
    "27": True,
}

ALARM_TYPE_STD = ["18", "19", "33", "112", "113", "144"]

SET_USERCODE_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
        vol.Required(ATTR_USERCODE): cv.string,
    }
)

GET_USERCODE_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
    }
)

CLEAR_USERCODE_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
    }
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Lock from Config Entry."""

    @callback
    def async_add_lock(lock):
        """Add Z-Wave Lock."""
        async_add_entities([lock])

    async_dispatcher_connect(hass, "zwave_new_lock", async_add_lock)

    network = hass.data[const.DATA_NETWORK]

    def set_usercode(service):
        """Set the usercode to index X on the lock."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        lock_node = network.nodes[node_id]
        code_slot = service.data.get(ATTR_CODE_SLOT)
        usercode = service.data.get(ATTR_USERCODE)

        for value in lock_node.get_values(
            class_id=const.COMMAND_CLASS_USER_CODE
        ).values():
            if value.index != code_slot:
                continue
            if len(str(usercode)) < 4:
                _LOGGER.error(
                    "Invalid code provided: (%s) "
                    "usercode must be at least 4 and at most"
                    " %s digits",
                    usercode,
                    len(value.data),
                )
                break
            value.data = str(usercode)
            break

    def get_usercode(service):
        """Get a usercode at index X on the lock."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        lock_node = network.nodes[node_id]
        code_slot = service.data.get(ATTR_CODE_SLOT)

        for value in lock_node.get_values(
            class_id=const.COMMAND_CLASS_USER_CODE
        ).values():
            if value.index != code_slot:
                continue
            _LOGGER.info("Usercode at slot %s is: %s", value.index, value.data)
            break

    def clear_usercode(service):
        """Set usercode to slot X on the lock."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        lock_node = network.nodes[node_id]
        code_slot = service.data.get(ATTR_CODE_SLOT)
        data = ""

        for value in lock_node.get_values(
            class_id=const.COMMAND_CLASS_USER_CODE
        ).values():
            if value.index != code_slot:
                continue
            for i in range(len(value.data)):
                data += "\0"
                i += 1
            _LOGGER.debug("Data to clear lock: %s", data)
            value.data = data
            _LOGGER.info("Usercode at slot %s is cleared", value.index)
            break

    hass.services.async_register(
        DOMAIN, SERVICE_SET_USERCODE, set_usercode, schema=SET_USERCODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_USERCODE, get_usercode, schema=GET_USERCODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_USERCODE, clear_usercode, schema=CLEAR_USERCODE_SCHEMA
    )


def get_device(node, values, **kwargs):
    """Create Z-Wave entity device."""
    return ZwaveLock(values)


class ZwaveLock(ZWaveDeviceEntity, LockEntity):
    """Representation of a Z-Wave Lock."""

    def __init__(self, values):
        """Initialize the Z-Wave lock device."""
        ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self._state = None
        self._notification = None
        self._lock_status = None
        self._v2btze = None
        self._state_workaround = False
        self._track_message_workaround = False
        self._previous_message = None
        self._alarm_type_workaround = False

        # Enable appropriate workaround flags for our device
        # Make sure that we have values for the key before converting to int
        if self.node.manufacturer_id.strip() and self.node.product_id.strip():
            specific_sensor_key = (
                int(self.node.manufacturer_id, 16),
                int(self.node.product_id, 16),
            )
            if specific_sensor_key in DEVICE_MAPPINGS:
                workaround = DEVICE_MAPPINGS[specific_sensor_key]
                if workaround & WORKAROUND_V2BTZE:
                    self._v2btze = 1
                    _LOGGER.debug("Polycontrol Danalock v2 BTZE workaround enabled")
                if workaround & WORKAROUND_DEVICE_STATE:
                    self._state_workaround = True
                    _LOGGER.debug("Notification device state workaround enabled")
                if workaround & WORKAROUND_TRACK_MESSAGE:
                    self._track_message_workaround = True
                    _LOGGER.debug("Message tracking workaround enabled")
                if workaround & WORKAROUND_ALARM_TYPE:
                    self._alarm_type_workaround = True
                    _LOGGER.debug("Alarm Type device state workaround enabled")
        self.update_properties()

    def update_properties(self):
        """Handle data changes for node values."""
        self._state = self.values.primary.data
        _LOGGER.debug("lock state set to %s", self._state)
        if self.values.access_control:
            notification_data = self.values.access_control.data
            self._notification = LOCK_NOTIFICATION.get(str(notification_data))
            if self._state_workaround:
                self._state = LOCK_STATUS.get(str(notification_data))
                _LOGGER.debug("workaround: lock state set to %s", self._state)
            if (
                self._v2btze
                and self.values.v2btze_advanced
                and self.values.v2btze_advanced.data == CONFIG_ADVANCED
            ):
                self._state = LOCK_STATUS.get(str(notification_data))
                _LOGGER.debug(
                    "Lock state set from Access Control value and is %s, get=%s",
                    str(notification_data),
                    self.state,
                )

        if self._track_message_workaround:
            this_message = self.node.stats["lastReceivedMessage"][5]

            if this_message == const.COMMAND_CLASS_DOOR_LOCK:
                self._state = self.values.primary.data
                _LOGGER.debug("set state to %s based on message tracking", self._state)
                if self._previous_message == const.COMMAND_CLASS_DOOR_LOCK:
                    if self._state:
                        self._notification = LOCK_NOTIFICATION[NOTIFICATION_RF_LOCK]
                        self._lock_status = LOCK_ALARM_TYPE[ALARM_RF_LOCK]
                    else:
                        self._notification = LOCK_NOTIFICATION[NOTIFICATION_RF_UNLOCK]
                        self._lock_status = LOCK_ALARM_TYPE[ALARM_RF_UNLOCK]
                    return

            self._previous_message = this_message

        if not self.values.alarm_type:
            return

        alarm_type = self.values.alarm_type.data
        if self.values.alarm_level:
            alarm_level = self.values.alarm_level.data
        else:
            alarm_level = None

        if not alarm_type:
            return

        if self._alarm_type_workaround:
            self._state = LOCK_STATUS.get(str(alarm_type))
            _LOGGER.debug(
                "workaround: lock state set to %s -- alarm type: %s",
                self._state,
                str(alarm_type),
            )

        if alarm_type == 21:
            self._lock_status = (
                f"{LOCK_ALARM_TYPE.get(str(alarm_type))}"
                f"{MANUAL_LOCK_ALARM_LEVEL.get(str(alarm_level))}"
            )
            return
        if str(alarm_type) in ALARM_TYPE_STD:
            self._lock_status = f"{LOCK_ALARM_TYPE.get(str(alarm_type))}{alarm_level}"
            return
        if alarm_type == 161:
            self._lock_status = (
                f"{LOCK_ALARM_TYPE.get(str(alarm_type))}"
                f"{TAMPER_ALARM_LEVEL.get(str(alarm_level))}"
            )

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
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        data = super().extra_state_attributes
        if self._notification:
            data[ATTR_NOTIFICATION] = self._notification
        if self._lock_status:
            data[ATTR_LOCK_STATUS] = self._lock_status
        return data
