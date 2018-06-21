"""
Support for Yamaha Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.yamaha/
"""
import logging

import requests
import voluptuous as vol

from homeassistant.components.media_player import (
    DOMAIN, MEDIA_PLAYER_SCHEMA, MEDIA_TYPE_MUSIC, PLATFORM_SCHEMA,
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE, SUPPORT_STOP,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    MediaPlayerDevice)
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, STATE_IDLE, STATE_OFF, STATE_ON,
    STATE_PLAYING)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['rxv==0.5.1']

_LOGGER = logging.getLogger(__name__)

ATTR_ENABLED = 'enabled'
ATTR_PORT = 'port'

CONF_SOURCE_IGNORE = 'source_ignore'
CONF_SOURCE_NAMES = 'source_names'
CONF_ZONE_IGNORE = 'zone_ignore'
CONF_ZONE_NAMES = 'zone_names'

DATA_YAMAHA = 'yamaha_known_receivers'
DEFAULT_NAME = "Yamaha Receiver"

ENABLE_OUTPUT_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_ENABLED): cv.boolean,
    vol.Required(ATTR_PORT): cv.string,
})

SERVICE_ENABLE_OUTPUT = 'yamaha_enable_output'

SUPPORT_YAMAHA = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE | SUPPORT_PLAY

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_SOURCE_IGNORE, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_ZONE_IGNORE, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_SOURCE_NAMES, default={}): {cv.string: cv.string},
    vol.Optional(CONF_ZONE_NAMES, default={}): {cv.string: cv.string},
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Yamaha platform."""
    import rxv
    # Keep track of configured receivers so that we don't end up
    # discovering a receiver dynamically that we have static config
    # for. Map each device from its zone_id to an instance since
    # YamahaDevice is not hashable (thus not possible to add to a set).
    if hass.data.get(DATA_YAMAHA) is None:
        hass.data[DATA_YAMAHA] = {}

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    source_ignore = config.get(CONF_SOURCE_IGNORE)
    source_names = config.get(CONF_SOURCE_NAMES)
    zone_ignore = config.get(CONF_ZONE_IGNORE)
    zone_names = config.get(CONF_ZONE_NAMES)

    if discovery_info is not None:
        name = discovery_info.get('name')
        model = discovery_info.get('model_name')
        ctrl_url = discovery_info.get('control_url')
        desc_url = discovery_info.get('description_url')
        receivers = rxv.RXV(
            ctrl_url, model_name=model, friendly_name=name,
            unit_desc_url=desc_url).zone_controllers()
        _LOGGER.debug("Receivers: %s", receivers)
        # when we are dynamically discovered config is empty
        zone_ignore = []
    elif host is None:
        receivers = []
        for recv in rxv.find():
            receivers.extend(recv.zone_controllers())
    else:
        ctrl_url = "http://{}:80/YamahaRemoteControl/ctrl".format(host)
        receivers = rxv.RXV(ctrl_url, name).zone_controllers()

    devices = []
    for receiver in receivers:
        if receiver.zone in zone_ignore:
            continue

        device = YamahaDevice(
            name, receiver, source_ignore, source_names, zone_names)

        # Only add device if it's not already added
        if device.zone_id not in hass.data[DATA_YAMAHA]:
            hass.data[DATA_YAMAHA][device.zone_id] = device
            devices.append(device)
        else:
            _LOGGER.debug("Ignoring duplicate receiver: %s", name)

    def service_handler(service):
        """Handle for services."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)

        devices = [device for device in hass.data[DATA_YAMAHA].values()
                   if not entity_ids or device.entity_id in entity_ids]

        for device in devices:
            port = service.data[ATTR_PORT]
            enabled = service.data[ATTR_ENABLED]

            device.enable_output(port, enabled)
            device.schedule_update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_ENABLE_OUTPUT, service_handler,
        schema=ENABLE_OUTPUT_SCHEMA)

    add_devices(devices)


