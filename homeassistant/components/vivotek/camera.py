"""Support for Vivotek IP Cameras."""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

from libpyvivotek import VivotekCamera
import voluptuous as vol

from homeassistant.components.camera import (
    PLATFORM_SCHEMA as CAMERA_PLATFORM_SCHEMA,
    Camera,
    CameraEntityFeature,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import VivotekConfigEntry
from .const import (
    CONF_FRAMERATE,
    CONF_SECURITY_LEVEL,
    CONF_STREAM_PATH,
    DOMAIN,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_CAMERA_BRAND = "VIVOTEK"
DEFAULT_NAME = "VIVOTEK Camera"
DEFAULT_EVENT_0_KEY = "event_i0_enable"
DEFAULT_SECURITY_LEVEL = "admin"
DEFAULT_STREAM_SOURCE = "live.sdp"


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
    entry: VivotekConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the component from a config entry."""
    config = entry.data
    creds = f"{config[CONF_USERNAME]}:{config[CONF_PASSWORD]}"
    stream_source = (
        f"rtsp://{creds}@{config[CONF_IP_ADDRESS]}:554/{config[CONF_STREAM_PATH]}"
    )
    cam_client = entry.runtime_data.cam_client
    mac_address = await hass.async_add_executor_job(cam_client.get_mac)
    unique_id = format_mac(mac_address)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, unique_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, mac_address)},
    )

    if not entry.unique_id:
        hass.config_entries.async_update_entry(
            entry,
            unique_id=unique_id,
            title=str(config[CONF_NAME]),
        )
    async_add_entities([VivotekCam(entry.data, cam_client, stream_source, unique_id)])


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a Vivotek IP Camera from Yaml."""
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
    unique_id = cam.get_mac()
    add_entities([VivotekCam(config, cam, stream_source, unique_id)], True)


class VivotekCam(Camera):
    """A Vivotek IP camera."""

    # Overrides from Camera
    _attr_brand = DEFAULT_CAMERA_BRAND
    _attr_supported_features = CameraEntityFeature.STREAM

    _attr_configuration_url: str | None = None
    _attr_serial: str | None = None

    def __init__(
        self,
        config: ConfigType | MappingProxyType[str, Any],
        cam_client: VivotekCamera,
        stream_source: str,
        unique_id: str,
    ) -> None:
        """Initialize a Vivotek camera."""
        super().__init__()
        self._cam_client = cam_client
        self._attr_configuration_url = f"http://{config[CONF_IP_ADDRESS]}"
        self._attr_frame_interval = 1 / config[CONF_FRAMERATE]
        self._attr_name = config[CONF_NAME]
        self._attr_unique_id = unique_id
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
        self._attr_available = self._attr_model is not None
        self._attr_serial = self._cam_client.get_serial()

    async def async_update(self) -> None:
        """Update the entity."""
        await self.hass.async_add_executor_job(self.update)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device info."""
        return DeviceInfo(
            configuration_url=self._attr_configuration_url,
            identifiers={(DOMAIN, self._attr_unique_id or "")},
            manufacturer=MANUFACTURER,
            model=self._attr_model,
            name=self._attr_name,
            serial_number=self._attr_unique_id,
        )
