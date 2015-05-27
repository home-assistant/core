"""
homeassistant.components.media_player.enigma
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Demo implementation of the media player.

"""
from homeassistant.components.media_player import (
    MediaPlayerDevice, STATE_NO_APP, ATTR_MEDIA_STATE,
    ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_TITLE, ATTR_MEDIA_DURATION,
    ATTR_MEDIA_VOLUME, MEDIA_STATE_PLAYING, MEDIA_STATE_STOPPED,
    YOUTUBE_COVER_URL_FORMAT)
from homeassistant.const import ATTR_ENTITY_PICTURE
import logging
import requests
log = logging.getLogger(__name__)

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the cast platform. """
    log.info('Config: %s', config)
    e2config = config

    host = e2config.get('host', None)
    port = e2config.get('port', "80")
    name = e2config.get('name', "Enigma2")

    log.info('host: %s', host)
    log.info('name: %s', name)

    if not host:
        log.error('Missing config variable-host')
        return False

    add_devices([
        EnigmaMediaPlayer(name, host, port)
    ])




class EnigmaMediaPlayer(MediaPlayerDevice):
    """ A Demo media player that only supports YouTube. """

    def __init__(self, name, host, port):
        self._name = name
        self._host = host
        # self._port = port
        self.state_attr = {ATTR_MEDIA_STATE: MEDIA_STATE_STOPPED}
        # self.update()

        self.is_playing = False
        self.media_title = None
        self.volume = 1.0
        self.channel_title = None

    @property
    def should_poll(self):
        """ No polling needed for a demo componentn. """
        return True

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return STATE_NO_APP if self.is_playing is False else self.channel_title

    @property
    def state_attributes(self):
        """ Returns the state attributes. """

        return self.state_attr

    def turn_off(self):
        """ turn_off media player. """
        self.is_playing = False

    def volume_up(self):
        """ volume_up media player. """
        if self.volume < 1:
            self.volume += 0.1

    def volume_down(self):
        """ volume_down media player. """
        if self.volume > 0:
            self.volume -= 0.1

    def media_play_pause(self):
        """ media_play_pause media player. """
        self.is_playing = not self.is_playing

    def media_play(self):
        """ media_play media player. """
        self.is_playing = True

    def media_pause(self):
        """ media_pause media player. """
        self.is_playing = False

    def play_youtube(self, media_id):
        """ Plays a YouTube media. """
        self.media_title = 'Demo media title'
        self.is_playing = True


    def update(self):
        """ Update state of the media_player. """
        log.info("updating status enigma media_player")

        url = 'http://%s/api/statusinfo' % self._host
        log.info('url: %s', url)

        r = requests.get(url)

        log.info('response: %s' % r)
        log.info("status_code %s" % r.status_code)

        if r.status_code != 200:
            log.error("There was an error connecting to %s" % url)
            log.error("status_code %s" % r.status_code)
            log.error("error %s" % r.error)

            return

        log.info('r.json: %s' % r.json())

        in_standby = r.json()['inStandby']
        log.info('r.json inStandby: %s' % in_standby)


        if in_standby == 'true':
            self.state_attr = {
                ATTR_MEDIA_STATE: MEDIA_STATE_STOPPED
            }
            self.is_playing = False
            self.media_title = None
        else:
            self.is_playing = True
            self.media_title = r.json()['currservice_name']
            self.channel_title = r.json()['currservice_station']

            self.state_attr = {
                ATTR_MEDIA_CONTENT_ID: self.channel_title,
                ATTR_MEDIA_TITLE: self.media_title,
                ATTR_MEDIA_DURATION: 100,
                ATTR_MEDIA_VOLUME: self.volume,
                ATTR_MEDIA_STATE: MEDIA_STATE_PLAYING
                # ATTR_ENTITY_PICTURE:
                # YOUTUBE_COVER_URL_FORMAT.format(self.youtube_id)
            }

