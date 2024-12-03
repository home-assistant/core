"""Camera platform that receives images through HTTP POST."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import timedelta
import logging
from typing import cast

from aiohttp import web
import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    PLATFORM_SCHEMA as CAMERA_PLATFORM_SCHEMA,
    Camera,
    CameraState,
)
from homeassistant.const import CONF_NAME, CONF_TIMEOUT, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_BUFFER_SIZE = "buffer"
CONF_IMAGE_FIELD = "field"

DEFAULT_NAME = "Push Camera"

ATTR_FILENAME = "filename"
ATTR_LAST_TRIP = "last_trip"

PUSH_CAMERA_DATA = "push_camera"

PLATFORM_SCHEMA = CAMERA_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_BUFFER_SIZE, default=1): cv.positive_int,
        vol.Optional(CONF_TIMEOUT, default=timedelta(seconds=5)): vol.All(
            cv.time_period, cv.positive_timedelta
        ),
        vol.Optional(CONF_IMAGE_FIELD, default="image"): cv.string,
        vol.Required(CONF_WEBHOOK_ID): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Push Camera platform."""
    if PUSH_CAMERA_DATA not in hass.data:
        hass.data[PUSH_CAMERA_DATA] = {}

    webhook_id = config.get(CONF_WEBHOOK_ID)

    cameras = [
        PushCamera(
            hass,
            config[CONF_NAME],
            config[CONF_BUFFER_SIZE],
            config[CONF_TIMEOUT],
            config[CONF_IMAGE_FIELD],
            webhook_id,
        )
    ]

    async_add_entities(cameras)


async def handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: web.Request
) -> None:
    """Handle incoming webhook POST with image files."""
    try:
        async with asyncio.timeout(5):
            data = dict(await request.post())
    except (TimeoutError, web.HTTPException) as error:
        _LOGGER.error("Could not get information from POST <%s>", error)
        return

    camera = hass.data[PUSH_CAMERA_DATA][webhook_id]

    if camera.image_field not in data:
        _LOGGER.warning("Webhook call without POST parameter <%s>", camera.image_field)
        return

    image_data = cast(web.FileField, data[camera.image_field])
    await camera.update_image(image_data.file.read(), image_data.filename)


class PushCamera(Camera):
    """The representation of a Push camera."""

    def __init__(self, hass, name, buffer_size, timeout, image_field, webhook_id):
        """Initialize push camera component."""
        super().__init__()
        self._name = name
        self._last_trip = None
        self._filename = None
        self._expired_listener = None
        self._timeout = timeout
        self.queue = deque([], buffer_size)
        self._current_image = None
        self._image_field = image_field
        self.webhook_id = webhook_id
        self.webhook_url = webhook.async_generate_url(hass, webhook_id)

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self.hass.data[PUSH_CAMERA_DATA][self.webhook_id] = self

        try:
            webhook.async_register(
                self.hass, CAMERA_DOMAIN, self.name, self.webhook_id, handle_webhook
            )
        except ValueError:
            _LOGGER.error(
                "In <%s>, webhook_id <%s> already used", self.name, self.webhook_id
            )

    @property
    def image_field(self):
        """HTTP field containing the image file."""
        return self._image_field

    async def update_image(self, image, filename):
        """Update the camera image."""
        if self.state == CameraState.IDLE:
            self._attr_is_recording = True
            self._last_trip = dt_util.utcnow()
            self.queue.clear()

        self._filename = filename
        self.queue.appendleft(image)

        @callback
        def reset_state(now):
            """Set state to idle after no new images for a period of time."""
            self._attr_is_recording = False
            self._expired_listener = None
            _LOGGER.debug("Reset state")
            self.async_write_ha_state()

        if self._expired_listener:
            self._expired_listener()

        self._expired_listener = async_track_point_in_utc_time(
            self.hass, reset_state, dt_util.utcnow() + self._timeout
        )

        self.async_write_ha_state()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response."""
        if self.queue:
            if self.state == CameraState.IDLE:
                self.queue.rotate(1)
            self._current_image = self.queue[0]

        return self._current_image

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def motion_detection_enabled(self):
        """Camera Motion Detection Status."""
        return False

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            name: value
            for name, value in (
                (ATTR_LAST_TRIP, self._last_trip),
                (ATTR_FILENAME, self._filename),
            )
            if value is not None
        }
