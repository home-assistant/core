"""Support for August binary sensors."""
from datetime import datetime, timedelta
import logging

from august.activity import ActivityType
from august.lock import LockDoorStatus
from august.util import update_lock_detail_from_activity

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY,
    BinarySensorDevice,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

from .const import (
    AUGUST_DEVICE_UPDATE,
    DATA_AUGUST,
    DEFAULT_NAME,
    DOMAIN,
    MIN_TIME_BETWEEN_DETAIL_UPDATES,
)

_LOGGER = logging.getLogger(__name__)

TIME_TO_DECLARE_DETECTION = timedelta(seconds=60)

SCAN_INTERVAL = MIN_TIME_BETWEEN_DETAIL_UPDATES


async def _async_retrieve_online_state(data, detail):
    """Get the latest state of the sensor."""
    return detail.is_online or detail.is_standby


async def _async_retrieve_motion_state(data, detail):

    return await _async_activity_time_based_state(
        data,
        detail.device_id,
        [ActivityType.DOORBELL_MOTION, ActivityType.DOORBELL_DING],
    )


async def _async_retrieve_ding_state(data, detail):

    return await _async_activity_time_based_state(
        data, detail.device_id, [ActivityType.DOORBELL_DING]
    )


async def _async_activity_time_based_state(data, device_id, activity_types):
    """Get the latest state of the sensor."""
    latest = data.activity_stream.async_get_latest_device_activity(
        device_id, activity_types
    )

    if latest is not None:
        start = latest.activity_start_time
        end = latest.activity_end_time + TIME_TO_DECLARE_DETECTION
        return start <= datetime.now() <= end
    return None


SENSOR_NAME = 0
SENSOR_DEVICE_CLASS = 1
SENSOR_STATE_PROVIDER = 2

# sensor_type: [name, device_class, async_state_provider]
SENSOR_TYPES_DOORBELL = {
    "doorbell_ding": ["Ding", DEVICE_CLASS_OCCUPANCY, _async_retrieve_ding_state],
    "doorbell_motion": ["Motion", DEVICE_CLASS_MOTION, _async_retrieve_motion_state],
    "doorbell_online": [
        "Online",
        DEVICE_CLASS_CONNECTIVITY,
        _async_retrieve_online_state,
    ],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the August binary sensors."""
    data = hass.data[DOMAIN][config_entry.entry_id][DATA_AUGUST]
    devices = []

    for door in data.locks:
        if not data.lock_has_doorsense(door.device_id):
            _LOGGER.debug("Not adding sensor class door for lock %s ", door.device_name)
            continue

        _LOGGER.debug("Adding sensor class door for %s", door.device_name)
        devices.append(AugustDoorBinarySensor(data, "door_open", door))

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
        self._undo_dispatch_subscription = None
        self._data = data
        self._sensor_type = sensor_type
        self._door = door
        self._state = None
        self._available = False
        self._firmware_version = None
        self._model = None

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
        """Return the class of this device."""
        return "door"

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return f"{self._door.device_name} Open"

    async def async_update(self):
        """Get the latest state of the sensor and update activity."""
        door_activity = self._data.activity_stream.async_get_latest_device_activity(
            self._door.device_id, [ActivityType.DOOR_OPERATION]
        )
        detail = await self._data.async_get_lock_detail(self._door.device_id)

        if door_activity is not None:
            update_lock_detail_from_activity(detail, door_activity)

        lock_door_state = None
        self._available = False
        if detail is not None:
            lock_door_state = detail.door_state
            self._available = detail.bridge_is_online
            self._firmware_version = detail.firmware_version
            self._model = detail.model

        self._state = lock_door_state == LockDoorStatus.OPEN

    @property
    def unique_id(self) -> str:
        """Get the unique of the door open binary sensor."""
        return f"{self._door.device_id}_open"

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._door.device_id)},
            "name": self._door.device_name,
            "manufacturer": DEFAULT_NAME,
            "sw_version": self._firmware_version,
            "model": self._model,
        }

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._undo_dispatch_subscription = async_dispatcher_connect(
            self.hass, f"{AUGUST_DEVICE_UPDATE}-{self._door.device_id}", update
        )

    async def async_will_remove_from_hass(self):
        """Undo subscription."""
        if self._undo_dispatch_subscription:
            self._undo_dispatch_subscription()


class AugustDoorbellBinarySensor(BinarySensorDevice):
    """Representation of an August binary sensor."""

    def __init__(self, data, sensor_type, doorbell):
        """Initialize the sensor."""
        self._undo_dispatch_subscription = None
        self._check_for_off_update_listener = None
        self._data = data
        self._sensor_type = sensor_type
        self._doorbell = doorbell
        self._state = None
        self._available = False
        self._firmware_version = None
        self._model = None

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
        return f"{self._doorbell.device_name} {SENSOR_TYPES_DOORBELL[self._sensor_type][SENSOR_NAME]}"

    async def async_update(self):
        """Get the latest state of the sensor."""
        self._cancel_any_pending_updates()
        async_state_provider = SENSOR_TYPES_DOORBELL[self._sensor_type][
            SENSOR_STATE_PROVIDER
        ]
        detail = await self._data.async_get_doorbell_detail(self._doorbell.device_id)
        # The doorbell will go into standby mode when there is no motion
        # for a short while. It will wake by itself when needed so we need
        # to consider is available or we will not report motion or dings
        if self.device_class == DEVICE_CLASS_CONNECTIVITY:
            self._available = True
        else:
            self._available = detail is not None and (
                detail.is_online or detail.is_standby
            )

        self._state = None
        if detail is not None:
            self._firmware_version = detail.firmware_version
            self._model = detail.model
            self._state = await async_state_provider(self._data, detail)
            if self._state and self.device_class != DEVICE_CLASS_CONNECTIVITY:
                self._schedule_update_to_recheck_turn_off_sensor()

    def _schedule_update_to_recheck_turn_off_sensor(self):
        """Schedule an update to recheck the sensor to see if it is ready to turn off."""

        @callback
        def _scheduled_update(now):
            """Timer callback for sensor update."""
            _LOGGER.debug("%s: executing scheduled update", self.entity_id)
            self.async_schedule_update_ha_state(True)
            self._check_for_off_update_listener = None

        self._check_for_off_update_listener = async_track_point_in_utc_time(
            self.hass, _scheduled_update, utcnow() + TIME_TO_DECLARE_DETECTION
        )

    def _cancel_any_pending_updates(self):
        """Cancel any updates to recheck a sensor to see if it is ready to turn off."""
        if self._check_for_off_update_listener:
            self._check_for_off_update_listener()
            self._check_for_off_update_listener = None

    @property
    def unique_id(self) -> str:
        """Get the unique id of the doorbell sensor."""
        return (
            f"{self._doorbell.device_id}_"
            f"{SENSOR_TYPES_DOORBELL[self._sensor_type][SENSOR_NAME].lower()}"
        )

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._doorbell.device_id)},
            "name": self._doorbell.device_name,
            "manufacturer": "August",
            "sw_version": self._firmware_version,
            "model": self._model,
        }

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._undo_dispatch_subscription = async_dispatcher_connect(
            self.hass, f"{AUGUST_DEVICE_UPDATE}-{self._doorbell.device_id}", update
        )

    async def async_will_remove_from_hass(self):
        """Undo subscription."""
        if self._undo_dispatch_subscription:
            self._undo_dispatch_subscription()
