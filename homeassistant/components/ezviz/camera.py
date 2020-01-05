"""This component provides basic support for Ezviz IP cameras."""
import asyncio
import logging

from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from pyezviz.client import EzvizClient, PyEzvizError
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, SUPPORT_STREAM, Camera
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_CAMERAS = "cameras"
CONF_SERIAL = "serial"
CONF_DEFAULT_CAMERA_USERNAME = "admin"

DATA_FFMPEG = "ffmpeg"

CAMERAS_CONFIG = vol.Schema(
    {
        vol.Optional(CONF_USERNAME, default=CONF_DEFAULT_CAMERA_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SERIAL): cv.string,
    }
)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_CAMERAS, default={}): vol.All(),
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

        # Get cameras
        connections = ezviz_client.get_CONNECTION()
        devices = ezviz_client.get_DEVICE()

    except PyEzvizError as exp:
        _LOGGER.error(exp)
        return

    # now, let's build the HASS devices
    cameras = {}
    camera_entities = []
    for device in devices:

        device_serial = device["deviceSerial"]

        # There seem to be a bug related to localRtspPort in Ezviz API...
        local_rtsp_port = 554
        if connections[device_serial]["localRtspPort"] != 0:
            local_rtsp_port = connections[device_serial]["localRtspPort"]

        cameras[device_serial] = {
            "serial": device_serial,
            "name": device["name"],
            "device_type": device["deviceType"],
            "version": device["version"],
            "status": device["status"],
            "create_time": device["userDeviceCreateTime"],
            "category": device["deviceCategory"],
            "sub_category": device["deviceSubCategory"],
            "custom_type": device["customType"],
            "local_ip": connections[device_serial]["localIp"],
            "net_ip": connections[device_serial]["netIp"],
            "local_rtsp_port": local_rtsp_port,
            "net_type": connections[device_serial]["netType"],
            "wan_ip": connections[device_serial]["wanIp"],
        }

    # Add the cameras as devices in HASS
    for camera_serial, camera in cameras.items():

        camera_username = CONF_DEFAULT_CAMERA_USERNAME
        camera_password = ""
        camera_rtsp_stream = ""

        if camera_serial in conf_cameras:
            camera_username = conf_cameras[camera_serial]["username"]
            camera_password = conf_cameras[camera_serial]["password"]
            camera_rtsp_stream = "rtsp://{}:{}@{}:{}".format(
                camera_username,
                camera_password,
                camera["local_ip"],
                camera["local_rtsp_port"],
            )
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
        camera_entities.append(EzvizCamera(**camera))

    add_entities(camera_entities)


class EzvizCamera(Camera):
    """An implementation of a Foscam IP camera."""

    def __init__(self, **data):
        """Set up for access to the Ezviz camera images."""

        self._username = data["username"]
        self._password = data["password"]
        self._rtsp_stream = data["rtsp_stream"]

        self._serial = data["serial"]
        self._name = data["name"]
        self._type = data["device_type"]
        self._version = data["version"]
        self._status = data["status"]
        self._create_time = data["create_time"]
        self._category = data["category"]
        self._sub_category = data["sub_category"]
        self._custom_type = data["custom_type"]
        self._local_ip = data["local_ip"]
        self._net_ip = data["net_ip"]
        self._local_rtsp_port = data["local_rtsp_port"]
        self._wan_ip = data["wan_ip"]
        self._net_type = data["net_type"]

    # async def async_added_to_hass(self):
    #     self._ffmpeg = self.hass.data[DATA_FFMPEG]

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
            "type": self._type,
            "version": self._version,
            "create_time": self._create_time,
            "category": self._category,
            "sub_category": self._sub_category,
            "custom_type": self._custom_type,
            "local_ip": self._local_ip,
            "net_ip": self._net_ip,
            "local_rtsp_port": self._local_rtsp_port,
            "wan_ip": self._wan_ip,
            "net_type": self._net_type,
            "rtsp_stream": self._rtsp_stream,
            "status": self._status,
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
        return self._type

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

    def is_streaming(self):
        """Return the status of the stream from the camera."""
        return self.is_on()

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
