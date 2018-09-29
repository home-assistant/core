"""
Support for Openhome Devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.openhome/
"""
import logging

from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP,
    MediaPlayerDevice)
from homeassistant.const import (
    STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING)

REQUIREMENTS = ['openhomedevice==0.4.2']

SUPPORT_OPENHOME = SUPPORT_SELECT_SOURCE | \
    SUPPORT_VOLUME_STEP | SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | \
    SUPPORT_TURN_OFF | SUPPORT_TURN_ON

_LOGGER = logging.getLogger(__name__)

DEVICES = []


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Openhome platform."""
    from openhomedevice.Device import Device

    if not discovery_info:
        return True

    name = discovery_info.get('name')
    description = discovery_info.get('ssdp_description')
    _LOGGER.info("Openhome device found: %s", name)
    device = Device(description)

    # if device has already been discovered
    if device.Uuid() in [x.unique_id for x in DEVICES]:
        return True

    device = OpenhomeDevice(hass, device)

    add_entities([device], True)
    DEVICES.append(device)

    return True


class OpenhomeDevice(MediaPlayerDevice):
    """Representation of an Openhome device."""

    def __init__(self, hass, device):
        """Initialise the Openhome device."""
        self.hass = hass
        self._device = device
        self._track_information = {}
        self._in_standby = None
        self._transport_state = None
        self._volume_level = None
        self._volume_muted = None
        self._supported_features = SUPPORT_OPENHOME
        self._source_names = list()
        self._source_index = {}
        self._source = {}
        self._name = None
        self._state = STATE_PLAYING

    def update(self):
        """Update state of device."""
        self._in_standby = self._device.IsInStandby()
        self._transport_state = self._device.TransportState()
        self._track_information = self._device.TrackInfo()
        self._volume_level = self._device.VolumeLevel()
        self._volume_muted = self._device.IsMuted()
        self._source = self._device.Source()
        self._name = self._device.Room().decode('utf-8')
        self._supported_features = SUPPORT_OPENHOME
        source_index = {}
        source_names = list()

        for source in self._device.Sources():
            source_names.append(source["name"])
            source_index[source["name"]] = source["index"]

        self._source_index = source_index
        self._source_names = source_names

        if self._source["type"] == "Radio":
            self._supported_features |= SUPPORT_STOP | SUPPORT_PLAY
        if self._source["type"] in ("Playlist", "Cloud"):
            self._supported_features |= SUPPORT_PREVIOUS_TRACK | \
                SUPPORT_NEXT_TRACK | SUPPORT_PAUSE | SUPPORT_PLAY

        if self._in_standby:
            self._state = STATE_OFF
        elif self._transport_state == 'Paused':
            self._state = STATE_PAUSED
        elif self._transport_state in ('Playing', 'Buffering'):
            self._state = STATE_PLAYING
        elif self._transport_state == 'Stopped':
            self._state = STATE_IDLE
        else:
            # Device is playing an external source with no transport controls
            self._state = STATE_PLAYING

    def turn_on(self):
        """Bring device out of standby."""
        self._device.SetStandby(False)

    def turn_off(self):
        """Put device in standby."""
        self._device.SetStandby(True)

    def media_pause(self):
        """Send pause command."""
        self._device.Pause()

    def media_stop(self):
        """Send stop command."""
        self._device.Stop()

    def media_play(self):
        """Send play command."""
        self._device.Play()

    def media_next_track(self):
        """Send next track command."""
        self._device.Skip(1)

    def media_previous_track(self):
        """Send previous track command."""
        self._device.Skip(-1)

    def select_source(self, source):
        """Select input source."""
        self._device.SetSource(self._source_index[source])

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def supported_features(self):
        """Flag of features commands that are supported."""
        return self._supported_features

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._device.Uuid()

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._track_information.get('albumArtwork')

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        artists = self._track_information.get('artist')
        if artists:
            return artists[0]

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._track_information.get('albumTitle')

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._track_information.get('title')

    @property
    def source(self):
        """Name of the current input source."""
        return self._source.get('name')

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume_level / 100.0

    @property
    def is_volume_muted(self):
        """Return true if volume is muted."""
        return self._volume_muted

    def volume_up(self):
        """Volume up media player."""
        self._device.IncreaseVolume()

    def volume_down(self):
        """Volume down media player."""
        self._device.DecreaseVolume()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._device.SetVolumeLevel(int(volume * 100))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self._device.SetMute(mute)
