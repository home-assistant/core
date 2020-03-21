"""This component provides basic support for Ezviz IP cameras."""
import asyncio
import logging

from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from pyezviz.camera import EzvizCamera
from pyezviz.client import EzvizClient, PyEzvizError
import voluptuous as vol

from homeassistant.components.camera import (
    CAMERA_SERVICE_SCHEMA,
    PLATFORM_SCHEMA,
    SUPPORT_STREAM,
    Camera,
)
from homeassistant.components.camera.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.service import async_extract_entity_ids

_LOGGER = logging.getLogger(__name__)

CONF_CAMERAS = "cameras"
CONF_SERIAL = "serial"

DEFAULT_CAMERA_USERNAME = "admin"
DEFAULT_RTSP_PORT = "554"

DATA_FFMPEG = "ffmpeg"

ATTR_DIRECTION = "direction"
ATTR_SPEED = "speed"
DEFAULT_SPEED = 5

ATTR_ENABLE = "enable"
ATTR_SWITCH = "switch"
AUDIO = "audio"
PRIVACY = "privacy"
STATE = "state"
FOLLOW_MOVE = "follow_move"

DIR_UP = "up"
DIR_DOWN = "down"
DIR_LEFT = "left"
DIR_RIGHT = "right"

SERVICE_PTZ = "ezviz_ptz"
EZVIZ_DATA = "ezviz"
ENTITIES = "entities"

CAMERA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CAMERAS, default={}): {cv.string: CAMERA_SCHEMA},
    }
)

