"""Support for Google Nest SDM Cameras."""

import logging
from typing import Optional

from google_nest_sdm.camera_traits import CameraImageTrait, CameraLiveStreamTrait
from google_nest_sdm.device import Device
from haffmpeg.tools import IMAGE_JPEG

from homeassistant.components.camera import SUPPORT_STREAM, Camera
from homeassistant.components.ffmpeg import async_get_image
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.dt import utcnow

from .const import DOMAIN, SIGNAL_NEST_UPDATE
from .device_info import DeviceInfo

_LOGGER = logging.getLogger(__name__)


async def async_setup_sdm_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the cameras."""

    subscriber = hass.data[DOMAIN][entry.entry_id]
    device_manager = await subscriber.async_get_device_manager()

    # Fetch initial data so we have data when entities subscribe.

    entities = []
    for device in device_manager.devices.values():
        if (
            CameraImageTrait.NAME in device.traits
            or CameraLiveStreamTrait.NAME in device.traits
        ):
            entities.append(NestCamera(device))
    async_add_entities(entities)


class NestCamera(Camera):
    """Devices that support cameras."""

    def __init__(self, device: Device):
        """Initialize the camera."""
        super().__init__()
        self._device = device
        self._device_info = DeviceInfo(device)
        self._stream = None

    @property
    def should_poll(self) -> bool:
        """Disable polling since entities have state pushed via pubsub."""
        return False

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        # The API "name" field is a unique device identifier.
        return f"{self._device.name}-camera"

    @property
    def name(self):
        """Return the name of the camera."""
        return self._device_info.device_name

    @property
    def device_info(self):
        """Return device specific attributes."""
        return self._device_info.device_info

    @property
    def brand(self):
        """Return the camera brand."""
        return self._device_info.device_brand

    @property
    def model(self):
        """Return the camera model."""
        return self._device_info.device_model

    @property
    def supported_features(self):
        """Flag supported features."""
        features = 0
        if CameraLiveStreamTrait.NAME in self._device.traits:
            features = features | SUPPORT_STREAM
        return features

    async def stream_source(self):
        """Return the source of the stream."""
        if CameraLiveStreamTrait.NAME not in self._device.traits:
            return None
        trait = self._device.traits[CameraLiveStreamTrait.NAME]
        now = utcnow()
        if not self._stream:
            logging.debug("Fetching stream url")
            self._stream = await trait.generate_rtsp_stream()
        elif self._stream.expires_at < now:
            logging.debug("Stream expired, extending stream")
            new_stream = await self._stream.extend_rtsp_stream()
            self._stream = new_stream
        return self._stream.rtsp_stream_url

    async def async_will_remove_from_hass(self):
        """Invalidates the RTSP token when unloaded."""
        if self._stream:
            logging.debug("Invalidating stream")
            await self._stream.stop_rtsp_stream()

    async def async_added_to_hass(self):
        """Run when entity is added to register update signal handler."""
        # Event messages trigger the SIGNAL_NEST_UPDATE, which is intercepted
        # here to re-fresh the signals from _device.  Unregister this callback
        # when the entity is removed.
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_NEST_UPDATE, self.async_write_ha_state
            )
        )

    async def async_camera_image(self):
        """Return bytes of camera image."""
        stream_url = await self.stream_source()
        if not stream_url:
            return None
        return await async_get_image(self.hass, stream_url, output_format=IMAGE_JPEG)
