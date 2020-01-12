"""Support to the Logi Circle cameras."""
from datetime import timedelta
import logging

from homeassistant.components.camera import ATTR_ENTITY_ID, SUPPORT_ON_OFF, Camera
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a Logi Circle Camera. Obsolete."""
    _LOGGER.warning("Logi Circle no longer works with camera platform configuration")


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Logi Circle Camera based on a config entry."""
    devices = await hass.data[LOGI_CIRCLE_DOMAIN].cameras
    ffmpeg = hass.data[DATA_FFMPEG]

    cameras = [LogiCam(device, entry, ffmpeg) for device in devices]

    async_add_entities(cameras, True)


class LogiCam(Camera):
    """An implementation of a Logi Circle camera."""

    def __init__(self, camera, device_info, ffmpeg):
        """Initialize Logi Circle camera."""
        super().__init__()
        self._camera = camera
        self._name = self._camera.name
        self._id = self._camera.mac_address
        self._has_battery = self._camera.supports_feature("battery_level")
        self._ffmpeg = ffmpeg
        self._listeners = []

    async def async_added_to_hass(self):
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

    async def async_will_remove_from_hass(self):
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
    def supported_features(self):
        """Logi Circle camera's support turning on and off ("soft" switch)."""
        return SUPPORT_ON_OFF

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "name": self._camera.name,
            "identifiers": {(LOGI_CIRCLE_DOMAIN, self._camera.id)},
            "model": self._camera.model_name,
            "sw_version": self._camera.firmware,
            "manufacturer": DEVICE_BRAND,
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
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

    async def async_camera_image(self):
        """Return a still image from the camera."""
        return await self._camera.live_stream.download_jpeg()

    async def async_turn_off(self):
        """Disable streaming mode for this camera."""
        await self._camera.set_config("streaming", False)

    async def async_turn_on(self):
        """Enable streaming mode for this camera."""
        await self._camera.set_config("streaming", True)

    @property
    def should_poll(self):
        """Update the image periodically."""
        return True

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

        # Respect configured path whitelist.
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

        # Respect configured path whitelist.
        if not self.hass.config.is_allowed_path(snapshot_file):
            _LOGGER.error("Can't write %s, no access to path!", snapshot_file)
            return

        await self._camera.live_stream.download_jpeg(
            filename=snapshot_file, refresh=True
        )

    async def async_update(self):
        """Update camera entity and refresh attributes."""
        await self._camera.update()
