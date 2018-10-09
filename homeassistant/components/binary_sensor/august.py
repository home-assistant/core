"""
Support for August binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.august/
"""
import logging
from datetime import timedelta, datetime

from homeassistant.components.august import DATA_AUGUST
from homeassistant.components.binary_sensor import (BinarySensorDevice)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['august']

SCAN_INTERVAL = timedelta(seconds=5)


def _retrieve_online_state(data, doorbell):
    """Get the latest state of the sensor."""
    detail = data.get_doorbell_detail(doorbell.device_id)
    return detail.is_online


def _retrieve_motion_state(data, doorbell):
    from august.activity import ActivityType
    return _activity_time_based_state(data, doorbell,
                                      [ActivityType.DOORBELL_MOTION,
                                       ActivityType.DOORBELL_DING])


def _retrieve_ding_state(data, doorbell):
    from august.activity import ActivityType
    return _activity_time_based_state(data, doorbell,
                                      [ActivityType.DOORBELL_DING])


def _retrieve_lock_door_state(data, lock):
    return data.get_lock_door_status(lock.device_id)


def _activity_time_based_state(data, doorbell, activity_types):
    """Get the latest state of the sensor."""
    latest = data.get_latest_device_activity(doorbell.device_id,
                                             *activity_types)

    if latest is not None:
        start = latest.activity_start_time
        end = latest.activity_end_time + timedelta(seconds=30)
        return start <= datetime.now() <= end
    return None


# Sensor types: Name, device_class, state_provider
SENSOR_TYPES = {
    'doorbell_ding': ['Ding', 'occupancy', _retrieve_ding_state],
    'doorbell_motion': ['Motion', 'motion', _retrieve_motion_state],
    'doorbell_online': ['Online', 'connectivity', _retrieve_online_state],
    'lock_door_status': ['Door', 'door', _retrieve_lock_door_state],
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the August binary sensors."""
    data = hass.data[DATA_AUGUST]
    devices = []

    for doorbell in data.doorbells:
        for sensor_type in SENSOR_TYPES:
            if SENSOR_TYPES[sensor_type][1] == 'door':
                continue
            _LOGGER.debug("Adding doorbell sensor class %s for %s",
                          SENSOR_TYPES[sensor_type][1], doorbell.device_name)
            devices.append(AugustBinarySensor(data, sensor_type, doorbell))

    from august.lock import LockDoorStatus
    for lock in data.locks:
        for sensor_type in SENSOR_TYPES:
            if SENSOR_TYPES[sensor_type][1] != 'door':
                continue

            state_provider = SENSOR_TYPES[sensor_type][2]
            if state_provider(data, lock) is LockDoorStatus.UNKNOWN:
                _LOGGER.debug(
                    ("Not adding sensor class %s for lock %s "
                     "as status is unknown"),
                    SENSOR_TYPES[sensor_type][1], lock.device_name
                )
            else:
                _LOGGER.debug(
                    "Adding lock sensor class %s for %s",
                    SENSOR_TYPES[sensor_type][1], lock.device_name
                )
                devices.append(AugustBinarySensor(data, sensor_type, lock))

    add_entities(devices, True)


class AugustBinarySensor(BinarySensorDevice):
    """Representation of an August binary sensor."""

    def __init__(self, data, sensor_type, device):
        """Initialize the sensor."""
        self._data = data
        self._sensor_type = sensor_type
        self._device = device
        self._state = None

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        from august.lock import LockDoorStatus

        # For door sensor, return true if open or unknown,
        # otherwise return false.
        if SENSOR_TYPES[self._sensor_type][1] == 'door':
            return self._state is not LockDoorStatus.CLOSED

        return self._state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SENSOR_TYPES[self._sensor_type][1]

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return "{} {}".format(self._device.device_name,
                              SENSOR_TYPES[self._sensor_type][0])

    def update(self):
        """Get the latest state of the sensor."""
        state_provider = SENSOR_TYPES[self._sensor_type][2]
        self._state = state_provider(self._data, self._device)
