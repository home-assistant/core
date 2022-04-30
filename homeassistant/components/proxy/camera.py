"""Proxy camera platform that enables image processing of camera data."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import io
import logging

from PIL import Image
import voluptuous as vol

from homeassistant.components.camera import (
    PLATFORM_SCHEMA,
    Camera,
    async_get_image,
    async_get_mjpeg_stream,
    async_get_still_stream,
)
from homeassistant.const import CONF_ENTITY_ID, CONF_MODE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_CACHE_IMAGES = "cache_images"
CONF_FORCE_RESIZE = "force_resize"
CONF_IMAGE_QUALITY = "image_quality"
CONF_IMAGE_REFRESH_RATE = "image_refresh_rate"
CONF_MAX_IMAGE_WIDTH = "max_image_width"
CONF_MAX_IMAGE_HEIGHT = "max_image_height"
CONF_MAX_STREAM_WIDTH = "max_stream_width"
CONF_MAX_STREAM_HEIGHT = "max_stream_height"
CONF_IMAGE_TOP = "image_top"
CONF_IMAGE_LEFT = "image_left"
CONF_STREAM_QUALITY = "stream_quality"

MODE_RESIZE = "resize"
MODE_CROP = "crop"

DEFAULT_BASENAME = "Camera Proxy"
DEFAULT_QUALITY = 75

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_CACHE_IMAGES, False): cv.boolean,
        vol.Optional(CONF_FORCE_RESIZE, False): cv.boolean,
        vol.Optional(CONF_MODE, default=MODE_RESIZE): vol.In([MODE_RESIZE, MODE_CROP]),
        vol.Optional(CONF_IMAGE_QUALITY): int,
        vol.Optional(CONF_IMAGE_REFRESH_RATE): float,
        vol.Optional(CONF_MAX_IMAGE_WIDTH): int,
        vol.Optional(CONF_MAX_IMAGE_HEIGHT): int,
        vol.Optional(CONF_MAX_STREAM_WIDTH): int,
        vol.Optional(CONF_MAX_STREAM_HEIGHT): int,
        vol.Optional(CONF_IMAGE_LEFT): int,
        vol.Optional(CONF_IMAGE_TOP): int,
        vol.Optional(CONF_STREAM_QUALITY): int,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Proxy camera platform."""
    async_add_entities([ProxyCamera(hass, config)])


def _precheck_image(image, opts):
    """Perform some pre-checks on the given image."""
    if not opts:
        raise ValueError()
    try:
        img = Image.open(io.BytesIO(image))
    except OSError as err:
        _LOGGER.warning("Failed to open image")
        raise ValueError() from err
    imgfmt = str(img.format)
    if imgfmt not in ("PNG", "JPEG"):
        _LOGGER.warning("Image is of unsupported type: %s", imgfmt)
        raise ValueError()
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _resize_image(image, opts):
    """Resize image."""
    try:
        img = _precheck_image(image, opts)
    except ValueError:
        return image

    quality = opts.quality or DEFAULT_QUALITY
    new_width = opts.max_width
    (old_width, old_height) = img.size
    old_size = len(image)
    if old_width <= new_width:
        if opts.quality is None:
            _LOGGER.debug("Image is smaller-than/equal-to requested width")
            return image
        new_width = old_width

    scale = new_width / float(old_width)
    new_height = int(float(old_height) * float(scale))

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    imgbuf = io.BytesIO()
    img.save(imgbuf, "JPEG", optimize=True, quality=quality)
    newimage = imgbuf.getvalue()
    if not opts.force_resize and len(newimage) >= old_size:
        _LOGGER.debug(
            "Using original image (%d bytes) "
            "because resized image (%d bytes) is not smaller",
            old_size,
            len(newimage),
        )
        return image

    _LOGGER.debug(
        "Resized image from (%dx%d - %d bytes) to (%dx%d - %d bytes)",
        old_width,
        old_height,
        old_size,
        new_width,
        new_height,
        len(newimage),
    )
    return newimage


