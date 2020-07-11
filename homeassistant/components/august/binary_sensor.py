"""Support for August binary sensors."""
from datetime import datetime, timedelta
import logging

from august.activity import ActivityType
from august.lock import LockDoorStatus
from august.util import update_lock_detail_from_activity

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

from .const import DATA_AUGUST, DOMAIN
from .entity import AugustEntityMixin

_LOGGER = logging.getLogger(__name__)

TIME_TO_DECLARE_DETECTION = timedelta(seconds=60)


def _retrieve_online_state(data, detail):
    """Get the latest state of the sensor."""
    # The doorbell will go into standby mode when there is no motion
    # for a short while. It will wake by itself when needed so we need
    # to consider is available or we will not report motion or dings

    return detail.is_online or detail.is_standby


def _retrieve_motion_state(data, detail):

    return _activity_time_based_state(
        data,
        detail.device_id,
        [ActivityType.DOORBELL_MOTION, ActivityType.DOORBELL_DING],
    )


def _retrieve_ding_state(data, detail):

    return _activity_time_based_state(
        data, detail.device_id, [ActivityType.DOORBELL_DING]
    )


def _activity_time_based_state(data, device_id, activity_types):
    """Get the latest state of the sensor."""
    latest = data.activity_stream.get_latest_device_activity(device_id, activity_types)

    if latest is not None:
        start = latest.activity_start_time
        end = latest.activity_end_time + TIME_TO_DECLARE_DETECTION
        return start <= datetime.now() <= end
    return None


SENSOR_NAME = 0
SENSOR_DEVICE_CLASS = 1
SENSOR_STATE_PROVIDER = 2
SENSOR_STATE_IS_TIME_BASED = 3

# sensor_type: [name, device_class, state_provider, is_time_based]
SENSOR_TYPES_DOORBELL = {
    "doorbell_ding": ["Ding", DEVICE_CLASS_OCCUPANCY, _retrieve_ding_state, True],
    "doorbell_motion": ["Motion", DEVICE_CLASS_MOTION, _retrieve_motion_state, True],
    "doorbell_online": [
        "Online",
        DEVICE_CLASS_CONNECTIVITY,
        _retrieve_online_state,
        False,
    ],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the August binary sensors."""
    data = hass.data[DOMAIN][config_entry.entry_id][DATA_AUGUST]
    devices = []

    for door in data.locks:
        detail = data.get_device_detail(door.device_id)
        if not detail.doorsense:
            _LOGGER.debug(
                "Not adding sensor class door for lock %s because it does not have doorsense",
                door.device_name,
            )
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


class AugustDoorBinarySensor(AugustEntityMixin, BinarySensorEntity):
    """Representation of an August Door binary sensor."""

    def __init__(self, data, sensor_type, device):
        """Initialize the sensor."""
        super().__init__(data, device)
        self._data = data
        self._sensor_type = sensor_type
        self._device = device
        self._update_from_data()

    @property
    def available(self):
        """Return the availability of this sensor."""
        return self._detail.bridge_is_online

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._detail.door_state == LockDoorStatus.OPEN

    @property
    def device_class(self):
        """Return the class of this device."""
        return DEVICE_CLASS_DOOR

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return f"{self._device.device_name} Open"

    @callback
    def _update_from_data(self):
        """Get the latest state of the sensor and update activity."""
        door_activity = self._data.activity_stream.get_latest_device_activity(
            self._device_id, [ActivityType.DOOR_OPERATION]
        )

        if door_activity is not None:
            update_lock_detail_from_activity(self._detail, door_activity)

    @property
    def unique_id(self) -> str:
        """Get the unique of the door open binary sensor."""
        return f"{self._device_id}_open"


class AugustDoorbellBinarySensor(AugustEntityMixin, BinarySensorEntity):
    """Representation of an August binary sensor."""

    def __init__(self, data, sensor_type, device):
        """Initialize the sensor."""
        super().__init__(data, device)
        self._check_for_off_update_listener = None
        self._data = data
        self._sensor_type = sensor_type
        self._device = device
        self._state = None
        self._available = False
        self._update_from_data()

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
        return f"{self._device.device_name} {SENSOR_TYPES_DOORBELL[self._sensor_type][SENSOR_NAME]}"

    @property
    def _state_provider(self):
        """Return the state provider for the binary sensor."""
        return SENSOR_TYPES_DOORBELL[self._sensor_type][SENSOR_STATE_PROVIDER]

    @property
    def _is_time_based(self):
        """Return true of false if the sensor is time based."""
        return SENSOR_TYPES_DOORBELL[self._sensor_type][SENSOR_STATE_IS_TIME_BASED]

    @callback
    def _update_from_data(self):
        """Get the latest state of the sensor."""
        self._cancel_any_pending_updates()
        self._state = self._state_provider(self._data, self._detail)

        if self._is_time_based:
            self._available = _retrieve_online_state(self._data, self._detail)
            self._schedule_update_to_recheck_turn_off_sensor()
        else:
            self._available = True

    def _schedule_update_to_recheck_turn_off_sensor(self):
        """Schedule an update to recheck the sensor to see if it is ready to turn off."""

        # If the sensor is already off there is nothing to do
        if not self._state:
            return

        # self.hass is only available after setup is completed
        # and we will recheck in async_added_to_hass
        if not self.hass:
            return

        @callback
        def _scheduled_update(now):
            """Timer callback for sensor update."""
            self._check_for_off_update_listener = None
            self._update_from_data()

        self._check_for_off_update_listener = async_track_point_in_utc_time(
            self.hass, _scheduled_update, utcnow() + TIME_TO_DECLARE_DETECTION
        )

    def _cancel_any_pending_updates(self):
        """Cancel any updates to recheck a sensor to see if it is ready to turn off."""
        if self._check_for_off_update_listener:
            _LOGGER.debug("%s: canceled pending update", self.entity_id)
            self._check_for_off_update_listener()
            self._check_for_off_update_listener = None

    async def async_added_to_hass(self):
        """Call the mixin to subscribe and setup an async_track_point_in_utc_time to turn off the sensor if needed."""
        self._schedule_update_to_recheck_turn_off_sensor()
        await super().async_added_to_hass()

    @property
    def unique_id(self) -> str:
        """Get the unique id of the doorbell sensor."""
        return (
            f"{self._device_id}_"
            f"{SENSOR_TYPES_DOORBELL[self._sensor_type][SENSOR_NAME].lower()}"
        )
