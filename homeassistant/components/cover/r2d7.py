"""Support for r2d7 shade controllers.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/r2d7/
"""
import logging
import voluptuous as vol
from homeassistant.components.cover import (
    CoverDevice, SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_SET_POSITION,
    SUPPORT_STOP, ATTR_POSITION, PLATFORM_SCHEMA)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    CONF_HOST, CONF_PORT, CONF_NAME, CONF_ADDRESS, CONF_DEVICES)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['r2d7py==0.0.1']

_LOGGER = logging.getLogger(__name__)

CONF_UNIT = 'unit'
CONF_DURATION = 'duration'
CV_DURATION = vol.All(vol.Coerce(float), vol.Range(min=1., max=60.))

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_ADDRESS, default=1): cv.positive_int,
    vol.Required(CONF_UNIT): cv.positive_int,
    vol.Required(CONF_DURATION): CV_DURATION,
})
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.port,
    vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [DEVICE_SCHEMA])
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the r2d7 shade controller and shades."""
    from r2d7py.r2d7py import R2D7Hub

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    hub = R2D7Hub(host, port)

    devs = []
    for device in config.get(CONF_DEVICES):
        name = device.get(CONF_NAME)
        addr = device.get(CONF_ADDRESS)
        unit = device.get(CONF_UNIT)
        duration = device.get(CONF_DURATION)
        cover = hub.shade(addr, unit, duration)
        devs.append(R2D7Cover(cover, name))

    add_entities(devs, True)

    def cleanup(event):
        hub.close()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)
    return True


class R2D7Cover(CoverDevice):
    """Representation of an R2D7 controlled shade."""

    def __init__(self, cover, name):
        """Initialize the cover."""
        self._cover = cover
        self._name = name

    @property
    def name(self):
        """Device name."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return supported attributes."""
        return {"Addr": self._cover.addr,
                "Unit": self._cover.unit}

    @property
    def supported_features(self):
        """Flag supported features."""
        return (SUPPORT_OPEN | SUPPORT_CLOSE |
                SUPPORT_SET_POSITION | SUPPORT_STOP)

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._cover.position < 1

    @property
    def current_cover_position(self):
        """Return the current position of cover."""
        return self._cover.position

    def close_cover(self, **kwargs):
        """Close the cover."""
        self._cover.close()

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._cover.open()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._cover.stop()

    def set_cover_position(self, **kwargs):
        """Move the shade to a specific position."""
        if ATTR_POSITION in kwargs:
            self._cover.position = kwargs[ATTR_POSITION]

    @property
    def is_opening(self):
        """Is the cover opening."""
        return self._cover.is_opening

    @property
    def is_closing(self):
        """Is the cover closing."""
        return self._cover.is_closing

    def update(self):
        """Call when forcing a refresh of the device."""
        # FIX: Mark the device as non-polling
        pass
