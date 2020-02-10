"""This component provides basic support for Ezviz IP cameras."""
import asyncio
import logging

from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from pyezviz.camera import EzvizCamera
from pyezviz.client import EzvizClient, PyEzvizError
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, SUPPORT_STREAM, Camera
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_CAMERAS = "cameras"

DEFAULT_CAMERA_USERNAME = "admin"
DEFAULT_RTSP_PORT = "554"

DATA_FFMPEG = "ffmpeg"


EZVIZ_DATA = "ezviz"
ENTITIES = "entities"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_CAMERAS, default={}): dict,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, disc_info=None):
    """Set up the Ezviz IP Cameras."""

    conf_cameras = config[CONF_CAMERAS]

    account = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    try:
        ezviz_client = EzvizClient(account, password)
        ezviz_client.login()
        cameras = ezviz_client.load_cameras()

    except PyEzvizError as exp:
        _LOGGER.error(exp)
        return None

    # now, let's build the HASS devices
    camera_entities = []

    # Add the cameras as devices in HASS
    for camera in cameras:

        camera_username = DEFAULT_CAMERA_USERNAME
        camera_password = ""
        camera_rtsp_stream = ""
        camera_serial = camera["serial"]

        # There seem to be a bug related to localRtspPort in Ezviz API...
        local_rtsp_port = DEFAULT_RTSP_PORT
        if camera["local_rtsp_port"] and camera["local_rtsp_port"] != 0:
            local_rtsp_port = camera["local_rtsp_port"]

        if camera_serial in conf_cameras:
            camera_username = conf_cameras[camera_serial]["username"]
            camera_password = conf_cameras[camera_serial]["password"]
            camera_rtsp_stream = f"rtsp://{camera_username}:{camera_password}@{camera['local_ip']}:{local_rtsp_port}"
            _LOGGER.debug(
                "Camera %s source stream: %s", camera["serial"], camera_rtsp_stream
            )

        else:
            _LOGGER.info(
                "I found a camera (%s) but it is not configured. Please configure it if you wish to see the appropriate stream. Conf cameras: %s",
                camera_serial,
                conf_cameras,
            )

        camera["username"] = camera_username
        camera["password"] = camera_password
        camera["rtsp_stream"] = camera_rtsp_stream

        camera["ezviz_camera"] = EzvizCamera(ezviz_client, camera_serial)

        camera_entities.append(HassEzvizCamera(**camera))

    add_entities(camera_entities)


class HassEzvizCamera(Camera):
    """An implementation of a Foscam IP camera."""

    def __init__(self, **data):
        """Initialize an Ezviz camera."""
        super().__init__()

        self._username = data["username"]
        self._password = data["password"]
        self._rtsp_stream = data["rtsp_stream"]

        self._ezviz_camera = data["ezviz_camera"]
        self._serial = data["serial"]
        self._name = data["name"]
        self._status = data["status"]
        self._privacy = data["privacy"]
        self._audio = data["audio"]
        self._ir_led = data["ir_led"]
        self._state_led = data["state_led"]
        self._follow_move = data["follow_move"]
        self._alarm_notify = data["alarm_notify"]
        self._alarm_sound_mod = data["alarm_sound_mod"]
        self._encrypted = data["encrypted"]
        self._local_ip = data["local_ip"]
        self._detection_sensibility = data["detection_sensibility"]
        self._device_sub_category = data["device_sub_category"]
        self._local_rtsp_port = data["local_rtsp_port"]

        self._ffmpeg = None

    def update(self):
        """Update the camera states."""

        data = self._ezviz_camera.status()

        self._name = data["name"]
        self._status = data["status"]
        self._privacy = data["privacy"]
        self._audio = data["audio"]
        self._ir_led = data["ir_led"]
        self._state_led = data["state_led"]
        self._follow_move = data["follow_move"]
        self._alarm_notify = data["alarm_notify"]
        self._alarm_sound_mod = data["alarm_sound_mod"]
        self._encrypted = data["encrypted"]
        self._local_ip = data["local_ip"]
        self._detection_sensibility = data["detection_sensibility"]
        self._device_sub_category = data["device_sub_category"]
        self._local_rtsp_port = data["local_rtsp_port"]

    async def async_added_to_hass(self):
        """Subscribe to ffmpeg and add camera to list."""
        self._ffmpeg = self.hass.data[DATA_FFMPEG]
        entities = self.hass.data.setdefault(EZVIZ_DATA, {}).setdefault(ENTITIES, [])
        entities.append(self)

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    @property
    def device_state_attributes(self):
        """Return the Ezviz-specific camera state attributes."""
        return {
            "serial": self._serial,
            "name": self._name,
            "status": self._status,
            "device_sub_category": self._device_sub_category,
            "privacy": self._privacy,
            "audio": self._audio,
            "ir_led": self._ir_led,
            "state_led": self._state_led,
            "follow_move": self._follow_move,
            "alarm_notify": self._alarm_notify,
            "alarm_sound_mod": self._alarm_sound_mod,
            "encrypted": self._encrypted,
            "local_ip": self._local_ip,
            "detection_sensibility": self._detection_sensibility,
        }

    @property
    def available(self):
        """Return True if entity is available."""
        return self._status

    @property
    def brand(self):
        """Return the camera brand."""
        return "Ezviz"

    @property
    def supported_features(self):
        """Return supported features."""
        if self._rtsp_stream:
            return SUPPORT_STREAM
        return 0

    @property
    def model(self):
        """Return the camera model."""
        return self._device_sub_category

    @property
    def is_on(self):
        """Return true if on."""
        return self._status

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    async def async_camera_image(self):
        """Return a frame from the camera stream."""
        ffmpeg = ImageFrame(self._ffmpeg.binary, loop=self.hass.loop)

        image = await asyncio.shield(
            ffmpeg.get_image(self._rtsp_stream, output_format=IMAGE_JPEG,)
        )
        return image

    async def stream_source(self):
        """Return the stream source."""
        if self._local_rtsp_port:
            rtsp_stream_source = "rtsp://{}:{}@{}:{}".format(
                self._username, self._password, self._local_ip, self._local_rtsp_port
            )
            _LOGGER.debug(
                "Camera %s source stream: %s", self._serial, rtsp_stream_source
            )
            self._rtsp_stream = rtsp_stream_source
            return rtsp_stream_source
        return None
