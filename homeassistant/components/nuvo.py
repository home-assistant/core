
import logging

import voluptuous as vol

# Import the device class from home assistant component
from homeassistant.components.media_player import (
    DOMAIN, MEDIA_PLAYER_SCHEMA, PLATFORM_SCHEMA, SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP, MediaPlayerDevice)
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_NAME, CONF_PORT, STATE_OFF, STATE_ON)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

# Home Assistant depends on 3rd party packages for API specific code.
REQUIREMENTS = ['pynuvo==0.1']

_LOGGER = logging.getLogger(__name__)
#logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

SUPPORT_NUVO = SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | \
                    SUPPORT_VOLUME_STEP | SUPPORT_TURN_ON | \
                    SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
})

SOURCE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
})

CONF_ZONES = 'zones'
CONF_SOURCES = 'sources'

DATA_NUVO = 'nuvo'

SERVICE_SNAPSHOT = 'snapshot'
SERVICE_RESTORE = 'restore'

# Valid zone ids: 1-12
ZONE_IDS = vol.All(vol.Coerce(int), vol.Any(
    vol.Range(min=1, max=12)))

# Valid source ids: 1-6
SOURCE_IDS = vol.All(vol.Coerce(int), vol.Range(min=1, max=6))

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PORT): cv.string,
    vol.Required(CONF_ZONES): vol.Schema({ZONE_IDS: ZONE_SCHEMA}),
    vol.Required(CONF_SOURCES): vol.Schema({SOURCE_IDS: SOURCE_SCHEMA}),
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Nuvo multi zone amplifier platform."""
    port = config.get(CONF_PORT)

    from serial import SerialException
    from pynuvo import get_nuvo
    try:
        nuvo = get_nuvo(port)
    except SerialException:
        _LOGGER.error("Error connecting to Nuvo controller")
        return

    sources = {source_id: extra[CONF_NAME] for source_id, extra
               in config[CONF_SOURCES].items()}

    hass.data[DATA_NUVO] = []
    for zone_id, extra in config[CONF_ZONES].items():
        _LOGGER.info("Adding zone %d - %s", zone_id, extra[CONF_NAME])
        hass.data[DATA_NUVO].append(NuvoZone(
            nuvo, sources, zone_id, extra[CONF_NAME]))

    add_entities(hass.data[DATA_NUVO], True)

    def service_handle(service):
        """Handle for services."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)

        if entity_ids:
            devices = [device for device in hass.data[DATA_NUVO]
                       if device.entity_id in entity_ids]
        else:
            devices = hass.data[DATA_NUVO]

        for device in devices:
            if service.service == SERVICE_SNAPSHOT:
                device.snapshot()
            elif service.service == SERVICE_RESTORE:
                device.restore()

    hass.services.register(
        DOMAIN, SERVICE_SNAPSHOT, service_handle, schema=MEDIA_PLAYER_SCHEMA)

    hass.services.register(
        DOMAIN, SERVICE_RESTORE, service_handle, schema=MEDIA_PLAYER_SCHEMA)



def async_trigger(vars, boolMaybe):
    """ Incoming Message Listener """
    _LOGGER.debug("Async Trigger: %s", vars)
 

callback
def async_trigger_service_handler(service_call):
    """Handle automation trigger service calls."""
    vars = service_call.data.get(ATTR_VARIABLES)
    for entity in component.async_extract_from_service(service_call):
        hass.loop.create_task(entity.async_trigger(vars, True))


class NuvoZone(MediaPlayerDevice):
    """Representation of a Nuvo amplifier zone."""

    def __init__(self, nuvo, sources, zone_id, zone_name):
        """Initialize new zone."""
        self._nuvo = nuvo
        # dict source_id -> source name
        self._source_id_name = sources
        # dict source name -> source_id
        self._source_name_id = {v: k for k, v in sources.items()}
        # ordered list of all source names
        self._source_names = sorted(self._source_name_id.keys(),
                                    key=lambda v: self._source_name_id[v])
        self._zone_id = zone_id
        self._name = zone_name

        self._snapshot = None
        self._state = None
        self._volume = None
        self._source = None
        self._mute = None

    def update(self):
        """Retrieve latest state."""
        state = self._nuvo.zone_status(self._zone_id)
        if not state:
            return False
        self._state = STATE_ON if state.power else STATE_OFF
        self._volume = state.volume
        self._mute = state.mute
        idx = state.source
        if idx in self._source_id_name:
            self._source = self._source_id_name[idx]
        else:
            self._source = None
        return True

    @property
    def name(self):
        """Return the name of the zone."""
        return self._name

    @property
    def state(self):
        """Return the state of the zone."""
        return self._state

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._volume is None:
            return None
        return (( int(self._volume) + 78) / 78)

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    @property
    def supported_features(self):
        """Return flag of media commands that are supported."""
        return SUPPORT_NUVO

    @property
    def media_title(self):
        """Return the current source as medial title."""
        return self._source

    @property
    def source(self):
        """Return the current input source of the device."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    def snapshot(self):
        """Save zone's current state."""
        self._snapshot = self._nuvo.zone_status(self._zone_id)

    def restore(self):
        """Restore saved state."""
        if self._snapshot:
            self._nuvo.restore_zone(self._snapshot)
            self.schedule_update_ha_state(True)

    def select_source(self, source):
        """Set input source."""
        if source not in self._source_name_id:
            return
        idx = self._source_name_id[source]
        self._nuvo.set_source(self._zone_id, idx)

    def turn_on(self):
        """Turn the media player on."""
        self._nuvo.set_power(self._zone_id, True)

    def turn_off(self):
        """Turn the media player off."""
        self._nuvo.set_power(self._zone_id, False)

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self._nuvo.set_mute(self._zone_id, mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._nuvo.set_volume(self._zone_id, int( (volume * 78) - 78) )

    def volume_up(self):
        """Volume up the media player."""
        if self._volume is None:
            return
        self._nuvo.set_volume(self._zone_id, min(self._volume + 1, 0))

    def volume_down(self):
        """Volume down media player."""
        if self._volume is None:
            return
        self._nuvo.set_volume(self._zone_id, max(self._volume - 1, -78))


