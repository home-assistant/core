"""
homeassistant.components.media_player.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Demo implementation of the media player.

"""
from homeassistant.components.media_player import (
    MediaPlayerDevice, STATE_NO_APP, ATTR_MEDIA_STATE,
    ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_TITLE, ATTR_MEDIA_DURATION,
    ATTR_MEDIA_VOLUME, MEDIA_STATE_PLAYING, MEDIA_STATE_STOPPED,
    ATTR_MEDIA_IS_VOLUME_MUTED, MEDIA_STATE_PAUSED)
from homeassistant.const import ATTR_ENTITY_PICTURE
import jsonrpc_requests


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the kodi platform. """

    add_devices([
        KodiDevice(
            config.get('name', 'Kodi'),
            config.get('url'),
            auth=(
                config.get('user', ''),
                config.get('password', ''))),
    ])


class KodiDevice(MediaPlayerDevice):
    """ TODO. """

    def __init__(self, name, url, auth=None):
        self._name = name
        self._url = url
        self._server = jsonrpc_requests.Server(url, auth=auth)

    @property
    def should_poll(self):
        """ TODO. """
        return True

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    def _get_players(self):
        return self._server.Player.GetActivePlayers()

    @property
    def state(self):
        """ Returns the state of the device. """
        players = self._get_players()

        if len(players) == 0:
            return STATE_NO_APP

        return players[0]['type']

    @property
    def state_attributes(self):
        """ Returns the state attributes. """

        players = self._get_players()

        if len(players) == 0:
            return {
                ATTR_MEDIA_STATE: MEDIA_STATE_STOPPED
            }

        player_id = players[0]['playerid']

        assert isinstance(player_id, int)

        item = self._server.Player.GetItem(
            player_id,
            ['title', 'file', 'uniqueid', 'thumbnail', 'artist'])[
            'item']

        properties = self._server.Player.GetProperties(
            player_id,
            ['time', 'totaltime', 'speed'])

        app_properties = self._server.Application.GetProperties(
            ['volume', 'muted'])

        # find a string we can use as a title
        title = item.get('title',
                         item.get('label',
                                  item.get('file', 'unknown')))

        total_time = properties['totaltime']

        return {
            ATTR_MEDIA_CONTENT_ID: item['uniqueid'],
            ATTR_MEDIA_TITLE: title,
            ATTR_MEDIA_DURATION:
                total_time['hours'] * 3600 +
                total_time['minutes'] * 60 +
                total_time['seconds'],
            ATTR_MEDIA_VOLUME:
                app_properties['volume'] / 100.0,
            ATTR_MEDIA_IS_VOLUME_MUTED:
                app_properties['muted'],
            ATTR_ENTITY_PICTURE:
                item['thumbnail'],
            ATTR_MEDIA_STATE:
                MEDIA_STATE_PAUSED if properties['speed'] == 0
                else MEDIA_STATE_PLAYING,
        }

    def turn_off(self):
        """ turn_off media player. """
        self._server.System.Shutdown()
        self.update_ha_state()

    def volume_up(self):
        """ volume_up media player. """
        assert self._server.Input.ExecuteAction('volumeup') == 'OK'
        self.update_ha_state()

    def volume_down(self):
        """ volume_down media player. """
        assert self._server.Input.ExecuteAction('volumedown') == 'OK'
        self.update_ha_state()

    def volume_set(self, volume):
        """ TODO. """
        self._server.Application.SetVolume(int(volume * 100))
        self.update_ha_state()

    def volume_mute(self, mute):
        """ mute (true) or unmute (false) media player. """
        self._server.Application.SetMute(mute)
        self.update_ha_state()

    def _set_play_state(self, state):
        players = self._get_players()

        if len(players) != 0:
            self._server.Player.PlayPause(players[0]['playerid'], state)

        self.update_ha_state()

    def media_play_pause(self):
        """ media_play_pause media player. """
        self._set_play_state('toggle')

    def media_play(self):
        """ media_play media player. """
        self._set_play_state(True)

    def media_pause(self):
        """ media_pause media player. """
        self._set_play_state(False)

    def _goto(self, to):
        players = self._get_players()

        if len(players) != 0:
            self._server.Player.GoTo(players[0]['playerid'], to)

        self.update_ha_state()

    def media_next_track(self):
        self._goto('next')

    def media_prev_track(self):
        self._goto('previous')