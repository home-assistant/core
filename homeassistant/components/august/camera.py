"""Support for August doorbell camera."""
from __future__ import annotations

from yalexs.activity import ActivityType
from yalexs.util import update_doorbell_image_from_activity

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AugustData
from .const import DEFAULT_NAME, DEFAULT_TIMEOUT, DOMAIN
from .entity import AugustEntityMixin


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up August cameras."""
    data: AugustData = hass.data[DOMAIN][config_entry.entry_id]
    # Create an aiohttp session instead of using the default one since the
    # default one is likely to trigger august's WAF if another integration
    # is also using Cloudflare
    session = aiohttp_client.async_create_clientsession(hass)
    async_add_entities(
        AugustCamera(data, doorbell, session, DEFAULT_TIMEOUT)
        for doorbell in data.doorbells
    )


class AugustCamera(AugustEntityMixin, Camera):
    """An implementation of an August security camera."""

    _attr_translation_key = "camera"

    def __init__(self, data, device, session, timeout):
        """Initialize an August security camera."""
        super().__init__(data, device)
        self._timeout = timeout
        self._session = session
        self._image_url = None
        self._image_content = None
        self._attr_unique_id = f"{self._device_id:s}_camera"

    @property
    def is_recording(self) -> bool:
        """Return true if the device is recording."""
        return self._device.has_subscription

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return True

    @property
    def brand(self):
        """Return the camera brand."""
        return DEFAULT_NAME

    @property
    def model(self):
        """Return the camera model."""
        return self._detail.model

    @callback
    def _update_from_data(self):
        """Get the latest state of the sensor."""
        doorbell_activity = self._data.activity_stream.get_latest_device_activity(
            self._device_id,
            {ActivityType.DOORBELL_MOTION, ActivityType.DOORBELL_IMAGE_CAPTURE},
        )

        if doorbell_activity is not None:
            update_doorbell_image_from_activity(self._detail, doorbell_activity)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        self._update_from_data()

        if self._image_url is not self._detail.image_url:
            self._image_url = self._detail.image_url
            self._image_content = await self._detail.async_get_doorbell_image(
                self._session, timeout=self._timeout
            )
        return self._image_content
