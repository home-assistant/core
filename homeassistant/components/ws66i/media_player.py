"""Support for interfacing with WS66i 6 zone home audio controller."""
from datetime import timedelta
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
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.entity_platform import async_get_current_platform

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

SCAN_INTERVAL = timedelta(seconds=30)


@core.callback
def _get_sources_from_dict(data):
    sources_config = data[CONF_SOURCES]

    # Dict index to custom name
    source_id_name = {int(index): name for index, name in sources_config.items()}

    # Dict custom name to index
    source_name_id = {v: k for k, v in source_id_name.items()}

    # List of custom names
    source_names = sorted(source_name_id.keys(), key=lambda v: source_name_id[v])

    return [source_id_name, source_name_id, source_names]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the WS66i 6-zone amplifier platform."""
    ws66i = hass.data[DOMAIN][config_entry.entry_id][WS66I_OBJECT]
    sources = _get_sources_from_dict(config_entry.options)

    # Build the entities that control each of the zones.
    # Zones 11 - 16 are the master amp
    # Zones 21,31 - 26,36 are the daisy-chained amps
    async def _async_generate_entities(ws66i, sources) -> list:
        """Generate zone entities by searching for presence of zones."""
        entities = []
        for amp_num in range(1, 4):

            if amp_num > 1:
                # Don't add entities that aren't present
                status = await hass.async_add_executor_job(
                    ws66i.zone_status, (amp_num * 10 + 1)
                )
                if status is None:
                    break

            for zone_num in range(1, 7):
                zone_id = (amp_num * 10) + zone_num
                entities.append(
                    Ws66iZone(ws66i, sources, config_entry.entry_id, zone_id)
                )

        _LOGGER.info("Detected %d amp(s)", amp_num - 1)
        return entities

    # Generate a list of entities to add to HA
    entities = await _async_generate_entities(ws66i, sources)

    # Add them to HA
    async_add_entities(entities)

    # Set up services
    platform = async_get_current_platform()

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

    def __init__(self, ws66i, sources, entry_id, zone_id):
        """Initialize new zone."""
        self._ws66i = ws66i
        self._zone_id = zone_id
        # dict source_id -> source name
        self._source_id_name = sources[0]
        # dict source name -> source_id
        self._source_name_id = sources[1]
        # ordered list of all source names
        self._attr_source_list = sources[2]
        self._attr_unique_id = f"{entry_id}_{self._zone_id}"
        self._attr_name = f"Zone {self._zone_id}"
        self._attr_supported_features = SUPPORT_WS66I
        self._attr_available = True
        self._attr_should_poll = True
        self._attr_is_volume_muted = None
        self._attr_source = None
        self._attr_state = None
        self._attr_media_title = None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Soundavo",
            "model": "WS66i 6-Zone Amplifier",
        }

        self._snapshot = None
        self._volume = None

    def update(self):
        """Retrieve latest state."""
        new_state = self._ws66i.zone_status(self._zone_id)
        if not new_state:
            # End-user should turn on Amp and reload integration
            _LOGGER.warning(
                "Zone %d not detected. Check WS66i power and reload integration",
                self._zone_id,
            )
            self._attr_available = False
            self._attr_should_poll = False
            return

        # successfully retrieved zone state
        self._attr_state = STATE_ON if new_state.power else STATE_OFF
        self._volume = new_state.volume
        self._attr_is_volume_muted = new_state.mute
        idx = new_state.source
        if idx in self._source_id_name:
            self._attr_source = self._source_id_name[idx]
            self._attr_media_title = self._source_id_name[idx]
        else:
            self._attr_source = None
            self._attr_media_title = None

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._volume is None:
            return None
        return self._volume / 38.0

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
