"""Support to the Logi Circle cameras."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTRIBUTION,
    DEVICE_BRAND,
    DOMAIN as LOGI_CIRCLE_DOMAIN,
    LED_MODE_KEY,
    RECORDING_MODE_KEY,
    SIGNAL_LOGI_CIRCLE_RECONFIGURE,
    SIGNAL_LOGI_CIRCLE_RECORD,
    SIGNAL_LOGI_CIRCLE_SNAPSHOT,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a Logi Circle Camera. Obsolete."""
    _LOGGER.warning("Logi Circle no longer works with camera platform configuration")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Logi Circle Camera based on a config entry."""
    devices = await hass.data[LOGI_CIRCLE_DOMAIN].cameras
    ffmpeg = get_ffmpeg_manager(hass)

    cameras = [LogiCam(device, ffmpeg) for device in devices]

    async_add_entities(cameras, True)


class LogiCam(Camera):
    """An implementation of a Logi Circle camera."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = True  # Cameras default to False
    _attr_supported_features = CameraEntityFeature.ON_OFF
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, camera, ffmpeg):
        """Initialize Logi Circle camera."""
        super().__init__()
        self._camera = camera
        self._id = self._camera.mac_address
        self._has_battery = self._camera.supports_feature("battery_level")
        self._ffmpeg = ffmpeg
        self._listeners = []

    async def async_added_to_hass(self) -> None:
        """Connect camera methods to signals."""

        def _dispatch_proxy(method):
            """Expand parameters & filter entity IDs."""

            async def _call(params):
                entity_ids = params.get(ATTR_ENTITY_ID)
                filtered_params = {
                    k: v for k, v in params.items() if k != ATTR_ENTITY_ID
                }
                if entity_ids is None or self.entity_id in entity_ids:
                    await method(**filtered_params)

            return _call

        self._listeners.extend(
            [
                async_dispatcher_connect(
                    self.hass,
                    SIGNAL_LOGI_CIRCLE_RECONFIGURE,
                    _dispatch_proxy(self.set_config),
                ),
                async_dispatcher_connect(
                    self.hass,
                    SIGNAL_LOGI_CIRCLE_SNAPSHOT,
                    _dispatch_proxy(self.livestream_snapshot),
                ),
                async_dispatcher_connect(
                    self.hass,
                    SIGNAL_LOGI_CIRCLE_RECORD,
                    _dispatch_proxy(self.download_livestream),
                ),
            ]
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher listeners when removed."""
        for detach in self._listeners:
            detach()

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._id

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            identifiers={(LOGI_CIRCLE_DOMAIN, self._camera.id)},
            manufacturer=DEVICE_BRAND,
            model=self._camera.model_name,
            name=self._camera.name,
            sw_version=self._camera.firmware,
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        state = {
            "battery_saving_mode": (
                STATE_ON if self._camera.battery_saving else STATE_OFF
            ),
            "microphone_gain": self._camera.microphone_gain,
        }

        # Add battery attributes if camera is battery-powered
        if self._has_battery:
            state[ATTR_BATTERY_CHARGING] = self._camera.charging
            state[ATTR_BATTERY_LEVEL] = self._camera.battery_level

        return state

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from the camera."""
        return await self._camera.live_stream.download_jpeg()

    async def async_turn_off(self) -> None:
        """Disable streaming mode for this camera."""
        await self._camera.set_config("streaming", False)

    async def async_turn_on(self) -> None:
        """Enable streaming mode for this camera."""
        await self._camera.set_config("streaming", True)

    async def set_config(self, mode, value):
        """Set an configuration property for the target camera."""
        if mode == LED_MODE_KEY:
            await self._camera.set_config("led", value)
        if mode == RECORDING_MODE_KEY:
            await self._camera.set_config("recording_disabled", not value)

    async def download_livestream(self, filename, duration):
        """Download a recording from the camera's livestream."""
        # Render filename from template.
        filename.hass = self.hass
        stream_file = filename.async_render(variables={ATTR_ENTITY_ID: self.entity_id})

        # Respect configured allowed paths.
        if not self.hass.config.is_allowed_path(stream_file):
            _LOGGER.error("Can't write %s, no access to path!", stream_file)
            return

        await self._camera.live_stream.download_rtsp(
            filename=stream_file,
            duration=timedelta(seconds=duration),
            ffmpeg_bin=self._ffmpeg.binary,
        )

    async def livestream_snapshot(self, filename):
        """Download a still frame from the camera's livestream."""
        # Render filename from template.
        filename.hass = self.hass
        snapshot_file = filename.async_render(
            variables={ATTR_ENTITY_ID: self.entity_id}
        )

        # Respect configured allowed paths.
        if not self.hass.config.is_allowed_path(snapshot_file):
            _LOGGER.error("Can't write %s, no access to path!", snapshot_file)
            return

        await self._camera.live_stream.download_jpeg(
            filename=snapshot_file, refresh=True
        )

    async def async_update(self) -> None:
        """Update camera entity and refresh attributes."""
        await self._camera.update()
