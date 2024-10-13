"""Support for Ubiquiti's UVC cameras."""

from __future__ import annotations

from datetime import datetime
import logging
import re
from typing import Any, cast

from uvcclient import camera as uvc_camera, nvr
from uvcclient.camera import UVCCameraClient
from uvcclient.nvr import UVCRemote
import voluptuous as vol

from homeassistant.components.camera import (
    PLATFORM_SCHEMA as CAMERA_PLATFORM_SCHEMA,
    Camera,
    CameraEntityFeature,
)
from homeassistant.const import CONF_PASSWORD, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.dt import utc_from_timestamp

_LOGGER = logging.getLogger(__name__)

CONF_NVR = "nvr"
CONF_KEY = "key"

DEFAULT_PASSWORD = "ubnt"
DEFAULT_PORT = 7080
DEFAULT_SSL = False

PLATFORM_SCHEMA = CAMERA_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NVR): cv.string,
        vol.Required(CONF_KEY): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Discover cameras on a Unifi NVR."""
    addr = config[CONF_NVR]
    key = config[CONF_KEY]
    password = config[CONF_PASSWORD]
    port = config[CONF_PORT]
    ssl = config[CONF_SSL]

    try:
        nvrconn = nvr.UVCRemote(addr, port, key, ssl=ssl)
        # Exceptions may be raised in all method calls to the nvr library.
        cameras = nvrconn.index()

        identifier = nvrconn.camera_identifier
        # Filter out airCam models, which are not supported in the latest
        # version of UnifiVideo and which are EOL by Ubiquiti
        cameras = [
            camera
            for camera in cameras
            if "airCam" not in nvrconn.get_camera(camera[identifier])["model"]
        ]
    except nvr.NotAuthorized:
        _LOGGER.error("Authorization failure while connecting to NVR")
        return
    except nvr.NvrError as ex:
        _LOGGER.error("NVR refuses to talk to me: %s", str(ex))
        raise PlatformNotReady from ex

    add_entities(
        (
            UnifiVideoCamera(nvrconn, camera[identifier], camera["name"], password)
            for camera in cameras
        ),
        True,
    )


class UnifiVideoCamera(Camera):
    """A Ubiquiti Unifi Video Camera."""

    _attr_should_poll = True  # Cameras default to False
    _attr_brand = "Ubiquiti"
    _attr_is_streaming = False
    _caminfo: dict[str, Any]

    def __init__(self, camera: UVCRemote, uuid: str, name: str, password: str) -> None:
        """Initialize an Unifi camera."""
        super().__init__()
        self._nvr = camera
        self._uuid = self._attr_unique_id = uuid
        self._attr_name = name
        self._password = password
        self._connect_addr: str | None = None
        self._camera: UVCCameraClient | None = None

    @property
    def supported_features(self) -> CameraEntityFeature:
        """Return supported features."""
        channels = self._caminfo["channels"]
        for channel in channels:
            if channel["isRtspEnabled"]:
                return CameraEntityFeature.STREAM

        return CameraEntityFeature(0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the camera state attributes."""
        attr = {}
        if self.motion_detection_enabled:
            attr["last_recording_start_time"] = timestamp_ms_to_date(
                self._caminfo["lastRecordingStartTime"]
            )
        return attr

    @property
    def is_recording(self) -> bool:
        """Return true if the camera is recording."""
        recording_state = "DISABLED"
        if "recordingIndicator" in self._caminfo:
            recording_state = self._caminfo["recordingIndicator"]

        return self._caminfo["recordingSettings"][
            "fullTimeRecordEnabled"
        ] or recording_state in ("MOTION_INPROGRESS", "MOTION_FINISHED")

    @property
    def motion_detection_enabled(self) -> bool:
        """Camera Motion Detection Status."""
        return bool(self._caminfo["recordingSettings"]["motionRecordEnabled"])

    @property
    def model(self) -> str:
        """Return the model of this camera."""
        return cast(str, self._caminfo["model"])

    def _login(self) -> bool:
        """Login to the camera."""
        caminfo = self._caminfo
        if self._connect_addr:
            addrs = [self._connect_addr]
        else:
            addrs = [caminfo["host"], caminfo["internalHost"]]

        client_cls: type[uvc_camera.UVCCameraClient]
        if self._nvr.server_version >= (3, 2, 0):
            client_cls = uvc_camera.UVCCameraClientV320
        else:
            client_cls = uvc_camera.UVCCameraClient

        if caminfo["username"] is None:
            caminfo["username"] = "ubnt"

        assert isinstance(caminfo["username"], str)

        camera = None
        for addr in addrs:
            try:
                camera = client_cls(addr, caminfo["username"], self._password)
                camera.login()
                _LOGGER.debug("Logged into UVC camera %s via %s", self._attr_name, addr)
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
            return False

        self._camera = camera
        self._caminfo = caminfo
        return True

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the image of this camera."""
        if not self._camera and not self._login():
            return None

        def _get_image(retry: bool = True) -> bytes | None:
            assert self._camera is not None
            try:
                return self._camera.get_snapshot()
            except uvc_camera.CameraConnectError:
                _LOGGER.error("Unable to contact camera")
                return None
            except uvc_camera.CameraAuthError:
                if retry:
                    self._login()
                    return _get_image(retry=False)
                _LOGGER.error("Unable to log into camera, unable to get snapshot")
                raise

        return _get_image()

    def set_motion_detection(self, mode: bool) -> None:
        """Set motion detection on or off."""
        set_mode = "motion" if mode is True else "none"

        try:
            self._nvr.set_recordmode(self._uuid, set_mode)
        except nvr.NvrError as err:
            _LOGGER.error("Unable to set recordmode to %s", set_mode)
            _LOGGER.debug(err)

    def enable_motion_detection(self) -> None:
        """Enable motion detection in camera."""
        self.set_motion_detection(True)

    def disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        self.set_motion_detection(False)

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        for channel in self._caminfo["channels"]:
            if channel["isRtspEnabled"]:
                return cast(
                    str,
                    next(
                        (
                            uri
                            for i, uri in enumerate(channel["rtspUris"])
                            if re.search(self._nvr._host, uri)  # noqa: SLF001
                        )
                    ),
                )

        return None

    def update(self) -> None:
        """Update the info."""
        self._caminfo = self._nvr.get_camera(self._uuid)


def timestamp_ms_to_date(epoch_ms: int) -> datetime | None:
    """Convert millisecond timestamp to datetime."""
    if epoch_ms:
        return utc_from_timestamp(epoch_ms / 1000)
    return None
