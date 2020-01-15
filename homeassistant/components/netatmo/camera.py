"""Support for the Netatmo cameras."""
import logging

from pyatmo import NoDevice
import requests
import voluptuous as vol

from homeassistant.components.camera import (
    CAMERA_SERVICE_SCHEMA,
    PLATFORM_SCHEMA,
    SUPPORT_STREAM,
    Camera,
)
from homeassistant.const import CONF_VERIFY_SSL, STATE_OFF, STATE_ON
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from . import CameraData
from .const import DATA_NETATMO_AUTH, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_HOME = "home"
CONF_CAMERAS = "cameras"
CONF_QUALITY = "quality"

DEFAULT_QUALITY = "high"

VALID_QUALITIES = ["high", "medium", "low", "poor"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_HOME): cv.string,
        vol.Optional(CONF_CAMERAS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_QUALITY, default=DEFAULT_QUALITY): vol.All(
            cv.string, vol.In(VALID_QUALITIES)
        ),
    }
)

_BOOL_TO_STATE = {True: STATE_ON, False: STATE_OFF}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up access to Netatmo cameras."""
    home = config.get(CONF_HOME)
    verify_ssl = config.get(CONF_VERIFY_SSL, True)
    quality = config.get(CONF_QUALITY, DEFAULT_QUALITY)

    auth = hass.data[DATA_NETATMO_AUTH]

    try:
        data = CameraData(hass, auth, home)
        for camera_name in data.get_camera_names():
            camera_type = data.get_camera_type(camera=camera_name, home=home)
            if CONF_CAMERAS in config:
                if (
                    config[CONF_CAMERAS] != []
                    and camera_name not in config[CONF_CAMERAS]
                ):
                    continue
            add_entities(
                [
                    NetatmoCamera(
                        data, camera_name, home, camera_type, verify_ssl, quality
                    )
                ]
            )
        data.get_persons()
    except NoDevice:
        return None

    async def async_service_handler(call):
        """Handle service call."""
        _LOGGER.debug(
            "Service handler invoked with service=%s and data=%s",
            call.service,
            call.data,
        )
        service = call.service
        entity_id = call.data["entity_id"][0]
        async_dispatcher_send(hass, f"{service}_{entity_id}")

    hass.services.async_register(
        DOMAIN, "set_light_auto", async_service_handler, CAMERA_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_light_on", async_service_handler, CAMERA_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_light_off", async_service_handler, CAMERA_SERVICE_SCHEMA
    )


class NetatmoCamera(Camera):
    """Representation of the images published from a Netatmo camera."""

    def __init__(self, data, camera_name, home, camera_type, verify_ssl, quality):
        """Set up for access to the Netatmo camera images."""
        super().__init__()
        self._data = data
        self._camera_name = camera_name
        self._home = home
        if home:
            self._name = f"{home} / {camera_name}"
        else:
            self._name = camera_name
        self._cameratype = camera_type
        self._verify_ssl = verify_ssl
        self._quality = quality

        # URLs.
        self._vpnurl = None
        self._localurl = None

        # Identifier
        self._id = None

        # Monitoring status.
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
                    camera=self._camera_name
                )
                return None
        except requests.exceptions.RequestException as error:
            _LOGGER.error("Welcome URL changed: %s", error)
            self._data.update()
            (self._vpnurl, self._localurl) = self._data.camera_data.cameraUrls(
                camera=self._camera_name
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
    def device_state_attributes(self):
        """Return the Netatmo-specific camera state attributes."""

        _LOGGER.debug("Getting new attributes from camera netatmo '%s'", self._name)

        attr = {}
        attr["id"] = self._id
        attr["status"] = self._status
        attr["sd_status"] = self._sd_status
        attr["alim_status"] = self._alim_status
        attr["is_local"] = self._is_local
        attr["vpn_url"] = self._vpn_url

        if self.model == "Presence":
            attr["light_mode_status"] = self._light_mode_status

        _LOGGER.debug("Attributes of '%s' = %s", self._name, attr)

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
        return "Netatmo"

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
        if self._cameratype == "NOC":
            return "Presence"
        if self._cameratype == "NACamera":
            return "Welcome"
        return None

    # Other Entity method overrides

    async def async_added_to_hass(self):
        """Subscribe to signals and add camera to list."""
        _LOGGER.debug("Registering services for entity_id=%s", self.entity_id)
        async_dispatcher_connect(
            self.hass, f"set_light_auto_{self.entity_id}", self.set_light_auto
        )
        async_dispatcher_connect(
            self.hass, f"set_light_on_{self.entity_id}", self.set_light_on
        )
        async_dispatcher_connect(
            self.hass, f"set_light_off_{self.entity_id}", self.set_light_off
        )

    def update(self):
        """Update entity status."""

        _LOGGER.debug("Updating camera netatmo '%s'", self._name)

        # Refresh camera data.
        self._data.update()

        # URLs.
        self._vpnurl, self._localurl = self._data.camera_data.cameraUrls(
            camera=self._camera_name
        )

        # Identifier
        self._id = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
        )["id"]

        # Monitoring status.
        self._status = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
        )["status"]

        _LOGGER.debug("Status of '%s' = %s", self._name, self._status)

        # SD Card status
        self._sd_status = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
        )["sd_status"]

        # Power status
        self._alim_status = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
        )["alim_status"]

        # Is local
        self._is_local = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
        )["is_local"]

        # VPN URL
        self._vpn_url = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
        )["vpn_url"]

        self.is_streaming = self._alim_status == "on"

        if self.model == "Presence":
            # Light mode status
            self._light_mode_status = self._data.camera_data.cameraByName(
                camera=self._camera_name, home=self._home
            )["light_mode_status"]

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
                    f"{self._localurl}/command/changestatus?status={_BOOL_TO_STATE.get(enable)}",
                    timeout=10,
                )
            elif self._vpnurl:
                requests.get(
                    f"{self._vpnurl}/command/changestatus?status={_BOOL_TO_STATE.get(enable)}",
                    timeout=10,
                    verify=self._verify_ssl,
                )
            else:
                _LOGGER.error("Welcome/Presence VPN URL is None")
                self._data.update()
                (self._vpnurl, self._localurl) = self._data.camera_data.cameraUrls(
                    camera=self._camera_name
                )
                return None
        except requests.exceptions.RequestException as error:
            _LOGGER.error("Welcome/Presence URL changed: %s", error)
            self._data.update()
            (self._vpnurl, self._localurl) = self._data.camera_data.cameraUrls(
                camera=self._camera_name
            )
            return None
        else:
            self.async_schedule_update_ha_state(True)

    # Netatmo Presence specific camera method.

    def set_light_auto(self):
        """Set flood light in automatic mode."""
        _LOGGER.debug(
            "Set the flood light in automatic mode for the camera '%s'", self._name
        )
        self._set_light_mode("auto")

    def set_light_on(self):
        """Set flood light on."""
        _LOGGER.debug("Set the flood light on for the camera '%s'", self._name)
        self._set_light_mode("on")

    def set_light_off(self):
        """Set flood light off."""
        _LOGGER.debug("Set the flood light off for the camera '%s'", self._name)
        self._set_light_mode("off")

    def _set_light_mode(self, mode):
        """Set light mode ('auto', 'on', 'off')."""
        if self.model == "Presence":
            try:
                config = f'{{"mode":"{mode}"}}'
                if self._localurl:
                    requests.get(
                        f"{self._localurl}/command/floodlight_set_config?config={config}",
                        timeout=10,
                    )
                elif self._vpnurl:
                    requests.get(
                        f"{self._vpnurl}/command/floodlight_set_config?config={config}",
                        timeout=10,
                        verify=self._verify_ssl,
                    )
                else:
                    _LOGGER.error("Presence VPN URL is None")
                    self._data.update()
                    (self._vpnurl, self._localurl) = self._data.camera_data.cameraUrls(
                        camera=self._camera_name
                    )
                    return None
            except requests.exceptions.RequestException as error:
                _LOGGER.error("Presence URL changed: %s", error)
                self._data.update()
                (self._vpnurl, self._localurl) = self._data.camera_data.cameraUrls(
                    camera=self._camera_name
                )
                return None
            else:
                self.async_schedule_update_ha_state(True)
        else:
            _LOGGER.error("Unsupported camera model for light mode")
