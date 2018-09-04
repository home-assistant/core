"""
Support for August binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.august/
"""
from datetime import timedelta, datetime

from homeassistant.components.august import DATA_AUGUST
from homeassistant.components.binary_sensor import (BinarySensorDevice)

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
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the August binary sensors."""
    data = hass.data[DATA_AUGUST]
    devices = []

    for doorbell in data.doorbells:
        for sensor_type in SENSOR_TYPES:
            devices.append(AugustBinarySensor(data, sensor_type, doorbell))

    add_entities(devices, True)


class AugustBinarySensor(BinarySensorDevice):
    """Representation of an August binary sensor."""

    def __init__(self, data, sensor_type, doorbell):
        """Initialize the sensor."""
        self._data = data
        self._sensor_type = sensor_type
        self._doorbell = doorbell
        self._state = None

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SENSOR_TYPES[self._sensor_type][1]

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return "{} {}".format(self._doorbell.device_name,
                              SENSOR_TYPES[self._sensor_type][0])

    def update(self):
        """Get the latest state of the sensor."""
        state_provider = SENSOR_TYPES[self._sensor_type][2]
        self._state = state_provider(self._data, self._doorbell)
