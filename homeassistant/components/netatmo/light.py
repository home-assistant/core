"""Support for the Netatmo camera lights."""
import logging

import pyatmo

from homeassistant.components.light import Light

from .camera import CameraData
from .const import AUTH, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Netatmo camera light platform."""
    auth = hass.data[DOMAIN][entry.entry_id][AUTH]

    def get_entities():
        """Retrieve Netatmo entities."""
        entities = []

        try:
            camera_data = CameraData(hass, auth)

            for camera in camera_data.get_all_cameras():
                if camera["type"] == "NOC":
                    _LOGGER.debug("Setting up camera %s", camera["id"])
                    entities.append(NetatmoLight(camera_data, camera["id"]))
        except pyatmo.NoDevice:
            _LOGGER.debug("No cameras found")

        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class NetatmoLight(Light):
    """Representation of a Netatmo Presence camera light."""

    def __init__(self, camera_data: CameraData, camera_id: str):
        """Initialize a Netatmo Presence camera light."""
        self._camera_id = camera_id
        self._data = camera_data
        self._camera_type = self._data.camera_data.get_camera(camera_id).get("type")
        self._name = (
            f"{MANUFACTURER} {self._data.camera_data.get_camera(camera_id).get('name')}"
        )
        self._is_on = False
        self._unique_id = f"{self._camera_id}-{self._camera_type}-light"
        self._verify_ssl = True

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def device_info(self):
        """Return the device info for the sensor."""
        return {
            "identifiers": {(DOMAIN, self._camera_id)},
            "name": self._name,
            "manufacturer": MANUFACTURER,
            "model": self._camera_type,
        }

    @property
    def unique_id(self):
        """Return the unique ID for this light."""
        return self._unique_id

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Turn camera floodlight on."""
        _LOGGER.debug("Turn camera '%s' on", self._name)
        self._data.camera_data.set_state(
            camera_id=self._camera_id, floodlight="on",
        )

    def turn_off(self, **kwargs):
        """Turn camera floodlight into auto mode."""
        _LOGGER.debug("Turn camera '%s' off", self._name)
        self._data.camera_data.set_state(
            camera_id=self._camera_id, floodlight="auto",
        )

    def update(self):
        """Update the camera data."""
        self._data.update()
        if self._data.camera_data.get_light_state(self._camera_id) == "on":
            self._is_on = True
        else:
            self._is_on = False
