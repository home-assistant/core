"""Support for the Netatmo cameras."""
import logging

import pyatmo
import requests

from homeassistant.components.camera import Camera, SUPPORT_STREAM
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.util import Throttle

from .const import (
    AUTH,
    DOMAIN,
    MANUFAKTURER,
    DATA_PERSONS,
    ATTR_PSEUDO,
    MIN_TIME_BETWEEN_UPDATES,
    MIN_TIME_BETWEEN_EVENT_UPDATES,
)

_LOGGER = logging.getLogger(__name__)

CONF_HOME = "home"
CONF_CAMERAS = "cameras"
CONF_QUALITY = "quality"

DEFAULT_QUALITY = "high"

VALID_QUALITIES = ["high", "medium", "low", "poor"]

_BOOL_TO_STATE = {True: STATE_ON, False: STATE_OFF}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Netatmo camera platform."""

    def get_devices():
        """Retrieve Netatmo devices."""
        devices = []
        try:
            camera_data = CameraData(hass, hass.data[DOMAIN][AUTH])
            for camera_id in camera_data.get_camera_ids():
                _LOGGER.debug("Setting up camera %s", camera_id)
                camera_type = camera_data.get_camera_type(camera_id=camera_id)
                devices.append(
                    NetatmoCamera(
                        camera_data, camera_id, camera_type, True, DEFAULT_QUALITY
                    )
                )
            camera_data.get_persons()
        except pyatmo.NoDevice:
            _LOGGER.debug("No cameras found")
        return devices

    async_add_entities(await hass.async_add_executor_job(get_devices), True)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up access to Netatmo cameras."""
    return


class NetatmoCamera(Camera):
    """Representation of a Netatmo camera."""

    def __init__(self, data, camera_id, camera_type, verify_ssl, quality):
        """Set up for access to the Netatmo camera images."""
        super().__init__()
        self._data = data
        self._camera_id = camera_id
        self._name = (
            f"{MANUFAKTURER} {self._data.camera_data.cameraById(camera_id).get('name')}"
        )
        self._camera_type = camera_type
        self._unique_id = f"{self._camera_id}-{self._camera_type}"
        self._verify_ssl = verify_ssl
        self._quality = quality

        # URLs
        self._vpnurl = None
        self._localurl = None

        # Identifier
        self._id = None

        # Monitoring status
        self._status = None

        # SD Card status
        self._sd_status = None

        # Power status
        self._alim_status = None

        # Is local
        self._is_local = None

        # VPN URL
        self._vpn_url = None

        # Light mode status
        self._light_mode_status = None

    def camera_image(self):
        """Return a still image response from the camera."""
        try:
            if self._localurl:
                response = requests.get(
                    f"{self._localurl}/live/snapshot_720.jpg", timeout=10
                )
            elif self._vpnurl:
                response = requests.get(
                    f"{self._vpnurl}/live/snapshot_720.jpg",
                    timeout=10,
                    verify=self._verify_ssl,
                )
            else:
                _LOGGER.error("Welcome VPN URL is None")
                self._data.update()
                (self._vpnurl, self._localurl) = self._data.camera_data.cameraUrls(
                    cid=self._camera_id
                )
                return None
        except requests.exceptions.RequestException as error:
            _LOGGER.error("Welcome URL changed: %s", error)
            self._data.update()
            (self._vpnurl, self._localurl) = self._data.camera_data.cameraUrls(
                cid=self._camera_id
            )
            return None
        return response.content

    # Entity property overrides

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    @property
    def name(self):
        """Return the name of this Netatmo camera device."""
        return self._name

    @property
    def device_info(self):
        """Return the device info for the sensor."""
        return {
            "identifiers": {(DOMAIN, self._camera_id)},
            "name": self._name,
            "manufacturer": MANUFAKTURER,
            "model": self._camera_type,
        }

    @property
    def device_state_attributes(self):
        """Return the Netatmo-specific camera state attributes."""
        attr = {}
        attr["id"] = self._id
        attr["status"] = self._status
        attr["sd_status"] = self._sd_status
        attr["alim_status"] = self._alim_status
        attr["is_local"] = self._is_local
        attr["vpn_url"] = self._vpn_url

        if self.model == "Presence":
            attr["light_mode_status"] = self._light_mode_status

        return attr

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self._alim_status == "on")

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_STREAM

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return bool(self._status == "on")

    @property
    def brand(self):
        """Return the camera brand."""
        return MANUFAKTURER

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return bool(self._status == "on")

    @property
    def is_on(self):
        """Return true if on."""
        return self.is_streaming

    async def stream_source(self):
        """Return the stream source."""
        url = "{0}/live/files/{1}/index.m3u8"
        if self._localurl:
            return url.format(self._localurl, self._quality)
        return url.format(self._vpnurl, self._quality)

    @property
    def model(self):
        """Return the camera model."""
        if self._camera_type == "NOC":
            return "Presence"
        if self._camera_type == "NACamera":
            return "Welcome"
        return None

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._unique_id

    def update(self):
        """Update entity status."""

        # Refresh camera data
        self._data.update()

        camera = self._data.camera_data.cameraById(cid=self._camera_id)

        # URLs
        self._vpnurl, self._localurl = self._data.camera_data.cameraUrls(
            cid=self._camera_id
        )

        # Monitoring status
        self._status = camera.get("status")

        # SD Card status
        self._sd_status = camera.get("sd_status")

        # Power status
        self._alim_status = camera.get("alim_status")

        # Is local
        self._is_local = camera.get("is_local")

        # VPN URL
        self._vpn_url = camera.get("vpn_url")

        self.is_streaming = self._alim_status == "on"

        if self.model == "Presence":
            # Light mode status
            self._light_mode_status = camera.get("light_mode_status")

    # Camera method overrides

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        _LOGGER.debug("Enable motion detection of the camera '%s'", self._name)
        self._enable_motion_detection(True)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        _LOGGER.debug("Disable motion detection of the camera '%s'", self._name)
        self._enable_motion_detection(False)

    def _enable_motion_detection(self, enable):
        """Enable or disable motion detection."""
        try:
            if self._localurl:
                requests.get(
                    f"{self._localurl}/command/changestatus?status="
                    f"{_BOOL_TO_STATE.get(enable)}",
                    timeout=10,
                )
            elif self._vpnurl:
                requests.get(
                    f"{self._vpnurl}/command/changestatus?status="
                    f"{_BOOL_TO_STATE.get(enable)}",
                    timeout=10,
                    verify=self._verify_ssl,
                )
            else:
                _LOGGER.error("Welcome/Presence VPN URL is None")
                self._data.update()
                (self._vpnurl, self._localurl) = self._data.camera_data.cameraUrls(
                    cid=self._camera_id
                )
                return None
        except requests.exceptions.RequestException as error:
            _LOGGER.error("Welcome/Presence URL changed: %s", error)
            self._data.update()
            (self._vpnurl, self._localurl) = self._data.camera_data.cameraUrls(
                cid=self._camera_id
            )
            return None
        else:
            self.async_schedule_update_ha_state(True)