def _crop_image(image, opts):
    """Crop image."""
    try:
        img = _precheck_image(image, opts)
    except ValueError:
        return image

    quality = opts.quality or DEFAULT_QUALITY
    (old_width, old_height) = img.size
    old_size = len(image)
    if opts.top is None:
        opts.top = 0
    if opts.left is None:
        opts.left = 0
    if opts.max_width is None or opts.max_width > old_width - opts.left:
        opts.max_width = old_width - opts.left
    if opts.max_height is None or opts.max_height > old_height - opts.top:
        opts.max_height = old_height - opts.top

    img = img.crop(
        (opts.left, opts.top, opts.left + opts.max_width, opts.top + opts.max_height)
    )
    imgbuf = io.BytesIO()
    img.save(imgbuf, "JPEG", optimize=True, quality=quality)
    newimage = imgbuf.getvalue()

    _LOGGER.debug(
        "Cropped image from (%dx%d - %d bytes) to (%dx%d - %d bytes)",
        old_width,
        old_height,
        old_size,
        opts.max_width,
        opts.max_height,
        len(newimage),
    )
    return newimage


class ImageOpts:
    """The representation of image options."""

    def __init__(self, max_width, max_height, left, top, quality, force_resize):
        """Initialize image options."""
        self.max_width = max_width
        self.max_height = max_height
        self.left = left
        self.top = top
        self.quality = quality
        self.force_resize = force_resize

    def __bool__(self):
        """Bool evaluation rules."""
        return bool(self.max_width or self.quality)


class ProxyCamera(Camera):
    """The representation of a Proxy camera."""

    def __init__(self, hass, config):
        """Initialize a proxy camera component."""
        super().__init__()
        self.hass = hass
        self._proxied_camera = config.get(CONF_ENTITY_ID)
        self._name = (
            config.get(CONF_NAME) or f"{DEFAULT_BASENAME} - {self._proxied_camera}"
        )
        self._image_opts = ImageOpts(
            config.get(CONF_MAX_IMAGE_WIDTH),
            config.get(CONF_MAX_IMAGE_HEIGHT),
            config.get(CONF_IMAGE_LEFT),
            config.get(CONF_IMAGE_TOP),
            config.get(CONF_IMAGE_QUALITY),
            config.get(CONF_FORCE_RESIZE),
        )

        self._stream_opts = ImageOpts(
            config.get(CONF_MAX_STREAM_WIDTH),
            config.get(CONF_MAX_STREAM_HEIGHT),
            config.get(CONF_IMAGE_LEFT),
            config.get(CONF_IMAGE_TOP),
            config.get(CONF_STREAM_QUALITY),
            True,
        )

        self._image_refresh_rate = config.get(CONF_IMAGE_REFRESH_RATE)
        self._cache_images = bool(
            config.get(CONF_IMAGE_REFRESH_RATE) or config.get(CONF_CACHE_IMAGES)
        )
        self._last_image_time = dt_util.utc_from_timestamp(0)
        self._last_image = None
        self._mode = config.get(CONF_MODE)

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return camera image."""
        return asyncio.run_coroutine_threadsafe(
            self.async_camera_image(), self.hass.loop
        ).result()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        now = dt_util.utcnow()

        if self._image_refresh_rate and now < self._last_image_time + timedelta(
            seconds=self._image_refresh_rate
        ):
            return self._last_image

        self._last_image_time = now
        image = await async_get_image(self.hass, self._proxied_camera)
        if not image:
            _LOGGER.error("Error getting original camera image")
            return self._last_image

        if self._mode == MODE_RESIZE:
            job = _resize_image
        else:
            job = _crop_image
        image_bytes: bytes = await self.hass.async_add_executor_job(
            job, image.content, self._image_opts
        )

        if self._cache_images:
            self._last_image = image_bytes
        return image_bytes

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from camera images."""
        if not self._stream_opts:
            return await async_get_mjpeg_stream(
                self.hass, request, self._proxied_camera
            )

        return await async_get_still_stream(
            request, self._async_stream_image, self.content_type, self.frame_interval
        )

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    async def _async_stream_image(self):
        """Return a still image response from the camera."""
        try:
            image = await async_get_image(self.hass, self._proxied_camera)
            if not image:
                return None
        except HomeAssistantError as err:
            raise asyncio.CancelledError() from err

        if self._mode == MODE_RESIZE:
            job = _resize_image
        else:
            job = _crop_image
        return await self.hass.async_add_executor_job(
            job, image.content, self._stream_opts
        )
