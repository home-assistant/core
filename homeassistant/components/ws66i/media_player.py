"""Support for interfacing with WS66i 6 zone home audio controller."""
import logging

from homeassistant import core
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import CONF_IP_ADDRESS, STATE_OFF, STATE_ON
from homeassistant.helpers import entity_platform

from .const import CONF_SOURCES, DOMAIN, SERVICE_RESTORE, SERVICE_SNAPSHOT, WS66I_OBJECT

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

SUPPORT_WS66I = (
    SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
)


@core.callback
def _get_sources_from_dict(data):
    sources_config = data[CONF_SOURCES]

    source_id_name = {int(index): name for index, name in sources_config.items()}

    source_name_id = {v: k for k, v in source_id_name.items()}

    source_names = sorted(source_name_id.keys(), key=lambda v: source_name_id[v])

    return [source_id_name, source_name_id, source_names]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the WS66i 6-zone amplifier platform."""
    ip_addr = config_entry.data[CONF_IP_ADDRESS]
    ws66i = hass.data[DOMAIN][config_entry.entry_id][WS66I_OBJECT]
    sources = _get_sources_from_dict(config_entry.options)

    # Build the entities that control each of the zones.
    # Zones 11 - 16 are the master amp
    # Zones 21,31 - 26,36 are the daisy-chained amps
    entities = []
    for i in range(1, 4):

        if i > 1:
            # Don't add entities that aren't present
            status = await hass.async_add_executor_job(ws66i.zone_status, (i * 10 + 1))
            if status is None:
                break

        _LOGGER.info("Detected amp %d at ip %s", i, ip_addr)
        for j in range(1, 7):
            zone_id = (i * 10) + j
            entities.append(Ws66iZone(ws66i, sources, config_entry.entry_id, zone_id))

    async_add_entities(entities)

    # Set up services
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SNAPSHOT,
        {},
        "snapshot",
    )

    platform.async_register_entity_service(
        SERVICE_RESTORE,
        {},
        "restore",
    )


class Ws66iZone(MediaPlayerEntity):
    """Representation of a WS66i amplifier zone."""

    def __init__(self, ws66i, sources, namespace, zone_id):
        """Initialize new zone."""
        self._ws66i = ws66i
        # dict source_id -> source name
        self._source_id_name = sources[0]
        # dict source name -> source_id
        self._source_name_id = sources[1]
        # ordered list of all source names
        self._source_names = sources[2]
        self._zone_id = zone_id
        self._attr_unique_id = f"{namespace}_{self._zone_id}"
        self._attr_name = f"Zone {self._zone_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Soundavo",
            "model": "WS66i 6-Zone Amplifier",
        }

        self._snapshot = None
        self._state = None
        self._volume = None
        self._source = None
        self._mute = None

    def update(self):
        """Retrieve latest state."""
        new_state = self._ws66i.zone_status(self._zone_id)
        if not new_state:
            _LOGGER.debug("Zone %d was not detected", self._zone_id)
            return

        # successfully retrieved zone state
        self._state = STATE_ON if new_state.power else STATE_OFF
        self._volume = new_state.volume
        self._mute = new_state.mute
        idx = new_state.source
        if idx in self._source_id_name:
            self._source = self._source_id_name[idx]
        else:
            self._source = None

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    @property
    def state(self):
        """Return the state of the zone."""
        return self._state

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._volume is None:
            return None
        return self._volume / 38.0

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    @property
    def supported_features(self):
        """Return flag of media commands that are supported."""
        return SUPPORT_WS66I

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
        self._snapshot = self._ws66i.zone_status(self._zone_id)

    def restore(self):
        """Restore saved state."""
        if self._snapshot:
            self._ws66i.restore_zone(self._snapshot)
            self.schedule_update_ha_state(True)

    def select_source(self, source):
        """Set input source."""
        if source not in self._source_name_id:
            return
        idx = self._source_name_id[source]
        self._ws66i.set_source(self._zone_id, idx)

    def turn_on(self):
        """Turn the media player on."""
        self._ws66i.set_power(self._zone_id, True)

    def turn_off(self):
        """Turn the media player off."""
        self._ws66i.set_power(self._zone_id, False)

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self._ws66i.set_mute(self._zone_id, mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._ws66i.set_volume(self._zone_id, int(volume * 38))

    def volume_up(self):
        """Volume up the media player."""
        if self._volume is None:
            return
        self._ws66i.set_volume(self._zone_id, min(self._volume + 1, 38))

    def volume_down(self):
        """Volume down media player."""
        if self._volume is None:
            return
        self._ws66i.set_volume(self._zone_id, max(self._volume - 1, 0))
