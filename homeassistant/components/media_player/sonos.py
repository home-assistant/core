"""
homeassistant.components.media_player.sonos
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides an interface to Sonos players (via SoCo)

Configuration:

To use SoCo, add something like this to your configuration:

media_player:
  platform: sonos
"""

import logging
import datetime

REQUIREMENTS = ['SoCo==0.11.1']

from homeassistant.components.media_player import (
    MediaPlayerDevice, SUPPORT_PAUSE, SUPPORT_SEEK, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_MUTE, SUPPORT_PREVIOUS_TRACK, SUPPORT_NEXT_TRACK,
    MEDIA_TYPE_MUSIC)

from homeassistant.const import (
    STATE_IDLE, STATE_PLAYING, STATE_PAUSED, STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)

SUPPORT_SONOS = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE |\
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | SUPPORT_SEEK


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Sonos platform. """

    import soco
    add_devices(SonosDevice(p) for p in soco.discover())

    return True


# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-public-methods
class SonosDevice(MediaPlayerDevice):
    """ Represents a Sonos device. """

    # pylint: disable=too-many-arguments
    def __init__(self, player):
        super(SonosDevice, self).__init__()
        self._player = player
        self.update()

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        if self._status == 'PAUSED_PLAYBACK':
            return STATE_PAUSED
        if self._status == 'PLAYING':
            return STATE_PLAYING
        if self._status == 'STOPPED':
            return STATE_IDLE
        return STATE_UNKNOWN

    def update(self):
        """ Retrieve latest state. """
        self._name = self._player.get_speaker_info()['zone_name'].replace(
            ' (R)', '').replace(' (L)', '')
        self._status = self._player.get_current_transport_info().get(
            'current_transport_state')
        self._trackinfo = self._player.get_current_track_info()

    @property
    def volume_level(self):
        """ Volume level of the media player (0..1). """
        if 'mixer volume' in self._status:
            return self._player.volume / 100.0

    @property
    def is_volume_muted(self):
        return self._player.mute

    @property
    def media_content_id(self):
        """ Content ID of current playing media. """
        return self._trackinfo.get('title', None)

    @property
    def media_content_type(self):
        """ Content type of current playing media. """
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """ Duration of current playing media in seconds. """
        dur = self._trackinfo.get('duration', '0:00')
        return sum(60 ** x[0] * int(x[1]) for x in
                   enumerate(reversed(dur.split(':'))))

    @property
    def media_image_url(self):
        """ Image url of current playing media. """
        if 'album_art' in self._trackinfo:
            return self._trackinfo['album_art']

    @property
    def media_title(self):
        """ Title of current playing media. """
        if 'artist' in self._trackinfo and 'title' in self._trackinfo:
            return '{artist} - {title}'.format(
                artist=self._trackinfo['artist'],
                title=self._trackinfo['title']
            )
        if 'title' in self._status:
            return self._trackinfo['title']

    @property
    def supported_media_commands(self):
        """ Flags of media commands that are supported. """
        return SUPPORT_SONOS

    def turn_off(self):
        """ turn_off media player. """
        self._player.pause()

    def volume_up(self):
        """ volume_up media player. """
        self._player.volume += 1
        self.update_ha_state()

    def volume_down(self):
        """ volume_down media player. """
        self._player.volume -= 1
        self.update_ha_state()

    def set_volume_level(self, volume):
        """ set volume level, range 0..1. """
        self._player.volume = str(int(volume * 100))
        self.update_ha_state()

    def mute_volume(self, mute):
        """ mute (true) or unmute (false) media player. """
        self._player.mute = mute
        self.update_ha_state()

    def media_play(self):
        """ media_play media player. """
        self._player.play()
        self.update_ha_state()

    def media_pause(self):
        """ media_pause media player. """
        self._player.pause()
        self.update_ha_state()

    def media_next_track(self):
        """ Send next track command. """
        self._player.next()
        self.update_ha_state()

    def media_previous_track(self):
        """ Send next track command. """
        self._player.previous()
        self.update_ha_state()

    def media_seek(self, position):
        """ Send seek command. """
        self._player.seek(str(datetime.timedelta(seconds=int(position))))
        self.update_ha_state()

    def turn_on(self):
        """ turn the media player on. """
        self._player.play()
        self.update_ha_state()
