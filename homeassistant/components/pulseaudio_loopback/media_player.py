"""Media player for PulseAudio loopback."""
from pulsectl import Pulse, PulseError, PulseVolumeInfo
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, STATE_OFF, STATE_ON
import homeassistant.helpers.config_validation as cv

DOMAIN = "pulseaudio_loopback"

CONF_SINK_NAME = "sink_name"
CONF_SOURCE_NAME = "source_name"
CONF_SOURCES = "sources"

DEFAULT_NAME = "paloopback"
DEFAULT_PORT = 4713

SOURCES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOURCE_NAME): cv.string,
        vol.Required(CONF_NAME, default=None): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SINK_NAME): cv.string,
        vol.Required(CONF_SOURCES): [SOURCES_SCHEMA],
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Pulse platform."""
    name = config.get(CONF_NAME)
    sources = config.get(CONF_SOURCES)
    sink_name = config.get(CONF_SINK_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    hass.data.setdefault(DOMAIN, {})

    server_id = str.format("{0}:{1}", host, port)

    if host:
        connect_to_server = server_id
    else:
        connect_to_server = None

    if server_id in hass.data[DOMAIN]:
        server = hass.data[DOMAIN][server_id]
    else:
        server = Pulse(server=connect_to_server, connect=False, threading_lock=True)
        hass.data[DOMAIN][server_id] = server

    add_entities([PulseDevice(server, name, sink_name, sources)], True)


class PulseDevice(MediaPlayerEntity):
    """Representation of a PulseAudio loopback media player."""

    def __init__(self, pa_server, name, sink_name, sources):
        """Initialize the Pulse device."""
        self._pa_svr = pa_server
        self._name = name
        self._sink = None
        self._sink_name = sink_name
        self._sources = sources
        self._source_names = [s["name"] for s in self._sources]
        self._status = None
        self._current_source = None
        self._last_source = None

    @property
    def available(self):
        """Return true when connected to server."""
        return self._pa_svr.connected

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
        if self._sink:
            return self._sink.volume.value_flat

        return 0

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

    def select_source(self, source):
        """Choose a different available playlist and play it."""
        self.connect_source(source)

    def set_volume_level(self, volume):
        """Set volume of media player."""
        if self._sink:
            self._pa_svr.sink_volume_set(
                self._sink.index, PulseVolumeInfo(volume, len(self._sink.volume.values))
            )

    def mute_volume(self, mute):
        """Mute."""
        if self._sink:
            self._pa_svr.sink_mute(self._sink.index, mute)

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._sink and self._sink.mute == 1

    def turn_off(self):
        """Service to send the Pulse the command to stop playing."""
        self.connect_source(None)

    def turn_on(self):
        """Service to send the Pulse the command to start playing."""
        if self._last_source:
            self.connect_source(self._last_source)
        else:
            self.connect_source(self._sources[0]["name"])

    def _get_module_idx(self, sink_name, source_name):
        for module in self._pa_svr.module_list():
            if not module.name == "module-loopback":
                continue

            if f"sink={sink_name}" not in module.argument:
                continue

            if f"source={source_name}" not in module.argument:
                continue

            return module.index

    def update(self):
        """Get the latest details from the device."""
        try:
            self._pa_svr.connect()
            self._sink = [
                s for s in self._pa_svr.sink_list() if s.name == self._sink_name
            ][0]

            current_source = None

            for source in self._sources:
                idx = self._get_module_idx(self._sink_name, source["source_name"])
                if idx:
                    current_source = source["name"]
                    break

            self._current_source = current_source

            if current_source:
                self._last_source = current_source

        except PulseError:
            return None

    def connect_source(self, source_name):
        """Connect sink to source."""
        for source in self._sources:
            if source["name"] == source_name:
                self._pa_svr.module_load(
                    "module-loopback",
                    args=f'sink={self._sink_name} source={source["source_name"]}',
                )
                self._current_source = source["name"]
            else:
                idx = self._get_module_idx(self._sink_name, source["source_name"])

                if not idx:
                    continue

                self._pa_svr.module_unload(idx)

        self.schedule_update_ha_state()
