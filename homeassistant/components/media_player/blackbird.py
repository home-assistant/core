"""
Support for interfacing with Monoprice Blackbird 4k 8x8 HDBaseT Matrix.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.blackbird
"""
import logging
import socket

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, MEDIA_PLAYER_SCHEMA, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    DOMAIN, SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON)
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE, STATE_OFF,
    STATE_ON)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyblackbird==0.5']

_LOGGER = logging.getLogger(__name__)

SUPPORT_BLACKBIRD = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
})

SOURCE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
})

CONF_ZONES = 'zones'
CONF_SOURCES = 'sources'

DATA_BLACKBIRD = 'blackbird'

SERVICE_SETALLZONES = 'blackbird_set_all_zones'
ATTR_SOURCE = 'source'

BLACKBIRD_SETALLZONES_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_SOURCE): cv.string
})


# Valid zone ids: 1-8
ZONE_IDS = vol.All(vol.Coerce(int), vol.Range(min=1, max=8))

# Valid source ids: 1-8
SOURCE_IDS = vol.All(vol.Coerce(int), vol.Range(min=1, max=8))

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_PORT, CONF_HOST),
    PLATFORM_SCHEMA.extend({
        vol.Exclusive(CONF_PORT, CONF_TYPE): cv.string,
        vol.Exclusive(CONF_HOST, CONF_TYPE): cv.string,
        vol.Required(CONF_ZONES): vol.Schema({ZONE_IDS: ZONE_SCHEMA}),
        vol.Required(CONF_SOURCES): vol.Schema({SOURCE_IDS: SOURCE_SCHEMA}),
    }))


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Monoprice Blackbird 4k 8x8 HDBaseT Matrix platform."""
    if DATA_BLACKBIRD not in hass.data:
        hass.data[DATA_BLACKBIRD] = {}

    port = config.get(CONF_PORT)
    host = config.get(CONF_HOST)

    from pyblackbird import get_blackbird
    from serial import SerialException

    connection = None
    if port is not None:
        try:
            blackbird = get_blackbird(port)
            connection = port
        except SerialException:
            _LOGGER.error("Error connecting to the Blackbird controller")
            return

    if host is not None:
        try:
            blackbird = get_blackbird(host, False)
            connection = host
        except socket.timeout:
            _LOGGER.error("Error connecting to the Blackbird controller")
            return

    sources = {source_id: extra[CONF_NAME] for source_id, extra
               in config[CONF_SOURCES].items()}

    devices = []
    for zone_id, extra in config[CONF_ZONES].items():
        _LOGGER.info("Adding zone %d - %s", zone_id, extra[CONF_NAME])
        unique_id = "{}-{}".format(connection, zone_id)
        device = BlackbirdZone(blackbird, sources, zone_id, extra[CONF_NAME])
        hass.data[DATA_BLACKBIRD][unique_id] = device
        devices.append(device)

    add_entities(devices, True)

    def service_handle(service):
        """Handle for services."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        source = service.data.get(ATTR_SOURCE)
        if entity_ids:
            devices = [device for device in hass.data[DATA_BLACKBIRD].values()
                       if device.entity_id in entity_ids]

        else:
            devices = hass.data[DATA_BLACKBIRD].values()

        for device in devices:
            if service.service == SERVICE_SETALLZONES:
                device.set_all_zones(source)

    hass.services.register(DOMAIN, SERVICE_SETALLZONES, service_handle,
                           schema=BLACKBIRD_SETALLZONES_SCHEMA)


class BlackbirdZone(MediaPlayerDevice):
    """Representation of a Blackbird matrix zone."""

    def __init__(self, blackbird, sources, zone_id, zone_name):
        """Initialize new zone."""
        self._blackbird = blackbird
        # dict source_id -> source name
        self._source_id_name = sources
        # dict source name -> source_id
        self._source_name_id = {v: k for k, v in sources.items()}
        # ordered list of all source names
        self._source_names = sorted(self._source_name_id.keys(),
                                    key=lambda v: self._source_name_id[v])
        self._zone_id = zone_id
        self._name = zone_name
        self._state = None
        self._source = None

    def update(self):
        """Retrieve latest state."""
        state = self._blackbird.zone_status(self._zone_id)
        if not state:
            return
        self._state = STATE_ON if state.power else STATE_OFF
        idx = state.av
        if idx in self._source_id_name:
            self._source = self._source_id_name[idx]
        else:
            self._source = None

    @property
    def name(self):
        """Return the name of the zone."""
        return self._name

    @property
    def state(self):
        """Return the state of the zone."""
        return self._state

    @property
    def supported_features(self):
        """Return flag of media commands that are supported."""
        return SUPPORT_BLACKBIRD

    @property
    def media_title(self):
        """Return the current source as media title."""
        return self._source

    @property
    def source(self):
        """Return the current input source of the device."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    def set_all_zones(self, source):
        """Set all zones to one source."""
        if source not in self._source_name_id:
            return
        idx = self._source_name_id[source]
        _LOGGER.debug("Setting all zones source to %s", idx)
        self._blackbird.set_all_zone_source(idx)

    def select_source(self, source):
        """Set input source."""
        if source not in self._source_name_id:
            return
        idx = self._source_name_id[source]
        _LOGGER.debug("Setting zone %d source to %s", self._zone_id, idx)
        self._blackbird.set_zone_source(self._zone_id, idx)

    def turn_on(self):
        """Turn the media player on."""
        _LOGGER.debug("Turning zone %d on", self._zone_id)
        self._blackbird.set_zone_power(self._zone_id, True)

    def turn_off(self):
        """Turn the media player off."""
        _LOGGER.debug("Turning zone %d off", self._zone_id)
        self._blackbird.set_zone_power(self._zone_id, False)
