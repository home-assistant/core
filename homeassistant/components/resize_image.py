"""
Component that will enable resizing images to reduce bandwidth.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/resize_image
"""
import asyncio
import logging

import voluptuous as vol

REQUIREMENTS = ['pillow==5.0.0']

DOMAIN = 'resize_image'

_LOGGER = logging.getLogger(__name__)


CONF_MAX_WIDTH = 'max_width'
CONF_QUALITY = 'quality'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_MAX_WIDTH, default=0): int,
        vol.Optional(CONF_QUALITY, default=75): int,
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the resize_image component."""
    conf = config.get(DOMAIN, {})

    resizer = ImageResizer(
        hass,
        conf.get(CONF_MAX_WIDTH),
        conf.get(CONF_QUALITY)
    )

    hass.data[DOMAIN] = resizer
    return True


class ImageResizer(object):
    """Helper for resize_image."""

    def __init__(self, hass, max_width, quality):
        """Initialize helper."""
        self.hass = hass
        self._max_width = max_width
        self._quality = quality

    def resize_image(self, image, requested_width):
        """Resize image."""
        from PIL import Image
        import io

        if self._max_width and requested_width > self._max_width:
            new_width = self._max_width
        else:
            new_width = requested_width
        if new_width == 0:
            _LOGGER.debug("No resize width requested")
            return image

        img = Image.open(io.BytesIO(image))
        imgfmt = str(img.format)
        if imgfmt != 'PNG' and imgfmt != 'JPEG':
            _LOGGER.debug("Image is of unsupported type: %s", imgfmt)
            return image

        (old_width, old_height) = img.size
        old_size = len(image)
        if old_width <= new_width:
            _LOGGER.debug("Image is smaller than requested width")
            return image

        scale = new_width / float(old_width)
        new_height = int((float(old_height)*float(scale)))

        img = img.resize((new_width, new_height), Image.ANTIALIAS)
        imgbuf = io.BytesIO()
        img.save(imgbuf, "JPEG", optimize=True, quality=self._quality)
        image = imgbuf.getvalue()
        _LOGGER.debug("Resized image "
                      "from (%dx%d - %d bytes) "
                      "to (%dx%d - %d bytes)",
                      old_width, old_height, old_size,
                      new_width, new_height, len(image))
        return image