class CameraData:
    """Get the latest data from Netatmo."""

    def __init__(self, hass, auth):
        """Initialize the data object."""
        self._hass = hass
        self.auth = auth
        self.camera_data = None
        self.camera_ids = []
        self.module_names = []
        self.camera_type = None

    def get_camera_home_id(self, camera_id):
        """Return the home id for a given camera id."""
        for home_id in self.camera_data.cameras:
            for camera in self.camera_data.cameras[home_id].values():
                if camera["id"] == camera_id:
                    return home_id
        return None

    def get_camera_ids(self):
        """Return all camera available on the API as a list."""
        self.camera_ids = []
        self.update()
        for home_id in self.camera_data.cameras:
            for camera in self.camera_data.cameras[home_id].values():
                self.camera_ids.append(camera["id"])
        return self.camera_ids

    def get_module_names(self, camera_id):
        """Return all module available on the API as a list."""
        self.module_names = []
        self.update()
        for module in self.camera_data.modules.values():
            if camera_id == module["cam_id"]:
                self.module_names.append(module["name"])
        return self.module_names

    def get_camera_type(self, camera_id=None):
        """Return camera type for a camera, cid has preference over camera."""
        self.camera_type = self.camera_data.cameraType(cid=camera_id)
        return self.camera_type

    def get_persons(self):
        """Gather person data for webhooks."""
        for person_id, person_data in self.camera_data.persons.items():
            self._hass.data[DOMAIN][DATA_PERSONS][person_id] = person_data.get(
                ATTR_PSEUDO
            )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Call the Netatmo API to update the data."""
        self.camera_data = pyatmo.CameraData(self.auth, size=100)

    @Throttle(MIN_TIME_BETWEEN_EVENT_UPDATES)
    def update_event(self):
        """Call the Netatmo API to update the events."""
        self.camera_data.updateEvent(devicetype=self.camera_type)
