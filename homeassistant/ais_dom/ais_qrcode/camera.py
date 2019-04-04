import logging
import io
import voluptuous as vol
from homeassistant.core import callback

from homeassistant.const import (
    CONF_NAME, CONF_VALUE_TEMPLATE, ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_START)
from homeassistant.components.camera import (PLATFORM_SCHEMA, Camera)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change
from datetime import timedelta

REQUIREMENTS = ['pyqrcode==1.2.1', 'pypng==0.0.18']
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'qr_code'

SCAN_INTERVAL = timedelta(seconds=2000)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


async def async_setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the QRCode image platform."""
    name = config.get(CONF_NAME)
    value_template = config.get(CONF_VALUE_TEMPLATE)

    if value_template is not None:
        value_template.hass = hass
    entity_ids = (config.get(ATTR_ENTITY_ID)
                  or value_template.extract_entities())

    add_devices([QRCodeCamera(hass, name, value_template, entity_ids)])
    return True


class QRCodeCamera(Camera):
    """Representation of an QRCode image."""

    def __init__(self, hass, name, template, entity_ids):
        """Initialize the QRCode entity."""
        super().__init__()
        self._hass = hass
        self._name = name
        self._template = template
        self._entities = entity_ids
        self._image = io.BytesIO()
        self._refresh_()

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def qr_state_listener(entity, old_state, new_state):
            """Handle device state changes."""
            self._refresh_()

        @callback
        def qr_sensor_startup(event):
            """Update template on startup."""
            async_track_state_change(
                self.hass, self._entities, qr_state_listener)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, qr_sensor_startup)

    @property
    def name(self):
        """Return the name of the image processor."""
        return self._name

    @property
    def should_poll(self):
        """Update the recording state periodically."""
        return True

    @property
    def state(self):
        return self._template.async_render()

    def camera_image(self):
        """Process the image."""
        return self._image.getvalue()

    def turn_on(self):
        """Turn on camera."""
        self._refresh_()

    def _refresh_(self):
        import pyqrcode
        import png
        qr_code = pyqrcode.create(self._template.async_render())
        self._image.truncate(0)
        self._image.seek(0)

        qr_code.png(self._image, scale=6, module_color=[0, 0, 0], background=[0xff, 0xff, 0xff])
