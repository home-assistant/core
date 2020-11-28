"""Support to interact with a Music Player Daemon."""
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

from . import get_pulse_interface
from .const import CONF_MEDIAPLAYER_SINKS, CONF_MEDIAPLAYER_SOURCES, CONF_SERVER, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the DenonAVR receiver from a config entry."""
    entities = []

    sinks = config_entry.options.get(CONF_MEDIAPLAYER_SINKS)
    sources = config_entry.options.get(CONF_MEDIAPLAYER_SOURCES)
    server = hass.data[DOMAIN][config_entry.entry_id][CONF_SERVER]
    interface = get_pulse_interface(hass, server)

    if sinks:
        for sink in sinks:
            entities.append(PulseDevice(server, interface, sink, sink, sources))

        async_add_entities(entities)


class PulseDevice(MediaPlayerEntity):
    """Representation of a Pulse server."""

    # pylint: disable=no-member
    def __init__(self, server, interface, name, sink_name, sources):
        """Initialize the Pulse device."""
        self._server = server
        self._name = name
        self._sink = None
        self._sink_name = sink_name
        self._source_names = sources
        self._status = None
        self._current_source = None
        self._last_source = None
        self._interface = interface
        self._volume = 0.0
        self._muted = False

    @property
    def unique_id(self):
        """Return the unique id of the zone."""
        return f"{self._server}-{self._sink_name}"

    @property
    def available(self):
        """Return true when connected to server."""
        return self._sink and self._interface.connected

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._current_source:
            return STATE_ON
        return STATE_OFF

    @property
    def volume_level(self):
        """Return the volume level."""
        return self._volume

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return (
            SUPPORT_VOLUME_SET
            | SUPPORT_VOLUME_STEP
            | SUPPORT_VOLUME_MUTE
            | SUPPORT_SELECT_SOURCE
            | SUPPORT_TURN_OFF
            | SUPPORT_TURN_ON
        )

    @property
    def media_title(self):
        """Return the content ID of current playing media."""
        return self._current_source

    @property
    def source(self):
        """Name of the current input source."""
        return self._current_source

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return self._source_names

    async def async_select_source(self, source):
        """Choose a different available playlist and play it."""
        self._current_source = source
        self.async_schedule_update_ha_state()
        await self._interface.async_connect_source(
            self._sink, source, self._source_names
        )

    async def async_set_volume_level(self, volume):
        """Set volume of media player."""
        self._volume = volume
        await self._interface.async_sink_volume_set(self._sink, volume)
        self.async_schedule_update_ha_state()

    async def async_mute_volume(self, mute):
        """Mute."""
        self._muted = True
        await self._interface.async_sink_mute(self._sink, mute)
        self.async_schedule_update_ha_state()

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    async def async_turn_off(self):
        """Service to send the Pulse the command to stop playing."""
        await self._interface.async_connect_source(self._sink, None, self._source_names)

    async def async_turn_on(self):
        """Service to send the Pulse the command to start playing."""

        if self._current_source is not None:
            return

        if self._last_source:
            source = self._last_source
        else:
            source = self._source_names[0]

        await self._interface.async_connect_source(
            self._sink, source, self._source_names
        )

    async def async_update(self):
        """Update internal status of the entity."""
        self._sink = self._interface.get_sink_by_name(self._sink_name)

        if self._sink:
            self._current_source = self._interface.get_connected_source(
                self._sink, self._source_names
            )
            if self._current_source:
                self._last_source = self._current_source

            self._volume = self._sink.volume.value_flat
            self._muted = self._sink.mute == 1
