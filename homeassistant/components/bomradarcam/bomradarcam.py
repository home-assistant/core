"""
Provide animated GIF loops of BOM radar imagery.
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_ID, CONF_NAME
from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.helpers import config_validation as cv

REQUIREMENTS = ['bomradarloop==0.1.2']

CONF_DELTA = 'delta'
CONF_FRAMES = 'frames'
CONF_LOCATION = 'location'
CONF_OUTFILE = 'filename'
LOGGER = logging.getLogger(__name__)


def _validate_schema(config):
    if config.get(CONF_LOCATION) is None:
        if not all((config.get(CONF_ID), config.get(CONF_DELTA),
                    config.get(CONF_FRAMES))):
            raise vol.Invalid(
                "Specify '{}', '{}' and '{}' when '{}' is unspecified".format(
                    CONF_ID, CONF_DELTA, CONF_FRAMES, CONF_LOCATION))
    return config


PLATFORM_SCHEMA = vol.All(PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DELTA): cv.positive_int,
    vol.Optional(CONF_OUTFILE): cv.string,
    vol.Optional(CONF_FRAMES): cv.positive_int,
    vol.Optional(CONF_ID): cv.string,
    vol.Optional(CONF_LOCATION): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Exclusive(CONF_ID, CONF_LOCATION,
                  msg="Specify either '{}' or '{}', not both".format(
                      CONF_ID, CONF_LOCATION))
}), _validate_schema)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up BOM radar-loop camera component."""
    location = config.get(CONF_LOCATION) or "ID {}".format(config.get(CONF_ID))
    name = config.get(CONF_NAME) or "BOM Radar Loop - {}".format(location)
    args = [config.get(x) for x in (CONF_LOCATION, CONF_ID, CONF_DELTA, CONF_FRAMES,
                                    CONF_OUTFILE)]
    add_devices([BOMRadarCam(hass, name, *args)])


class BOMRadarCam(Camera):
    """A camera component producing animated BOM radar-imagery GIFs."""

    def __init__(self, hass, name, location, radar_id, delta, frames, outfile):
        """Initialize the component."""
        from bomradarloop import BOMRadarLoop
        super().__init__()
        self._name = name
        self._cam = BOMRadarLoop(location, radar_id, delta, frames, outfile,
                                 LOGGER)

    def camera_image(self):
        """Return the current BOM radar-loop image."""
        return self._cam.current

    @property
    def name(self):
        """Return the component name."""
        return self._name
