"""
homeassistant.components.media_player
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Component to interface with various media players
"""
import logging

from homeassistant.components import discovery
from homeassistant.helpers.device import Device
from homeassistant.helpers.device_component import DeviceComponent
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_VOLUME_UP,
    SERVICE_VOLUME_DOWN, SERVICE_MEDIA_PLAY_PAUSE, SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PREV_TRACK)

DOMAIN = 'media_player'
DEPENDENCIES = []
SCAN_INTERVAL = 30

ENTITY_ID_FORMAT = DOMAIN + '.{}'

DISCOVERY_PLATFORMS = {
    discovery.services.GOOGLE_CAST: 'cast',
}

SERVICE_YOUTUBE_VIDEO = 'play_youtube_video'

STATE_NO_APP = 'idle'

ATTR_STATE = 'state'
ATTR_OPTIONS = 'options'
ATTR_MEDIA_STATE = 'media_state'
ATTR_MEDIA_CONTENT_ID = 'media_content_id'
ATTR_MEDIA_TITLE = 'media_title'
ATTR_MEDIA_ARTIST = 'media_artist'
ATTR_MEDIA_ALBUM = 'media_album'
ATTR_MEDIA_IMAGE_URL = 'media_image_url'
ATTR_MEDIA_VOLUME = 'media_volume'
ATTR_MEDIA_DURATION = 'media_duration'

MEDIA_STATE_UNKNOWN = 'unknown'
MEDIA_STATE_PLAYING = 'playing'
MEDIA_STATE_STOPPED = 'stopped'


YOUTUBE_COVER_URL_FORMAT = 'http://img.youtube.com/vi/{}/1.jpg'


def is_on(hass, entity_id=None):
    """ Returns true if specified media player entity_id is on.
    Will check all media player if no entity_id specified. """

    entity_ids = [entity_id] if entity_id else hass.states.entity_ids(DOMAIN)

    return any(not hass.states.is_state(entity_id, STATE_NO_APP)
               for entity_id in entity_ids)


def turn_off(hass, entity_id=None):
    """ Will turn off specified media player or all. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


def volume_up(hass, entity_id=None):
    """ Send the media player the command for volume up. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    hass.services.call(DOMAIN, SERVICE_VOLUME_UP, data)


def volume_down(hass, entity_id=None):
    """ Send the media player the command for volume down. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    hass.services.call(DOMAIN, SERVICE_VOLUME_DOWN, data)


def media_play_pause(hass, entity_id=None):
    """ Send the media player the command for play/pause. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    hass.services.call(DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, data)


def media_play(hass, entity_id=None):
    """ Send the media player the command for play/pause. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    hass.services.call(DOMAIN, SERVICE_MEDIA_PLAY, data)


def media_pause(hass, entity_id=None):
    """ Send the media player the command for play/pause. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    hass.services.call(DOMAIN, SERVICE_MEDIA_PAUSE, data)


def media_next_track(hass, entity_id=None):
    """ Send the media player the command for next track. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    hass.services.call(DOMAIN, SERVICE_MEDIA_NEXT_TRACK, data)


def media_prev_track(hass, entity_id=None):
    """ Send the media player the command for prev track. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    hass.services.call(DOMAIN, SERVICE_MEDIA_PREV_TRACK, data)


SERVICE_TO_METHOD = {
    SERVICE_TURN_OFF: 'turn_off',
    SERVICE_VOLUME_UP: 'volume_up',
    SERVICE_VOLUME_DOWN: 'volume_down',
    SERVICE_MEDIA_PLAY_PAUSE: 'media_play_pause',
    SERVICE_MEDIA_PLAY: 'media_play',
    SERVICE_MEDIA_PAUSE: 'media_pause',
    SERVICE_MEDIA_NEXT_TRACK: 'media_next_track',
}


def setup(hass, config):
    """ Track states and offer events for media_players. """
    component = DeviceComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL,
        DISCOVERY_PLATFORMS)

    component.setup(config)

    def media_player_service_handler(service):
        """ Maps services to methods on MediaPlayerDevice. """
        target_players = component.extract_from_service(service)

        method = SERVICE_TO_METHOD[service.service]

        for player in target_players:
            getattr(player, method)()

            if player.should_poll:
                player.update_ha_state(True)

    for service in SERVICE_TO_METHOD:
        hass.services.register(DOMAIN, service, media_player_service_handler)

    def play_youtube_video_service(service, media_id):
        """ Plays specified media_id on the media player. """
        target_players = component.extract_from_service(service)

        if media_id:
            for player in target_players:
                player.play_youtube(media_id)

    hass.services.register(DOMAIN, "start_fireplace",
                           lambda service:
                           play_youtube_video_service(service, "eyU3bRy2x44"))

    hass.services.register(DOMAIN, "start_epic_sax",
                           lambda service:
                           play_youtube_video_service(service, "kxopViU98Xo"))

    hass.services.register(DOMAIN, SERVICE_YOUTUBE_VIDEO,
                           lambda service:
                           play_youtube_video_service(
                               service, service.data.get('video')))

    return True


class MediaPlayerDevice(Device):
    """ ABC for media player devices. """

    def turn_off(self):
        """ turn_off media player. """
        pass

    def volume_up(self):
        """ volume_up media player. """
        pass

    def volume_down(self):
        """ volume_down media player. """
        pass

    def media_play_pause(self):
        """ media_play_pause media player. """
        pass

    def media_play(self):
        """ media_play media player. """
        pass

    def media_pause(self):
        """ media_pause media player. """
        pass

    def media_next_track(self):
        """ media_next_track media player. """
        pass

    def play_youtube(self, media_id):
        """ Plays a YouTube media. """
        pass
