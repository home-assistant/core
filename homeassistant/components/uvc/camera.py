"""Support for Ubiquiti's UVC cameras."""
import logging
import re

import requests
from uvcclient import camera as uvc_camera, nvr
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, SUPPORT_STREAM, Camera
from homeassistant.const import CONF_PORT, CONF_SSL
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_NVR = "nvr"
CONF_KEY = "key"
CONF_PASSWORD = "password"

DEFAULT_PASSWORD = "ubnt"
DEFAULT_PORT = 7080
DEFAULT_SSL = False

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NVR): cv.string,
        vol.Required(CONF_KEY): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Discover cameras on a Unifi NVR."""
    addr = config[CONF_NVR]
    key = config[CONF_KEY]
    password = config[CONF_PASSWORD]
    port = config[CONF_PORT]
    ssl = config[CONF_SSL]

    try:
        # Exceptions may be raised in all method calls to the nvr library.
        nvrconn = nvr.UVCRemote(addr, port, key, ssl=ssl)
        cameras = nvrconn.index()

        identifier = "id" if nvrconn.server_version >= (3, 2, 0) else "uuid"
        # Filter out airCam models, which are not supported in the latest
        # version of UnifiVideo and which are EOL by Ubiquiti
        cameras = [
            camera
            for camera in cameras
            if "airCam" not in nvrconn.get_camera(camera[identifier])["model"]
        ]
    except nvr.NotAuthorized:
        _LOGGER.error("Authorization failure while connecting to NVR")
        return False
    except nvr.NvrError as ex:
        _LOGGER.error("NVR refuses to talk to me: %s", str(ex))
        raise PlatformNotReady from ex
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error("Unable to connect to NVR: %s", str(ex))
        raise PlatformNotReady from ex

    add_entities(
        [
            UnifiVideoCamera(nvrconn, camera[identifier], camera["name"], password)
            for camera in cameras
        ],
        True,
    )
    return True


class UnifiVideoCamera(Camera):
    """A Ubiquiti Unifi Video Camera."""

    def __init__(self, camera, uuid, name, password):
        """Initialize an Unifi camera."""
        super().__init__()
        self._nvr = camera
        self._uuid = uuid
        self._name = name
        self._password = password
        self.is_streaming = False
        self._connect_addr = None
        self._camera = None
        self._motion_status = False
        self._caminfo = None

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def should_poll(self):
        """If this entity should be polled."""
        return True

    @property
    def supported_features(self):
        """Return supported features."""
        channels = self._caminfo["channels"]
        for channel in channels:
            if channel["isRtspEnabled"]:
                return SUPPORT_STREAM

        return 0

    @property
    def is_recording(self):
        """Return true if the camera is recording."""
        return self._caminfo["recordingSettings"]["fullTimeRecordEnabled"]

    @property
    def motion_detection_enabled(self):
        """Camera Motion Detection Status."""
        return self._caminfo["recordingSettings"]["motionRecordEnabled"]

    @property
    def brand(self):
        """Return the brand of this camera."""
        return "Ubiquiti"

    @property
    def model(self):
        """Return the model of this camera."""
        return self._caminfo["model"]

    def _login(self):
        """Login to the camera."""
        caminfo = self._caminfo
        if self._connect_addr:
            addrs = [self._connect_addr]
        else:
            addrs = [caminfo["host"], caminfo["internalHost"]]

        if self._nvr.server_version >= (3, 2, 0):
            client_cls = uvc_camera.UVCCameraClientV320
        else:
            client_cls = uvc_camera.UVCCameraClient

        if caminfo["username"] is None:
            caminfo["username"] = "ubnt"

        camera = None
        for addr in addrs:
            try:
                camera = client_cls(addr, caminfo["username"], self._password)
                camera.login()
                _LOGGER.debug(
                    "Logged into UVC camera %(name)s via %(addr)s",
                    {"name": self._name, "addr": addr},
                )
                self._connect_addr = addr
                break
            except OSError:
                pass
            except uvc_camera.CameraConnectError:
                pass
            except uvc_camera.CameraAuthError:
                pass
        if not self._connect_addr:
            _LOGGER.error("Unable to login to camera")
            return None

        self._camera = camera
        self._caminfo = caminfo
        return True

    def camera_image(self):
        """Return the image of this camera."""

        if not self._camera:
            if not self._login():
                return

        def _get_image(retry=True):
            try:
                return self._camera.get_snapshot()
            except uvc_camera.CameraConnectError:
                _LOGGER.error("Unable to contact camera")
            except uvc_camera.CameraAuthError:
                if retry:
                    self._login()
                    return _get_image(retry=False)
                _LOGGER.error("Unable to log into camera, unable to get snapshot")
                raise

        return _get_image()

    def set_motion_detection(self, mode):
        """Set motion detection on or off."""
        set_mode = "motion" if mode is True else "none"

        try:
            self._nvr.set_recordmode(self._uuid, set_mode)
            self._motion_status = mode
        except nvr.NvrError as err:
            _LOGGER.error("Unable to set recordmode to %s", set_mode)
            _LOGGER.debug(err)

    def enable_motion_detection(self):
        """Enable motion detection in camera."""
        self.set_motion_detection(True)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        self.set_motion_detection(False)

    async def stream_source(self):
        """Return the source of the stream."""
        for channel in self._caminfo["channels"]:
            if channel["isRtspEnabled"]:
                uri = next(
                    (
                        uri
                        for i, uri in enumerate(channel["rtspUris"])
                        # pylint: disable=protected-access
                        if re.search(self._nvr._host, uri)
                        # pylint: enable=protected-access
                    )
                )
                return uri

        return None

    def update(self):
        """Update the info."""
        self._caminfo = self._nvr.get_camera(self._uuid)
