"""Support for the Netatmo cameras."""
import logging

import pyatmo
import requests
import voluptuous as vol

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    SUPPORT_STREAM,
    Camera,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import ATTR_PSEUDO, DATA_HANDLER, DATA_PERSONS, DOMAIN, MANUFACTURER, MODELS
from .netatmo_entity_base import NetatmoBase

_LOGGER = logging.getLogger(__name__)

CONF_HOME = "home"
CONF_CAMERAS = "cameras"
CONF_QUALITY = "quality"

DEFAULT_QUALITY = "high"

VALID_QUALITIES = ["high", "medium", "low", "poor"]

_BOOL_TO_STATE = {True: STATE_ON, False: STATE_OFF}

SCHEMA_SERVICE_SETLIGHTAUTO = vol.Schema(
    {vol.Optional(ATTR_ENTITY_ID): cv.entity_domain(CAMERA_DOMAIN)}
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Netatmo camera platform."""
    if "access_camera" not in entry.data["token"]["scope"]:
        _LOGGER.info(
            "Cameras are currently not supported with this authentication method"
        )
        return

    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]

    data_class = "CameraData"

    def get_entities():
        """Retrieve Netatmo entities."""
        entities = []
        try:
            all_cameras = []
            for home in data_handler.data[data_class].cameras.values():
                for camera in home.values():
                    all_cameras.append(camera)

            for camera in all_cameras:  # camera_data.get_all_cameras():
                _LOGGER.debug("Adding camera %s %s", camera["id"], camera["name"])
                entities.append(
                    NetatmoCamera(
                        data_handler,
                        data_class,
                        camera["id"],
                        camera["type"],
                        True,
                        DEFAULT_QUALITY,
                    )
                )

            for person_id, person_data in data_handler.data[data_class].persons.items():
                hass.data[DOMAIN][DATA_PERSONS][person_id] = person_data.get(
                    ATTR_PSEUDO
                )
        except pyatmo.NoDevice:
            _LOGGER.debug("No cameras found")
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Netatmo camera platform."""
    return


class NetatmoCamera(Camera, NetatmoBase):
    """Representation of a Netatmo camera."""

    def __init__(
        self, data_handler, data_class, camera_id, camera_type, verify_ssl, quality
    ):
        """Set up for access to the Netatmo camera images."""
        Camera.__init__(self)
        NetatmoBase.__init__(self, data_handler)

        self._data_class = data_class

        self._camera_id = camera_id
        self._camera_name = self._data.get_camera(cid=camera_id).get("name")
        self._name = f"{MANUFACTURER} {self._camera_name}"
        self._camera_type = camera_type
        self._unique_id = f"{self._camera_id}-{self._camera_type}"
        self._verify_ssl = verify_ssl
        self._quality = quality
        self._vpnurl = None
        self._localurl = None
        self._status = None
        self._sd_status = None
        self._alim_status = None
        self._is_local = None

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
                _LOGGER.error("Welcome/Presence VPN URL is None")
                (self._vpnurl, self._localurl) = self._data.camera_urls(
                    cid=self._camera_id
                )
                return None
        except requests.exceptions.RequestException as error:
            _LOGGER.info("Welcome/Presence URL changed: %s", error)
            (self._vpnurl, self._localurl) = self._data.camera_urls(cid=self._camera_id)
            return None
        return response.content

    @property
    def name(self):
        """Return the name of this Netatmo camera device."""
        return self._name

    @property
    def device_info(self):
        """Return the device info for the sensor."""
        return {
            "identifiers": {(DOMAIN, self._camera_id)},
            "name": self._camera_name,
            "manufacturer": MANUFACTURER,
            "model": MODELS[self._camera_type],
        }

    @property
    def device_state_attributes(self):
        """Return the Netatmo-specific camera state attributes."""
        attr = {}
        attr["id"] = self._camera_id
        attr["status"] = self._status
        attr["sd_status"] = self._sd_status
        attr["alim_status"] = self._alim_status
        attr["is_local"] = self._is_local
        attr["vpn_url"] = self._vpnurl

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
        return MANUFACTURER

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

    @callback
    def async_update_callback(self):
        """Update the entity's state."""
        camera = self._data.get_camera(cid=self._camera_id)

        self._vpnurl, self._localurl = self._data.camera_urls(cid=self._camera_id)
        self._status = camera.get("status")
        self._sd_status = camera.get("sd_status")
        self._alim_status = camera.get("alim_status")
        self._is_local = camera.get("is_local")
        self.is_streaming = self._alim_status == "on"
