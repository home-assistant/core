"""
Proxy camera platform that enables image processing of camera data.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/proxy
"""
import logging
import asyncio
import aiohttp
import async_timeout

import voluptuous as vol

from homeassistant.util.async import run_coroutine_threadsafe
from homeassistant.helpers import config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID, HTTP_HEADER_HA_AUTH)
from homeassistant.components.camera import (
    PLATFORM_SCHEMA, Camera)
from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession, async_aiohttp_proxy_web)

REQUIREMENTS = ['pillow==5.0.0']

_LOGGER = logging.getLogger(__name__)

CONF_MAX_IMAGE_WIDTH = "max_image_width"
CONF_IMAGE_QUALITY = "image_quality"
CONF_IMAGE_REFRESH_RATE = "image_refresh_rate"
CONF_FORCE_RESIZE = "force_resize"
CONF_MAX_STREAM_WIDTH = "max_stream_width"
CONF_STREAM_QUALITY = "stream_quality"
CONF_CACHE_IMAGES = "cache_images"

DEFAULT_BASENAME = "Camera Proxy"
DEFAULT_QUALITY = 75

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_MAX_IMAGE_WIDTH): int,
    vol.Optional(CONF_IMAGE_QUALITY): int,
    vol.Optional(CONF_IMAGE_REFRESH_RATE): float,
    vol.Optional(CONF_FORCE_RESIZE, False): cv.boolean,
    vol.Optional(CONF_CACHE_IMAGES, False): cv.boolean,
    vol.Optional(CONF_MAX_STREAM_WIDTH): int,
    vol.Optional(CONF_STREAM_QUALITY): int,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Proxy camera platform."""
    async_add_devices([ProxyCamera(hass, config)])

    return True


@asyncio.coroutine
def _read_frame(req):
    """Read a single frame from an MJPEG stream."""
    # based on https://gist.github.com/russss/1143799
    import cgi
    # Read in HTTP headers:
    stream = req.content
    # multipart/x-mixed-replace; boundary=--frameboundary
    __mimetype, options = cgi.parse_header(req.headers['content-type'])
    boundary = options.get('boundary').encode('utf-8')
    if not boundary:
        raise Exception("Can't find content-type")

    line = yield from stream.readline()
    # Seek ahead to the first chunk
    while line.strip() != boundary:
        line = yield from stream.readline()
    # Read in chunk headers
    while line.strip() != b'':
        parts = line.split(b':')
        if len(parts) > 1 and parts[0].lower() == b'content-length':
            # Grab chunk length
            length = int(parts[1].strip())
        line = yield from stream.readline()
    image = yield from stream.read(length)
    return image


def _resize_image(image, opts):
    """Resize image."""
    from PIL import Image
    import io

    if not opts:
        return image

    quality = opts.quality if opts.quality else DEFAULT_QUALITY
    new_width = opts.max_width

    img = Image.open(io.BytesIO(image))
    imgfmt = str(img.format)
    if imgfmt != 'PNG' and imgfmt != 'JPEG':
        _LOGGER.debug("Image is of unsupported type: %s", imgfmt)
        return image

    (old_width, old_height) = img.size
    old_size = len(image)
    if old_width <= new_width:
        if opts.quality is None:
            _LOGGER.debug("Image is smaller than requested width")
            return image
        new_width = old_width

    scale = new_width / float(old_width)
    new_height = int((float(old_height)*float(scale)))

    img = img.resize((new_width, new_height), Image.ANTIALIAS)
    imgbuf = io.BytesIO()
    img.save(imgbuf, "JPEG", optimize=True, quality=quality)
    newimage = imgbuf.getvalue()
    if not opts.force_resize and len(newimage) >= old_size:
        _LOGGER.debug("Using original image(%d bytes) "
                      "because resized image (%d bytes) is larger",
                      old_size, len(newimage))
        return image

    _LOGGER.debug("Resized image "
                  "from (%dx%d - %d bytes) "
                  "to (%dx%d - %d bytes)",
                  old_width, old_height, old_size,
                  new_width, new_height, len(newimage))
    return newimage


class ImageOpts():
    """The representation of image options."""

    def __init__(self, max_width, quality, force_resize):
        """Initialize image options."""
        self.max_width = max_width
        self.quality = quality
        self.force_resize = force_resize

    def __bool__(self):
        """Bool evaution rules."""
        return True if self.max_width or self.quality else False


class ProxyCamera(Camera):
    """The representation of a Proxy camera."""

    def __init__(self, hass, config):
        """Initialize a proxy camera component."""
        super().__init__()
        self.hass = hass
        self._proxied_camera = config.get(CONF_ENTITY_ID)
        self._name = config.get(CONF_NAME)
        if not self._name:
            self._name = "{} - {}".format(DEFAULT_BASENAME,
                                          self._proxied_camera)
        self._image_opts = ImageOpts(
            config.get(CONF_MAX_IMAGE_WIDTH),
            config.get(CONF_IMAGE_QUALITY),
            config.get(CONF_FORCE_RESIZE))

        self._stream_opts = ImageOpts(
            config.get(CONF_MAX_STREAM_WIDTH),
            config.get(CONF_STREAM_QUALITY),
            True)
        self._image_refresh_rate = config.get(CONF_IMAGE_REFRESH_RATE)
        self._cache_images = (
            True
            if (config.get(CONF_IMAGE_REFRESH_RATE)
                or config.get(CONF_CACHE_IMAGES))
            else False)
        self._last_image_time = 0
        self._last_image = None
        self._headers = (
            {HTTP_HEADER_HA_AUTH: self.hass.config.api.api_password}
            if self.hass.config.api.api_password is not None
            else None)

    def camera_image(self):
        """Return camera image."""
        return run_coroutine_threadsafe(
            self.async_camera_image(), self.hass.loop).result()

    @asyncio.coroutine
    def async_camera_image(self):
        """Return a still image response from the camera."""
        now = dt_util.utcnow()

        if (self._image_refresh_rate and
                now < self._last_image_time + self._image_refresh_rate):
            return self._last_image

        self._last_image_time = now
        url = "{}/api/camera_proxy/{}".format(
            self.hass.config.api.base_url, self._proxied_camera)
        try:
            websession = async_get_clientsession(self.hass)
            with async_timeout.timeout(10, loop=self.hass.loop):
                response = yield from websession.get(url,
                                                     headers=self._headers)
            image = yield from response.read()
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout getting camera image")
            return self._last_image
        except aiohttp.ClientError as err:
            _LOGGER.error("Error getting new camera image: %s", err)
            return self._last_image

        image = yield from self.hass.async_add_job(
            _resize_image, image, self._image_opts)

        if self._cache_images:
            self._last_image = image
        return image

    @asyncio.coroutine
    def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from camera images."""
        websession = async_get_clientsession(self.hass)
        url = "{}/api/camera_proxy_stream/{}".format(
            self.hass.config.api.base_url, self._proxied_camera)
        stream_coro = websession.get(url, headers=self._headers)

        if not self._stream_opts:
            yield from async_aiohttp_proxy_web(self.hass, request, stream_coro)
            return

        response = aiohttp.web.StreamResponse()
        response.content_type = ('multipart/x-mixed-replace; '
                                 'boundary=--frameboundary')
        yield from response.prepare(request)

        def write(img_bytes):
            """Write image to stream."""
            response.write(bytes(
                '--frameboundary\r\n'
                'Content-Type: {}\r\n'
                'Content-Length: {}\r\n\r\n'.format(
                    self.content_type, len(img_bytes)),
                'utf-8') + img_bytes + b'\r\n')

        with async_timeout.timeout(10, loop=self.hass.loop):
            req = yield from stream_coro
        try:
            while True:
                image = yield from _read_frame(req)
                image = yield from self.hass.async_add_job(
                    _resize_image, image, self._stream_opts)
                write(image)
        except asyncio.CancelledError:
            _LOGGER.debug("Stream closed by frontend.")
            response = None

        finally:
            if response is not None:
                yield from response.write_eof()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