class YamahaDevice(MediaPlayerDevice):
    """Representation of a Yamaha device."""

    def __init__(
            self, name, receiver, source_ignore, source_names, zone_names):
        """Initialize the Yamaha Receiver."""
        self.receiver = receiver
        self._muted = False
        self._volume = 0
        self._pwstate = STATE_OFF
        self._current_source = None
        self._source_list = None
        self._source_ignore = source_ignore or []
        self._source_names = source_names or {}
        self._zone_names = zone_names or {}
        self._reverse_mapping = None
        self._playback_support = None
        self._is_playback_supported = False
        self._play_status = None
        self._name = name
        self._zone = receiver.zone

    def update(self):
        """Get the latest details from the device."""
        try:
            self._play_status = self.receiver.play_status()
        except requests.exceptions.ConnectionError:
            _LOGGER.info("Receiver is offline: %s", self._name)
            return

        if self.receiver.on:
            if self._play_status is None:
                self._pwstate = STATE_ON
            elif self._play_status.playing:
                self._pwstate = STATE_PLAYING
            else:
                self._pwstate = STATE_IDLE
        else:
            self._pwstate = STATE_OFF

        self._muted = self.receiver.mute
        self._volume = (self.receiver.volume / 100) + 1

        if self.source_list is None:
            self.build_source_list()

        current_source = self.receiver.input
        self._current_source = self._source_names.get(
            current_source, current_source)
        self._playback_support = self.receiver.get_playback_support()
        self._is_playback_supported = self.receiver.is_playback_supported(
            self._current_source)

    def build_source_list(self):
        """Build the source list."""
        self._reverse_mapping = {alias: source for source, alias in
                                 self._source_names.items()}

        self._source_list = sorted(
            self._source_names.get(source, source) for source in
            self.receiver.inputs()
            if source not in self._source_ignore)

    @property
    def name(self):
        """Return the name of the device."""
        name = self._name
        zone_name = self._zone_names.get(self._zone, self._zone)
        if zone_name != "Main_Zone":
            # Zone will be one of Main_Zone, Zone_2, Zone_3
            name += " " + zone_name.replace('_', ' ')
        return name

    @property
    def state(self):
        """Return the state of the device."""
        return self._pwstate

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def source(self):
        """Return the current input source."""
        return self._current_source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def zone_id(self):
        """Return a zone_id to ensure 1 media player per zone."""
        return '{0}:{1}'.format(self.receiver.ctrl_url, self._zone)

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        supported_features = SUPPORT_YAMAHA

        supports = self._playback_support
        mapping = {
            'play': (SUPPORT_PLAY | SUPPORT_PLAY_MEDIA),
            'pause': SUPPORT_PAUSE,
            'stop': SUPPORT_STOP,
            'skip_f': SUPPORT_NEXT_TRACK,
            'skip_r': SUPPORT_PREVIOUS_TRACK,
        }
        for attr, feature in mapping.items():
            if getattr(supports, attr, False):
                supported_features |= feature
        return supported_features

    def turn_off(self):
        """Turn off media player."""
        self.receiver.on = False

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        receiver_vol = 100 - (volume * 100)
        negative_receiver_vol = -receiver_vol
        self.receiver.volume = negative_receiver_vol

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self.receiver.mute = mute

    def turn_on(self):
        """Turn the media player on."""
        self.receiver.on = True
        self._volume = (self.receiver.volume / 100) + 1

    def media_play(self):
        """Send play command."""
        self._call_playback_function(self.receiver.play, "play")

    def media_pause(self):
        """Send pause command."""
        self._call_playback_function(self.receiver.pause, "pause")

    def media_stop(self):
        """Send stop command."""
        self._call_playback_function(self.receiver.stop, "stop")

    def media_previous_track(self):
        """Send previous track command."""
        self._call_playback_function(self.receiver.previous, "previous track")

    def media_next_track(self):
        """Send next track command."""
        self._call_playback_function(self.receiver.next, "next track")

    def _call_playback_function(self, function, function_text):
        import rxv
        try:
            function()
        except rxv.exceptions.ResponseException:
            _LOGGER.warning(
                "Failed to execute %s on %s", function_text, self._name)

    def select_source(self, source):
        """Select input source."""
        self.receiver.input = self._reverse_mapping.get(source, source)

    def play_media(self, media_type, media_id, **kwargs):
        """Play media from an ID.

        This exposes a pass through for various input sources in the
        Yamaha to direct play certain kinds of media. media_type is
        treated as the input type that we are setting, and media id is
        specific to it.

        For the NET RADIO mediatype the format for ``media_id`` is a
        "path" in your vtuner hierarchy. For instance:
        ``Bookmarks>Internet>Radio Paradise``. The separators are
        ``>`` and the parts of this are navigated by name behind the
        scenes. There is a looping construct built into the yamaha
        library to do this with a fallback timeout if the vtuner
        service is unresponsive.

        NOTE: this might take a while, because the only API interface
        for setting the net radio station emulates button pressing and
        navigating through the net radio menu hierarchy. And each sub
        menu must be fetched by the receiver from the vtuner service.

        """
        if media_type == "NET RADIO":
            self.receiver.net_radio(media_id)

    def enable_output(self, port, enabled):
        """Enable or disable an output port.."""
        self.receiver.enable_output(port, enabled)

    @property
    def media_artist(self):
        """Artist of current playing media."""
        if self._play_status is not None:
            return self._play_status.artist

    @property
    def media_album_name(self):
        """Album of current playing media."""
        if self._play_status is not None:
            return self._play_status.album

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        # Loose assumption that if playback is supported, we are playing music
        if self._is_playback_supported:
            return MEDIA_TYPE_MUSIC
        return None

    @property
    def media_title(self):
        """Artist of current playing media."""
        if self._play_status is not None:
            song = self._play_status.song
            station = self._play_status.station

            # If both song and station is available, print both, otherwise
            # just the one we have.
            if song and station:
                return '{}: {}'.format(station, song)

            return song or station
