"""Support for Android IP Webcam."""
import asyncio
from datetime import timedelta

from pydroid_ipcam import PyDroidIPCam
import voluptuous as vol

from homeassistant.components.mjpeg.camera import CONF_MJPEG_URL, CONF_STILL_IMAGE_URL
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

ATTR_AUD_CONNS = "Audio Connections"
ATTR_HOST = "host"
ATTR_VID_CONNS = "Video Connections"

CONF_MOTION_SENSOR = "motion_sensor"

DATA_IP_WEBCAM = "android_ip_webcam"
DEFAULT_NAME = "IP Webcam"
DEFAULT_PORT = 8080
DEFAULT_TIMEOUT = 10
DOMAIN = "android_ip_webcam"

SCAN_INTERVAL = timedelta(seconds=10)
SIGNAL_UPDATE_DATA = "android_ip_webcam_update"

KEY_MAP = {
    "audio_connections": "Audio Connections",
    "adet_limit": "Audio Trigger Limit",
    "antibanding": "Anti-banding",
    "audio_only": "Audio Only",
    "battery_level": "Battery Level",
    "battery_temp": "Battery Temperature",
    "battery_voltage": "Battery Voltage",
    "coloreffect": "Color Effect",
    "exposure": "Exposure Level",
    "exposure_lock": "Exposure Lock",
    "ffc": "Front-facing Camera",
    "flashmode": "Flash Mode",
    "focus": "Focus",
    "focus_homing": "Focus Homing",
    "focus_region": "Focus Region",
    "focusmode": "Focus Mode",
    "gps_active": "GPS Active",
    "idle": "Idle",
    "ip_address": "IPv4 Address",
    "ipv6_address": "IPv6 Address",
    "ivideon_streaming": "Ivideon Streaming",
    "light": "Light Level",
    "mirror_flip": "Mirror Flip",
    "motion": "Motion",
    "motion_active": "Motion Active",
    "motion_detect": "Motion Detection",
    "motion_event": "Motion Event",
    "motion_limit": "Motion Limit",
    "night_vision": "Night Vision",
    "night_vision_average": "Night Vision Average",
    "night_vision_gain": "Night Vision Gain",
    "orientation": "Orientation",
    "overlay": "Overlay",
    "photo_size": "Photo Size",
    "pressure": "Pressure",
    "proximity": "Proximity",
    "quality": "Quality",
    "scenemode": "Scene Mode",
    "sound": "Sound",
    "sound_event": "Sound Event",
    "sound_timeout": "Sound Timeout",
    "torch": "Torch",
    "video_connections": "Video Connections",
    "video_chunk_len": "Video Chunk Length",
    "video_recording": "Video Recording",
    "video_size": "Video Size",
    "whitebalance": "White Balance",
    "whitebalance_lock": "White Balance Lock",
    "zoom": "Zoom",
}

ICON_MAP = {
    "audio_connections": "mdi:speaker",
    "battery_level": "mdi:battery",
    "battery_temp": "mdi:thermometer",
    "battery_voltage": "mdi:battery-charging-100",
    "exposure_lock": "mdi:camera",
    "ffc": "mdi:camera-front-variant",
    "focus": "mdi:image-filter-center-focus",
    "gps_active": "mdi:crosshairs-gps",
    "light": "mdi:flashlight",
    "motion": "mdi:run",
    "night_vision": "mdi:weather-night",
    "overlay": "mdi:monitor",
    "pressure": "mdi:gauge",
    "proximity": "mdi:map-marker-radius",
    "quality": "mdi:quality-high",
    "sound": "mdi:speaker",
    "sound_event": "mdi:speaker",
    "sound_timeout": "mdi:speaker",
    "torch": "mdi:white-balance-sunny",
    "video_chunk_len": "mdi:video",
    "video_connections": "mdi:eye",
    "video_recording": "mdi:record-rec",
    "whitebalance_lock": "mdi:white-balance-auto",
}

SWITCHES = [
    "exposure_lock",
    "ffc",
    "focus",
    "gps_active",
    "motion_detect",
    "night_vision",
    "overlay",
    "torch",
    "whitebalance_lock",
    "video_recording",
]

