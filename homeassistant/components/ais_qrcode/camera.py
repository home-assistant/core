import logging
import io
from homeassistant.core import callback
from homeassistant.components.ais_dom import ais_global
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.components.camera import Camera
from homeassistant.helpers.event import async_track_state_change
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "qr_code"

SCAN_INTERVAL = timedelta(seconds=2000)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the QRCode image platform."""

    add_entities([QRCodeCamera(hass, "remote_access", "remote_access")])


class QRCodeCamera(Camera):
    """Representation of an QRCode image."""

    def __init__(self, hass, name, entity_ids):
        """Initialize the QRCode entity."""
        super().__init__()
        self._hass = hass
        self._name = name
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
            async_track_state_change(self.hass, self._entities, qr_state_listener)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, qr_sensor_startup)

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
        gate_id = ais_global.get_sercure_android_id_dom()
        return "https://" + gate_id + ".paczka.pro"

    def camera_image(self):
        """Process the image."""
        return self._image.getvalue()

    def turn_on(self):
        """Turn on camera."""
        self._refresh_()

    def turn_off(self):
        pass

    def enable_motion_detection(self):
        pass

    def disable_motion_detection(self):
        pass

    def _refresh_(self):
        import pyqrcode
        import png

        gate_id = ais_global.get_sercure_android_id_dom()
        _template = "https://" + gate_id + ".paczka.pro"
        qr_code = pyqrcode.create(_template)
        self._image.truncate(0)
        self._image.seek(0)

        qr_code.png(
            self._image, scale=6, module_color=[0, 0, 0], background=[0xFF, 0xFF, 0xFF]
        )
