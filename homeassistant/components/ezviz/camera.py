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
DEFAULT_CAMERA_USERNAME = "admin"

DATA_FFMPEG = "ffmpeg"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_CAMERAS, default={}): dict,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Ezviz IP Cameras."""
    conf_cameras = {}
    if CONF_CAMERAS in config:
        conf_cameras = config[CONF_CAMERAS]
        _LOGGER.debug("Expecting %s cameras from config", len(conf_cameras))

    account = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    try:
        ezviz_client = EzvizClient(account, password)
        ezviz_client.login()

        # Get cameras
        connections = ezviz_client.get_CONNECTION()
        devices = ezviz_client.get_DEVICE()
        # now, let's build the HASS devices
        cameras = {}
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
        for camera_serial in cameras:
            camera = cameras[camera_serial]
            _LOGGER.debug("CAMERA: %s", camera)

            camera_username = DEFAULT_CAMERA_USERNAME
            camera_password = ""
            camera_rtsp_stream = ""

            if camera_serial in conf_cameras:
                camera_username = conf_cameras[camera_serial]["username"]
                camera_password = conf_cameras[camera_serial]["password"]
                camera_rtsp_stream = f"rtsp://{camera_username}:{camera_password}@{camera['local_ip']}:{camera['local_rtsp_port']}"
                _LOGGER.debug(
                    "Camera %s source stream: %s", camera["serial"], camera_rtsp_stream
                )

            else:
                _LOGGER.error(
                    "Found a camera (%s) but it is not configured. Please configure it if you wish to see the appropriate stream. Conf cameras: %s",
                    camera_serial,
                    conf_cameras,
                )

            async_add_entities(
                [
                    EzvizCamera(
                        hass,
                        camera_username,
                        camera_password,
                        camera_rtsp_stream,
                        camera["serial"],
                        camera["name"],
                        camera["device_type"],
                        camera["version"],
                        camera["status"],
                        camera["create_time"],
                        camera["category"],
                        camera["sub_category"],
                        camera["custom_type"],
                        camera["local_ip"],
                        camera["net_ip"],
                        camera["local_rtsp_port"],
                        camera["wan_ip"],
                        camera["net_type"],
                    )
                ]
            )
    except PyEzvizError as exp:
        _LOGGER.error(exp)
        return


class EzvizCamera(Camera):
    """An implementation of a Foscam IP camera."""

    def __init__(
        self,
        hass,
        username,
        password,
        rtsp_stream,
        serial,
        name,
        device_type,
        version,
        status,
        create_time,
        category,
        sub_category,
        custom_type,
        local_ip,
        net_ip,
        local_rtsp_port,
        wan_ip,
        net_type,
    ):
        """Initialize an Ezviz camera."""
        super().__init__()

        self._username = username
        self._password = password
        self._rtsp_stream = rtsp_stream

        self._serial = serial
        self._name = name
        self._type = device_type
        self._version = version
        self._status = status
        self._create_time = create_time
        self._category = category
        self._sub_category = sub_category
        self._custom_type = custom_type
        self._local_ip = local_ip
        self._net_ip = net_ip
        self._local_rtsp_port = local_rtsp_port
        self._wan_ip = wan_ip
        self._net_type = net_type

        self._ffmpeg = hass.data[DATA_FFMPEG]

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    @property
    def device_state_attributes(self):
        """Return the Netatmo-specific camera state attributes."""
        _LOGGER.debug("Getting new attributes from ezviz camera '%s'", self._name)

        attr = {}

        attr["serial"] = self._serial
        attr["type"] = self._type
        attr["version"] = self._version
        attr["create_time"] = self._create_time
        attr["category"] = self._category
        attr["sub_category"] = self._sub_category
        attr["custom_type"] = self._custom_type
        attr["local_ip"] = self._local_ip
        attr["net_ip"] = self._net_ip
        attr["local_rtsp_port"] = self._local_rtsp_port
        attr["wan_ip"] = self._wan_ip
        attr["net_type"] = self._net_type
        attr["rtsp_stream"] = self._rtsp_stream

        _LOGGER.debug("Attributes of '%s' = %s", self._name, attr)

        return attr

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
