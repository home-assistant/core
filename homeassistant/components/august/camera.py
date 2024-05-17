"""Support for August doorbell camera."""

from __future__ import annotations

import logging

from aiohttp import ClientSession
from yalexs.activity import ActivityType
from yalexs.const import Brand
from yalexs.doorbell import ContentTokenExpired, Doorbell
from yalexs.util import update_doorbell_image_from_activity

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AugustConfigEntry, AugustData
from .const import DEFAULT_NAME, DEFAULT_TIMEOUT
from .entity import AugustEntityMixin

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AugustConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up August cameras."""
    data = config_entry.runtime_data
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

    def __init__(
        self, data: AugustData, device: Doorbell, session: ClientSession, timeout: int
    ) -> None:
        """Initialize an August security camera."""
        super().__init__(data, device)
        self._timeout = timeout
        self._session = session
        self._image_url = None
        self._content_token = None
        self._image_content = None
        self._attr_unique_id = f"{self._device_id:s}_camera"
        self._attr_motion_detection_enabled = True
        self._attr_brand = DEFAULT_NAME

    @property
    def is_recording(self) -> bool:
        """Return true if the device is recording."""
        return self._device.has_subscription

    @property
    def model(self) -> str | None:
        """Return the camera model."""
        return self._detail.model

    async def _async_update(self):
        """Update device."""
        _LOGGER.debug("async_update called %s", self._detail.device_name)
        await self._data.refresh_camera_by_id(self._device_id)
        self._update_from_data()

    @callback
    def _update_from_data(self) -> None:
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
            self._content_token = self._detail.content_token or self._content_token
            _LOGGER.debug(
                "calling doorbell async_get_doorbell_image, %s",
                self._detail.device_name,
            )
            try:
                self._image_content = await self._detail.async_get_doorbell_image(
                    self._session, timeout=self._timeout
                )
            except ContentTokenExpired:
                if self._data.brand == Brand.YALE_HOME:
                    _LOGGER.debug(
                        "Error fetching camera image, updating content-token from api to retry"
                    )
                    await self._async_update()
                    self._image_content = await self._detail.async_get_doorbell_image(
                        self._session, timeout=self._timeout
                    )

        return self._image_content
