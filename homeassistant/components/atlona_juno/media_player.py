"""Support for interfacing with Atlona Juno 451 HDMI 4x1 Switch."""
import logging

from pyatlonajuno.lib import Juno451
import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerDevice, PLATFORM_SCHEMA
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PROTOCOL,
    CONF_HOST,
    CONF_PORT,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Atlona Juno 451"
DEFAULT_PORT = 80
DEFAULT_PROTOCOL = "http"

DATA_ATLONAJUNO = "atlona_juno"

SUPPORT_ATLONAJUNO = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

CONF_SOURCES = "sources"
ATTR_SOURCE = "source"

# Valid source ids: 1-4
MEDIA_PLAYER_SCHEMA = vol.Schema({ATTR_ENTITY_ID: cv.comp_entity_ids})
SOURCE_IDS = vol.All(vol.Coerce(int), vol.Range(min=1, max=4))
SOURCE_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): cv.string,
        vol.Required(CONF_SOURCES): vol.Schema({SOURCE_IDS: SOURCE_SCHEMA}),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Atlona Juno 451 HDMI switch."""
    if DATA_ATLONAJUNO not in hass.data:
        hass.data[DATA_ATLONAJUNO] = {}

    url = "{}://{}:{}".format(
        config.get(CONF_PROTOCOL), config.get(CONF_HOST), config.get(CONF_PORT)
    )
    _LOGGER.debug("Composed URL for Atlona Juno %s", url)
    sources = {
        source_id: extra[CONF_NAME] for source_id, extra in config[CONF_SOURCES].items()
    }

    # As a device has one and only one IP address in our context, this qualiffies for uid
    unique_id = "{}-{}".format(DATA_ATLONAJUNO, config.get(CONF_HOST).replace(".", "_"))
    atlona_device = AtlonaJuno(config.get(CONF_NAME), unique_id, Juno451(url), sources)
    hass.data[DATA_ATLONAJUNO][unique_id] = atlona_device

    add_entities([atlona_device], True)


class AtlonaJuno(MediaPlayerDevice):
    """Representation of a Atlona Juno 451 HDMI switch."""

    def __init__(self, name, unique_id, atlona_device, sources):
        """Initialize."""
        self._name = name
        self._unique_id = unique_id
        self._atlona_device = atlona_device
        # dict source_id -> source name
        self._source_id_name = sources
        # dict source name -> source_id
        self._source_name_id = {v: k for k, v in sources.items()}
        # ordered list of all source names
        self._source_names = sorted(
            self._source_name_id.keys(), key=lambda v: self._source_name_id[v]
        )
        self._state = None
        self._source = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the on/off state of the device."""
        return self._state

    @property
    def source(self):
        """Return the current input source of the device."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    @property
    def supported_features(self):
        """Return supported features flag."""
        return SUPPORT_ATLONAJUNO

    @property
    def device_state_attributes(self):
        """Set device attributes."""
        attributes = {}
        attributes[ATTR_SOURCE] = self._source
        return attributes

    def turn_on(self):
        """Turn the power on."""
        self._state = STATE_ON
        self._atlona_device.setPowerState("on")
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn the power off."""
        self._state = STATE_OFF
        self._atlona_device.setPowerState("off")
        self.schedule_update_ha_state()

    def select_source(self, source):
        """Set input source."""
        if source not in self._source_name_id:
            return
        source_index = self._source_name_id[source]
        _LOGGER.debug("Setting input source to %s", source)
        self._atlona_device.setSource(source_index)

    def update(self):
        """Retrieve state."""
        self._state = self._atlona_device.getPowerState()
        source_index = self._atlona_device.getSource()
        if source_index in self._source_id_name:
            self._source = self._source_id_name[source_index]
        else:
            self._source = None
