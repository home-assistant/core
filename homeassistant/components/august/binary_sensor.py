"""Support for August binary sensors."""
from datetime import datetime, timedelta
import logging

from august.activity import ACTIVITY_ACTION_STATES, ActivityType
from august.lock import LockDoorStatus

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.util import dt

from . import DATA_AUGUST

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


async def _async_retrieve_door_state(data, lock):
    """Get the latest state of the DoorSense sensor."""
    return await data.async_get_door_state(lock.device_id)


async def _async_retrieve_online_state(data, doorbell):
    """Get the latest state of the sensor."""
    detail = await data.async_get_doorbell_detail(doorbell.device_id)
    if detail is None:
        return None

    return detail.is_online


async def _async_retrieve_motion_state(data, doorbell):

    return await _async_activity_time_based_state(
        data, doorbell, [ActivityType.DOORBELL_MOTION, ActivityType.DOORBELL_DING]
    )


async def _async_retrieve_ding_state(data, doorbell):

    return await _async_activity_time_based_state(
        data, doorbell, [ActivityType.DOORBELL_DING]
    )


async def _async_activity_time_based_state(data, doorbell, activity_types):
    """Get the latest state of the sensor."""
    latest = await data.async_get_latest_device_activity(
        doorbell.device_id, *activity_types
    )

    if latest is not None:
        start = latest.activity_start_time
        end = latest.activity_end_time + timedelta(seconds=45)
        return start <= datetime.now() <= end
    return None


SENSOR_NAME = 0
SENSOR_DEVICE_CLASS = 1
SENSOR_STATE_PROVIDER = 2

# sensor_type: [name, device_class, async_state_provider]
SENSOR_TYPES_DOOR = {"door_open": ["Open", "door", _async_retrieve_door_state]}

SENSOR_TYPES_DOORBELL = {
    "doorbell_ding": ["Ding", "occupancy", _async_retrieve_ding_state],
    "doorbell_motion": ["Motion", "motion", _async_retrieve_motion_state],
    "doorbell_online": ["Online", "connectivity", _async_retrieve_online_state],
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the August binary sensors."""
    data = hass.data[DATA_AUGUST]
    devices = []

    for door in data.locks:
        for sensor_type in SENSOR_TYPES_DOOR:
            if not data.lock_has_doorsense(door.device_id):
                _LOGGER.debug(
                    "Not adding sensor class %s for lock %s ",
                    SENSOR_TYPES_DOOR[sensor_type][SENSOR_DEVICE_CLASS],
                    door.device_name,
                )
                continue

            _LOGGER.debug(
                "Adding sensor class %s for %s",
                SENSOR_TYPES_DOOR[sensor_type][SENSOR_DEVICE_CLASS],
                door.device_name,
            )
            devices.append(AugustDoorBinarySensor(data, sensor_type, door))

    for doorbell in data.doorbells:
        for sensor_type in SENSOR_TYPES_DOORBELL:
            _LOGGER.debug(
                "Adding doorbell sensor class %s for %s",
                SENSOR_TYPES_DOORBELL[sensor_type][SENSOR_DEVICE_CLASS],
                doorbell.device_name,
            )
            devices.append(AugustDoorbellBinarySensor(data, sensor_type, doorbell))

    async_add_entities(devices, True)


class AugustDoorBinarySensor(BinarySensorDevice):
    """Representation of an August Door binary sensor."""

    def __init__(self, data, sensor_type, door):
        """Initialize the sensor."""
        self._data = data
        self._sensor_type = sensor_type
        self._door = door
        self._state = None
        self._available = False

    @property
    def available(self):
        """Return the availability of this sensor."""
        return self._available

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SENSOR_TYPES_DOOR[self._sensor_type][SENSOR_DEVICE_CLASS]

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return "{} {}".format(
            self._door.device_name, SENSOR_TYPES_DOOR[self._sensor_type][SENSOR_NAME]
        )

    async def async_update(self):
        """Get the latest state of the sensor and update activity."""
        async_state_provider = SENSOR_TYPES_DOOR[self._sensor_type][
            SENSOR_STATE_PROVIDER
        ]
        lock_door_state = await async_state_provider(self._data, self._door)
        self._available = (
            lock_door_state is not None and lock_door_state != LockDoorStatus.UNKNOWN
        )
        self._state = lock_door_state == LockDoorStatus.OPEN

        door_activity = await self._data.async_get_latest_device_activity(
            self._door.device_id, ActivityType.DOOR_OPERATION
        )

        if door_activity is not None:
            self._sync_door_activity(door_activity)

    def _update_door_state(self, door_state, update_start_time):
        new_state = door_state == LockDoorStatus.OPEN
        if self._state != new_state:
            self._state = new_state
            self._data.update_door_state(
                self._door.device_id, door_state, update_start_time
            )

    def _sync_door_activity(self, door_activity):
        """Check the activity for the latest door open/close activity (events).

        We use this to determine the door state in between calls to the lock
        api as we update it more frequently
        """
        last_door_state_update_time_utc = self._data.get_last_door_state_update_time_utc(
            self._door.device_id
        )
        activity_end_time_utc = dt.as_utc(door_activity.activity_end_time)

        if activity_end_time_utc > last_door_state_update_time_utc:
            _LOGGER.debug(
                "The activity log has new events for %s: [action=%s] [activity_end_time_utc=%s] > [last_door_state_update_time_utc=%s]",
                self.name,
                door_activity.action,
                activity_end_time_utc,
                last_door_state_update_time_utc,
            )
            activity_start_time_utc = dt.as_utc(door_activity.activity_start_time)
            if door_activity.action in ACTIVITY_ACTION_STATES:
                self._update_door_state(
                    ACTIVITY_ACTION_STATES[door_activity.action],
                    activity_start_time_utc,
                )
            else:
                _LOGGER.info(
                    "Unhandled door activity action %s for %s",
                    door_activity.action,
                    self.name,
                )

    @property
    def unique_id(self) -> str:
        """Get the unique of the door open binary sensor."""
        return "{:s}_{:s}".format(
            self._door.device_id,
            SENSOR_TYPES_DOOR[self._sensor_type][SENSOR_NAME].lower(),
        )


class AugustDoorbellBinarySensor(BinarySensorDevice):
    """Representation of an August binary sensor."""

    def __init__(self, data, sensor_type, doorbell):
        """Initialize the sensor."""
        self._data = data
        self._sensor_type = sensor_type
        self._doorbell = doorbell
        self._state = None
        self._available = False

    @property
    def available(self):
        """Return the availability of this sensor."""
        return self._available

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SENSOR_TYPES_DOORBELL[self._sensor_type][SENSOR_DEVICE_CLASS]

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return "{} {}".format(
            self._doorbell.device_name,
            SENSOR_TYPES_DOORBELL[self._sensor_type][SENSOR_NAME],
        )

    async def async_update(self):
        """Get the latest state of the sensor."""
        async_state_provider = SENSOR_TYPES_DOORBELL[self._sensor_type][
            SENSOR_STATE_PROVIDER
        ]
        self._state = await async_state_provider(self._data, self._doorbell)
        # The doorbell will go into standby mode when there is no motion
        # for a short while. It will wake by itself when needed so we need
        # to consider is available or we will not report motion or dings
        self._available = self._doorbell.is_online or self._doorbell.status == "standby"

    @property
    def unique_id(self) -> str:
        """Get the unique id of the doorbell sensor."""
        return "{:s}_{:s}".format(
            self._doorbell.device_id,
            SENSOR_TYPES_DOORBELL[self._sensor_type][SENSOR_NAME].lower(),
        )
