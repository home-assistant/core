"""Support for Vivotek IP Cameras."""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any, TypedDict

from libpyvivotek import VivotekCamera
import voluptuous as vol

from homeassistant.components.camera import (
    PLATFORM_SCHEMA as CAMERA_PLATFORM_SCHEMA,
    Camera,
    CameraEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_FRAMERATE, CONF_SECURITY_LEVEL, CONF_STREAM_PATH

_LOGGER = logging.getLogger(__name__)

DEFAULT_CAMERA_BRAND = "VIVOTEK"
DEFAULT_NAME = "VIVOTEK Camera"
DEFAULT_EVENT_0_KEY = "event_i0_enable"
DEFAULT_SECURITY_LEVEL = "admin"
DEFAULT_STREAM_SOURCE = "live.sdp"


class VivotekCameraConf(TypedDict):
    """Vivotek Camera configuration type."""

    authentication: str
    ip_address: str
    password: str
    port: int
    security_level: str
    ssl: bool
    username: str
    verify_ssl: bool


PLATFORM_SCHEMA = CAMERA_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_FRAMERATE, default=2): cv.positive_int,
        vol.Optional(CONF_SECURITY_LEVEL, default=DEFAULT_SECURITY_LEVEL): cv.string,
        vol.Optional(CONF_STREAM_PATH, default=DEFAULT_STREAM_SOURCE): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the component from a config entry."""
    config = entry.data
    creds = f"{config[CONF_USERNAME]}:{config[CONF_PASSWORD]}"
    cam = VivotekCamera(
        host=config[CONF_IP_ADDRESS],
        port=(443 if config[CONF_SSL] else 80),
        verify_ssl=config[CONF_VERIFY_SSL],
        usr=config[CONF_USERNAME],
        pwd=config[CONF_PASSWORD],
        digest_auth=config[CONF_AUTHENTICATION] == HTTP_DIGEST_AUTHENTICATION,
        sec_lvl=config[CONF_SECURITY_LEVEL],
    )
    stream_source = (
        f"rtsp://{creds}@{config[CONF_IP_ADDRESS]}:554/{config[CONF_STREAM_PATH]}"
    )

    try:
        # Test connection
        mac = await hass.async_add_executor_job(cam.get_mac)
        assert len(mac) > 0
    except Exception:
        _LOGGER.exception("Unexpected exception during setup")
        return

    async_add_entities([VivotekCam(config, cam, stream_source)])


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a Vivotek IP Camera."""
    creds = f"{config[CONF_USERNAME]}:{config[CONF_PASSWORD]}"
    cam = VivotekCamera(
        host=config[CONF_IP_ADDRESS],
        port=(443 if config[CONF_SSL] else 80),
        verify_ssl=config[CONF_VERIFY_SSL],
        usr=config[CONF_USERNAME],
        pwd=config[CONF_PASSWORD],
        digest_auth=config[CONF_AUTHENTICATION] == HTTP_DIGEST_AUTHENTICATION,
        sec_lvl=config[CONF_SECURITY_LEVEL],
    )
    stream_source = (
        f"rtsp://{creds}@{config[CONF_IP_ADDRESS]}:554/{config[CONF_STREAM_PATH]}"
    )
    add_entities([VivotekCam(config, cam, stream_source)], True)


async def async_test_config(
    hass: HomeAssistant,
    data: dict[str, Any] | MappingProxyType[str, Any] | VivotekCameraConf,
) -> None:
    """Test if the provided configuration is valid."""
    cam = VivotekCamera(
        host=data[CONF_IP_ADDRESS],
        port=data[CONF_PORT],
        verify_ssl=data[CONF_VERIFY_SSL],
        usr=data[CONF_USERNAME],
        pwd=data[CONF_PASSWORD],
        digest_auth=(data[CONF_AUTHENTICATION] == HTTP_DIGEST_AUTHENTICATION),
        sec_lvl=data[CONF_SECURITY_LEVEL],
    )
    mac = await hass.async_add_executor_job(cam.get_mac)
    assert len(mac) > 0


class VivotekCam(Camera):
    """A Vivotek IP camera."""

    _attr_brand = DEFAULT_CAMERA_BRAND
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        config: ConfigType | MappingProxyType[str, Any],
        cam_client: VivotekCamera,
        stream_source: str,
    ) -> None:
        """Initialize a Vivotek camera."""
        super().__init__()

        self._cam_client = cam_client
        self._attr_frame_interval = 1 / config[CONF_FRAMERATE]
        self._attr_name = config[CONF_NAME]
        self._stream_source = stream_source

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        return self._cam_client.snapshot()

    async def stream_source(self) -> str:
        """Return the source of the stream."""
        return self._stream_source

    def disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        response = self._cam_client.set_param(DEFAULT_EVENT_0_KEY, 0)
        self._attr_motion_detection_enabled = int(response) == 1

    def enable_motion_detection(self) -> None:
        """Enable motion detection in camera."""
        response = self._cam_client.set_param(DEFAULT_EVENT_0_KEY, 1)
        self._attr_motion_detection_enabled = int(response) == 1

    def update(self) -> None:
        """Update entity status."""
        self._attr_model = self._cam_client.model_name
