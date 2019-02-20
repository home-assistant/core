"""
Provide animated GIF loops of BOM radar imagery.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/bomradarcam/
"""

import logging

import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.helpers import config_validation as cv

REQUIREMENTS = ['bomradarloop==0.1.2']

CONF_DELTA = 'delta'
CONF_FRAMES = 'frames'
CONF_ID = 'id'
CONF_LOC = 'location'
CONF_NAME = 'name'
CONF_OUTFILE = 'filename'
LOGGER = logging.getLogger(__name__)


def _validate_schema(config):
    if config.get('location'):
        if config.get('id'):
            raise vol.Invalid("Specify either 'id' or 'location', not both")
    else:
        reqs = (config.get('id'), config.get('delta'), config.get('frames'))
        if not all(reqs):
            raise vol.Invalid("Specify 'id', 'delta' and 'frames' when"
                              " 'location' is unspecified")
    return config


PLATFORM_SCHEMA = vol.All(PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DELTA): cv.positive_int,
    vol.Optional(CONF_OUTFILE): cv.string,
    vol.Optional(CONF_FRAMES): cv.positive_int,
    vol.Optional(CONF_ID): cv.string,
    vol.Optional(CONF_LOC): cv.string,
    vol.Optional(CONF_NAME): cv.string,
}), _validate_schema)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up BOM radar-loop camera component."""
    location = config.get(CONF_LOC) or "ID {}".format(config.get(CONF_ID))
    name = config.get(CONF_NAME) or "BOM Radar Loop - {}".format(location)
    args = [config.get(x) for x in (CONF_LOC, CONF_ID, CONF_DELTA, CONF_FRAMES,
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