SERVICE_PTZ_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_DIRECTION): vol.In([DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT]),
        vol.Optional(ATTR_SPEED, default=DEFAULT_SPEED): cv.positive_int,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ezviz IP Cameras."""

    async def async_handle_ptz(service):
        """Handle PTZ service call."""
        direction = service.data.get(ATTR_DIRECTION, None)
        speed = service.data.get(ATTR_SPEED, None)

        all_cameras = hass.data[EZVIZ_DATA][ENTITIES]
        entity_ids = await async_extract_entity_ids(hass, service)
        target_cameras = []
        if not entity_ids:
            target_cameras = all_cameras
        else:
            target_cameras = [
                camera for camera in all_cameras if camera.entity_id in entity_ids
            ]
        for camera in target_cameras:
            await camera.async_perform_ptz(direction, speed)

    async def async_switch_handler(call):
        """Handle switch call."""
        service = call.service
        entity_id = call.data["entity_id"][0]
        async_dispatcher_send(hass, f"{service}_{entity_id}")

    hass.services.async_register(
        DOMAIN, SERVICE_PTZ, async_handle_ptz, schema=SERVICE_PTZ_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, "ezviz_switch_ir_on", async_switch_handler, CAMERA_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "ezviz_switch_ir_off", async_switch_handler, CAMERA_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "ezviz_switch_audio_on", async_switch_handler, CAMERA_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "ezviz_switch_audio_off", async_switch_handler, CAMERA_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "ezviz_switch_privacy_on", async_switch_handler, CAMERA_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "ezviz_switch_privacy_off", async_switch_handler, CAMERA_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "ezviz_switch_state_on", async_switch_handler, CAMERA_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "ezviz_switch_state_off", async_switch_handler, CAMERA_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        "ezviz_switch_follow_move_on",
        async_switch_handler,
        CAMERA_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "ezviz_switch_follow_move_off",
        async_switch_handler,
        CAMERA_SERVICE_SCHEMA,
    )

    conf_cameras = config[CONF_CAMERAS]

    account = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    try:
        ezviz_client = EzvizClient(account, password)
        ezviz_client.login()
        cameras = ezviz_client.load_cameras()

    except PyEzvizError as exp:
        _LOGGER.error(exp)
        return

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
            camera_username = conf_cameras[camera_serial][CONF_USERNAME]
            camera_password = conf_cameras[camera_serial][CONF_PASSWORD]
            camera_rtsp_stream = f"rtsp://{camera_username}:{camera_password}@{camera['local_ip']}:{local_rtsp_port}"
            _LOGGER.debug(
                "Camera %s source stream: %s", camera["serial"], camera_rtsp_stream
            )

        else:
            _LOGGER.info(
                "Found camera with serial %s without configuration. Add it to configuration.yaml to see the camera stream",
                camera_serial,
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

        self._username = data.get("username")
        self._password = data.get("password")
        self._rtsp_stream = data.get("rtsp_stream")
        self._ezviz_camera = data.get("ezviz_camera")

        self._serial = data.get("serial")
        self._name = data.get("name")
        self._status = data.get("status", 0)
        self._privacy = data.get("privacy")
        self._audio = data.get("audio")
        self._ir_led = data.get("ir_led", 0)
        self._state_led = data.get("state_led", 0)
        self._follow_move = data.get("follow_move", 0)
        self._alarm_notify = data.get("alarm_notify", 0)
        self._alarm_sound_mod = data.get("alarm_sound_mod", 0)
        self._encrypted = data.get("encrypted", 0)
        self._local_ip = data.get("local_ip")
        self._detection_sensibility = data.get("detection_sensibility")
        self._device_sub_category = data.get("device_sub_category")
        self._local_rtsp_port = data.get("local_rtsp_port", 554)

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
        _LOGGER.debug("Registering services for entity_id=%s", self.entity_id)
        async_dispatcher_connect(
            self.hass, f"ezviz_switch_ir_on_{self.entity_id}", self.switch_ir_on
        )
        async_dispatcher_connect(
            self.hass, f"ezviz_switch_ir_off_{self.entity_id}", self.switch_ir_off
        )
        async_dispatcher_connect(
            self.hass, f"ezviz_switch_audio_on_{self.entity_id}", self.switch_audio_on
        )
        async_dispatcher_connect(
            self.hass, f"ezviz_switch_audio_off_{self.entity_id}", self.switch_audio_off
        )
        async_dispatcher_connect(
            self.hass,
            f"ezviz_switch_privacy_on_{self.entity_id}",
            self.switch_privacy_on,
        )
        async_dispatcher_connect(
            self.hass,
            f"ezviz_switch_privacy_off_{self.entity_id}",
            self.switch_privacy_off,
        )
        async_dispatcher_connect(
            self.hass, f"ezviz_switch_state_on_{self.entity_id}", self.switch_state_on
        )
        async_dispatcher_connect(
            self.hass, f"ezviz_switch_state_off_{self.entity_id}", self.switch_state_off
        )
        async_dispatcher_connect(
            self.hass,
            f"ezviz_switch_follow_move_on_{self.entity_id}",
            self.switch_follow_move_on,
        )
        async_dispatcher_connect(
            self.hass,
            f"ezviz_switch_follow_move_off_{self.entity_id}",
            self.switch_follow_move_off,
        )

    async def async_perform_ptz(self, direction, speed):
        """Perform a PTZ action on the camera."""
        await self.hass.async_add_executor_job(
            self._ezviz_camera.move, direction, speed
        )

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
            # if privacy == true, the device closed the lid or did a 180° tilt
            "privacy": self._privacy,
            # is the camera listening ?
            "audio": self._audio,
            # infrared led on ?
            "ir_led": self._ir_led,
            # state led on  ?
            "state_led": self._state_led,
            # if true, the camera will move automatically to follow movements
            "follow_move": self._follow_move,
            # if true, if some movement is detected, the app is notified
            "alarm_notify": self._alarm_notify,
            # if true, if some movement is detected, the camera makes some sound
            "alarm_sound_mod": self._alarm_sound_mod,
            # are the camera's stored videos/images encrypted?
            "encrypted": self._encrypted,
            # camera's local ip on local network
            "local_ip": self._local_ip,
            # from 1 to 9, the higher is the sensibility, the more it will detect small movements
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

    def switch_audio_on(self):
        """Switch audio on."""
        self._switch("audio", 1)

    def switch_audio_off(self):
        """Switch audio on."""
        self._switch("audio", 0)

    def switch_ir_on(self):
        """Switch IR on."""
        self._switch("ir", 1)

    def switch_ir_off(self):
        """Switch IR on."""
        self._switch("ir", 0)

    def switch_privacy_on(self):
        """Switch privacy on."""
        self._switch("privacy", 1)

    def switch_privacy_off(self):
        """Switch privacy on."""
        self._switch("privacy", 0)

    def switch_state_on(self):
        """Switch state on."""
        self._switch("state", 1)

    def switch_state_off(self):
        """Switch state on."""
        self._switch("state", 0)

    def switch_follow_move_on(self):
        """Switch follow_move on."""
        self._switch("follow_move", 1)

    def switch_follow_move_off(self):
        """Switch follow_move on."""
        self._switch("follow_move", 0)

    def _switch(self, switch, enable):
        """Switch switch named switch to enable state."""
        _LOGGER.debug(
            "Switch %s for the camera %s to state: %s", switch, self._name, enable
        )

        if switch == "ir":
            self._ezviz_camera.switch_device_ir_led(enable)
        elif switch == "state":
            self._ezviz_camera.switch_device_state_led(enable)
        elif switch == "audio":
            self._ezviz_camera.switch_device_audio(enable)
        elif switch == "privacy":
            self._ezviz_camera.switch_privacy_mode(enable)
        elif switch == "follow_move":
            self._ezviz_camera.switch_follow_move(enable)
        else:
            return None
        return True