SENSORS = [
    "audio_connections",
    "battery_level",
    "battery_temp",
    "battery_voltage",
    "light",
    "motion",
    "pressure",
    "proximity",
    "sound",
    "video_connections",
]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                        vol.Required(CONF_HOST): cv.string,
                        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                        vol.Optional(
                            CONF_TIMEOUT, default=DEFAULT_TIMEOUT
                        ): cv.positive_int,
                        vol.Optional(
                            CONF_SCAN_INTERVAL, default=SCAN_INTERVAL
                        ): cv.time_period,
                        vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
                        vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
                        vol.Optional(CONF_SWITCHES): vol.All(
                            cv.ensure_list, [vol.In(SWITCHES)]
                        ),
                        vol.Optional(CONF_SENSORS): vol.All(
                            cv.ensure_list, [vol.In(SENSORS)]
                        ),
                        vol.Optional(CONF_MOTION_SENSOR): cv.boolean,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the IP Webcam component."""

    webcams = hass.data[DATA_IP_WEBCAM] = {}
    websession = async_get_clientsession(hass)

    async def async_setup_ipcamera(cam_config):
        """Set up an IP camera."""
        host = cam_config[CONF_HOST]
        username = cam_config.get(CONF_USERNAME)
        password = cam_config.get(CONF_PASSWORD)
        name = cam_config[CONF_NAME]
        interval = cam_config[CONF_SCAN_INTERVAL]
        switches = cam_config.get(CONF_SWITCHES)
        sensors = cam_config.get(CONF_SENSORS)
        motion = cam_config.get(CONF_MOTION_SENSOR)

        # Init ip webcam
        cam = PyDroidIPCam(
            hass.loop,
            websession,
            host,
            cam_config[CONF_PORT],
            username=username,
            password=password,
            timeout=cam_config[CONF_TIMEOUT],
        )

        if switches is None:
            switches = [
                setting for setting in cam.enabled_settings if setting in SWITCHES
            ]

        if sensors is None:
            sensors = [sensor for sensor in cam.enabled_sensors if sensor in SENSORS]
            sensors.extend(["audio_connections", "video_connections"])

        if motion is None:
            motion = "motion_active" in cam.enabled_sensors

        async def async_update_data(now):
            """Update data from IP camera in SCAN_INTERVAL."""
            await cam.update()
            async_dispatcher_send(hass, SIGNAL_UPDATE_DATA, host)

            async_track_point_in_utc_time(hass, async_update_data, utcnow() + interval)

        await async_update_data(None)

        # Load platforms
        webcams[host] = cam

        mjpeg_camera = {
            CONF_PLATFORM: "mjpeg",
            CONF_MJPEG_URL: cam.mjpeg_url,
            CONF_STILL_IMAGE_URL: cam.image_url,
            CONF_NAME: name,
        }
        if username and password:
            mjpeg_camera.update({CONF_USERNAME: username, CONF_PASSWORD: password})

        hass.async_create_task(
            discovery.async_load_platform(hass, "camera", "mjpeg", mjpeg_camera, config)
        )

        if sensors:
            hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    "sensor",
                    DOMAIN,
                    {CONF_NAME: name, CONF_HOST: host, CONF_SENSORS: sensors},
                    config,
                )
            )

        if switches:
            hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    "switch",
                    DOMAIN,
                    {CONF_NAME: name, CONF_HOST: host, CONF_SWITCHES: switches},
                    config,
                )
            )

        if motion:
            hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    "binary_sensor",
                    DOMAIN,
                    {CONF_HOST: host, CONF_NAME: name},
                    config,
                )
            )

    tasks = [async_setup_ipcamera(conf) for conf in config[DOMAIN]]
    if tasks:
        await asyncio.wait(tasks)

    return True


class AndroidIPCamEntity(Entity):
    """The Android device running IP Webcam."""

    def __init__(self, host, ipcam):
        """Initialize the data object."""
        self._host = host
        self._ipcam = ipcam

    async def async_added_to_hass(self):
        """Register update dispatcher."""

        @callback
        def async_ipcam_update(host):
            """Update callback."""
            if self._host != host:
                return
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE_DATA, async_ipcam_update)
        )

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def available(self):
        """Return True if entity is available."""
        return self._ipcam.available

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state_attr = {ATTR_HOST: self._host}
        if self._ipcam.status_data is None:
            return state_attr

        state_attr[ATTR_VID_CONNS] = self._ipcam.status_data.get("video_connections")
        state_attr[ATTR_AUD_CONNS] = self._ipcam.status_data.get("audio_connections")

        return state_attr
