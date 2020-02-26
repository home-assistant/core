"""Support for the Netatmo binary sensors."""
import logging

import pyatmo

from homeassistant.components.binary_sensor import BinarySensorDevice

from .camera import CameraData
from .const import AUTH, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

# These are the available sensors mapped to binary_sensor class
WELCOME_SENSOR_TYPES = {
    "Someone known": "motion",
    "Someone unknown": "motion",
    "Motion": "motion",
}
PRESENCE_SENSOR_TYPES = {
    "Outdoor motion": "motion",
    "Outdoor human": "motion",
    "Outdoor animal": "motion",
    "Outdoor vehicle": "motion",
}
TAG_SENSOR_TYPES = {"Tag Vibration": "vibration", "Tag Open": "opening"}

SENSOR_TYPES = {
    "NACamera": WELCOME_SENSOR_TYPES,
    "NOC": PRESENCE_SENSOR_TYPES,
}

CONF_HOME = "home"
CONF_CAMERAS = "cameras"
CONF_WELCOME_SENSORS = "welcome_sensors"
CONF_PRESENCE_SENSORS = "presence_sensors"
CONF_TAG_SENSORS = "tag_sensors"

DEFAULT_TIMEOUT = 90


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the access to Netatmo binary sensor."""
    auth = hass.data[DOMAIN][entry.entry_id][AUTH]

    def get_entities():
        """Retrieve Netatmo entities."""
        entities = []

        def get_camera_home_id(data, camera_id):
            """Return the home id for a given camera id."""
            for home_id in data.camera_data.cameras:
                for camera in data.camera_data.cameras[home_id].values():
                    if camera["id"] == camera_id:
                        return home_id
            return None

        try:
            data = CameraData(hass, auth)

            for camera in data.get_all_cameras():
                home_id = get_camera_home_id(data, camera_id=camera["id"])

                sensor_types = {}
                sensor_types.update(SENSOR_TYPES[camera["type"]])

                # Tags are only supported with Netatmo Welcome indoor cameras
                modules = data.get_modules(camera["id"])
                if camera["type"] == "NACamera" and modules:
                    for module in modules:
                        for sensor_type in TAG_SENSOR_TYPES:
                            _LOGGER.debug(
                                "Adding camera tag %s (%s)",
                                module["name"],
                                module["id"],
                            )
                            entities.append(
                                NetatmoBinarySensor(
                                    data,
                                    camera["id"],
                                    home_id,
                                    sensor_type,
                                    module["id"],
                                )
                            )

                for sensor_type in sensor_types:
                    entities.append(
                        NetatmoBinarySensor(data, camera["id"], home_id, sensor_type)
                    )
        except pyatmo.NoDevice:
            _LOGGER.debug("No camera entities to add")

        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class NetatmoBinarySensor(BinarySensorDevice):
    """Represent a single binary sensor in a Netatmo Camera device."""

    def __init__(self, data, camera_id, home_id, sensor_type, module_id=None):
        """Set up for access to the Netatmo camera events."""
        self._data = data
        self._camera_id = camera_id
        self._module_id = module_id
        self._sensor_type = sensor_type
        camera_info = data.camera_data.cameraById(cid=camera_id)
        self._camera_name = camera_info["name"]
        self._camera_type = camera_info["type"]
        self._home_id = home_id
        self._home_name = self._data.camera_data.getHomeName(home_id=home_id)
        self._timeout = DEFAULT_TIMEOUT
        if module_id:
            self._module_name = data.camera_data.moduleById(mid=module_id)["name"]
            self._name = (
                f"{MANUFACTURER} {self._camera_name} {self._module_name} {sensor_type}"
            )
            self._unique_id = (
                f"{self._camera_id}-{self._module_id}-"
                f"{self._camera_type}-{sensor_type}"
            )
        else:
            self._name = f"{MANUFACTURER} {self._camera_name} {sensor_type}"
            self._unique_id = f"{self._camera_id}-{self._camera_type}-{sensor_type}"
        self._state = None

    @property
    def name(self):
        """Return the name of the Netatmo device and this sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._unique_id

    @property
    def device_class(self):
        """Return the class of this sensor."""
        if self._camera_type == "NACamera":
            return WELCOME_SENSOR_TYPES.get(self._sensor_type)
        if self._camera_type == "NOC":
            return PRESENCE_SENSOR_TYPES.get(self._sensor_type)
        return TAG_SENSOR_TYPES.get(self._sensor_type)

    @property
    def device_info(self):
        """Return the device info for the sensor."""
        return {
            "identifiers": {(DOMAIN, self._camera_id)},
            "name": self._camera_name,
            "manufacturer": MANUFACTURER,
            "model": self._camera_type,
        }

    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        return self._state

    def update(self):
        """Request an update from the Netatmo API."""
        self._data.update()
        self._data.update_event(camera_type=self._camera_type)

        if self._camera_type == "NACamera":
            if self._sensor_type == "Someone known":
                self._state = self._data.camera_data.someone_known_seen(
                    cid=self._camera_id, exclude=self._timeout
                )
            elif self._sensor_type == "Someone unknown":
                self._state = self._data.camera_data.someone_unknown_seen(
                    cid=self._camera_id, exclude=self._timeout
                )
            elif self._sensor_type == "Motion":
                self._state = self._data.camera_data.motion_detected(
                    cid=self._camera_id, exclude=self._timeout
                )
        elif self._camera_type == "NOC":
            if self._sensor_type == "Outdoor motion":
                self._state = self._data.camera_data.outdoor_motion_detected(
                    cid=self._camera_id, offset=self._timeout
                )
            elif self._sensor_type == "Outdoor human":
                self._state = self._data.camera_data.human_detected(
                    cid=self._camera_id, offset=self._timeout
                )
            elif self._sensor_type == "Outdoor animal":
                self._state = self._data.camera_data.animal_detected(
                    cid=self._camera_id, offset=self._timeout
                )
            elif self._sensor_type == "Outdoor vehicle":
                self._state = self._data.camera_data.car_detected(
                    cid=self._camera_id, offset=self._timeout
                )
        if self._sensor_type == "Tag Vibration":
            self._state = self._data.camera_data.module_motion_detected(
                mid=self._module_id, cid=self._camera_id, exclude=self._timeout
            )
        elif self._sensor_type == "Tag Open":
            self._state = self._data.camera_data.module_opened(
                mid=self._module_id, cid=self._camera_id, exclude=self._timeout
            )
