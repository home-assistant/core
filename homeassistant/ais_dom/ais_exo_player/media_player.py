"""
Support to interact with a ExoPlayer on Android via HTTO and MQTT.

"""
import asyncio
import logging
import json
import os
import homeassistant.util.dt as dt_util
from homeassistant.core import callback
import homeassistant.components.mqtt as mqtt
import homeassistant.ais_dom.ais_global as ais_global
from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_STOP, SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA, MediaPlayerDevice, SUPPORT_SEEK,
    SUPPORT_SELECT_SOURCE, ATTR_MEDIA_DURATION, ATTR_MEDIA_SEEK_POSITION, SUPPORT_SELECT_SOUND_MODE)
from homeassistant.components.media_player.const import (
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP)
from typing import Optional
from homeassistant.const import (
    STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING,
    CONF_NAME, CONF_IP_ADDRESS, CONF_MAC)


_LOGGER = logging.getLogger(__name__)

SUPPORT_EXO = SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_PLAY_MEDIA | SUPPORT_PLAY | SUPPORT_STOP | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_VOLUME_STEP | SUPPORT_SEEK | SUPPORT_SELECT_SOURCE | SUPPORT_SELECT_SOUND_MODE

SUBSCTRIBE_TOPIC = 'ais/player_status'
DEFAULT_NAME = 'AIS Dom Odtwarzacz'


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the ExoPlayer platform."""
    if discovery_info is not None:
        name = discovery_info.get(CONF_NAME)
        _ip = discovery_info.get(CONF_IP_ADDRESS)
        _mac = discovery_info.get(CONF_MAC)
    else:
        name = config.get(CONF_NAME)
        _ip = config.get(CONF_IP_ADDRESS)
        # TODO get local mac address
        _mac = '1111111111111111111'

    device = ExoPlayerDevice(_ip, _mac, name)
    _LOGGER.info("device: " + str(device))
    async_add_devices([device], True)


class ExoPlayerDevice(MediaPlayerDevice):
    """Representation of a ExoPlayer ."""

    def turn_on(self):
        pass

    def turn_off(self):
        pass

    def set_volume_level(self, volume):
        self._volume_level = volume
        vol = int(volume * 100)
        self.hass.services.call(
            'ais_ai_service',
            'publish_command_to_frame', {
                "key": 'setVolume',
                "val": vol
            }
        )

    def select_sound_mode(self, sound_mode):
        pass

    def clear_playlist(self):
        pass

    # pylint: disable=no-member
    def __init__(self, device_ip, device_mac, name):
        """Initialize the ExoPlayer device."""
        self._device_ip = device_ip
        self._device_mac = device_mac
        self._name = name
        self._status = None
        self._playing = False
        self._qos = 2
        self._stream_image = None
        self._media_title = None
        self._media_source = None
        self._album_name = None
        self._playlists = [ais_global.G_AN_RADIO,
                           ais_global.G_AN_PODCAST,
                           ais_global.G_AN_MUSIC,
                           ais_global.G_AN_AUDIOBOOK,
                           ais_global.G_AN_NEWS,
                           ais_global.G_AN_LOCAL,
                           ais_global.G_AN_SPOTIFY]
        self._currentplaylist = None
        self._media_status_received_time = None
        self._media_position = 0
        self._duration = 0
        self._media_content_id = None
        self._volume_level = 0.5

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe MQTT events."""
        @callback
        def message_received(topic, payload, qos):
            """Handle new MQTT messages."""
            _LOGGER.info("payload: " + str(payload))
            self._media_status_received_time = dt_util.utcnow()
            try:
                message = json.loads(payload.decode('utf8').replace("'", '"'))
            except Exception as e:
                _LOGGER.error("problem to json.loads: " + str(e))
                message = json.loads(payload)
            try:
                self._volume_level = message.get("currentVolume", 0) / 100
            except Exception as e:
                _LOGGER.warning("no currentVolume info: " + str(e))
            self._status = message.get("currentStatus", 0)
            self._playing = message.get("playing", False)
            self._media_position = message.get("currentPosition", 0)
            if "duration" in message:
                self._duration = message.get("duration", 0)
            temp_stream_image = message.get("media_stream_image", None)
            if temp_stream_image is not None:
                if temp_stream_image.startswith("spotify:image:"):
                    temp_stream_image = temp_stream_image.replace("spotify:image:", "")
                    self._stream_image = "https://i.scdn.co/image/" + temp_stream_image
                else:
                    self._stream_image = temp_stream_image
            self._media_title = message.get("currentMedia", "AI-Speaker")
            self._media_source = message.get("media_source", self._media_source)
            self._album_name = message.get("media_album_name", "AI-Speaker")
            _LOGGER.debug(str.format("message_received: {0}", message))
            if "giveMeNextOne" in message:
                play_next = message.get("giveMeNextOne", False)
                if play_next is True:
                    self.hass.async_add_job(
                        self.hass.services.async_call(
                            'media_player',
                            'media_next_track', {
                                "entity_id": "media_player.wbudowany_glosnik"})
                            )
        return mqtt.async_subscribe(
            self.hass, SUBSCTRIBE_TOPIC, message_received, self._qos, None)

    def _fetch_status(self):
        """Fetch status from ExoPlayer."""
        _LOGGER.debug("_fetch_status")
        # TODO maybe we should do this for other players in network...
        # self.hass.services.call(
        #     'ais_ai_service',
        #     'publish_command_to_frame', {
        #         "key": 'getAudioStatus',
        #         "val": True,
        #         "ip": self._device_ip
        #         }
        #     )

    @property
    def source(self):
        """Name of the current input source."""
        return self._currentplaylist

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return self._playlists

    def select_source(self, source):
        """Choose a different available playlist and play it."""
        # TODO
        pass

    @property
    def volume_level(self):
        """Return the volume level of the Player"""
        return self._volume_level

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return int(float(self._duration))

    def media_seek(self, position):
        """Seek the media to a specific location."""
        if position == 0:
            self.hass.services.call(
                'ais_ai_service',
                'publish_command_to_frame', {
                    "key": 'seekTo',
                    "val": -5000
                }
            )
        elif position == 1:
            self.hass.services.call(
                'ais_ai_service',
                'publish_command_to_frame', {
                    "key": 'seekTo',
                    "val": 5000
                }
            )
        else:
            self.hass.services.call(
                'ais_ai_service',
                'publish_command_to_frame', {
                    "key": 'skipTo',
                    "val": position
                }
            )
            self._media_status_received_time = dt_util.utcnow()
            self._media_position = position

    def volume_up(self):
        """Service to send the exo the command for volume up."""
        self._volume_level = min(self._volume_level + 0.1, 1)
        self.hass.services.call(
            'ais_ai_service',
            'publish_command_to_frame', {
                "key": 'upVolume',
                "val": True
                }
            )

    def volume_down(self):
        """Service to send the exo the command for volume down."""
        self._volume_level = max(self._volume_level - 0.1, 0)
        self.hass.services.call(
            'ais_ai_service',
            'publish_command_to_frame', {
                "key": 'downVolume',
                "val": True
                }
            )

    def mute_volume(self, mute):
        """Service to send the exo the command for mute."""
        pass
        # TODO
        #  self.hass.services.call(
        #     'ais_ai_service',
        #     'publish_command_to_frame', {
        #         "key": 'downVolume',
        #         "val": True
        #     }
        # )

    @property
    def sound_mode(self):
        """Return the current matched sound mode."""
        return "NORMAL"

    @property
    def sound_mode_list(self):
        """Return a list of available sound modes."""
        return ["NORMAL", "BOOST", "TREBLE", "POP", "ROCK", "CLASSIC", "JAZZ", "DANCE", "R&P"]

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        # TODO
        return True

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        # TODO
        pass

    @property
    def available(self):
        """True if ExoPlayer is available and connected."""
        return True

    def update(self):
        """Get the latest data and update the state."""
        self._fetch_status()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def media_image_url(self):
        """Return the image url of current playing media."""
        if self._stream_image is None:
            return "http://localhost:8180/static/icons/tile-win-310x150.png"
        return self._stream_image

    @property
    def state(self):
        """Return the media state."""

        if self._playing is False:
            return STATE_PAUSED
        else:
            # STATE_IDLE == 1
            # STATE_BUFFERING == 2
            # Player.STATE_READY == 3
            # STATE_ENDED == 4
            if self._status == 1:
                return STATE_IDLE
            if self._status == 2:
                return STATE_PAUSED
            if self._status == 3:
                return STATE_PLAYING
            if self._status == 4:
                return STATE_PAUSED

        return STATE_OFF

    @property
    def media_title(self):
        """Return the title of current playing media."""
        return self._media_title

    @property
    def media_album_name(self):
        """Album of current playing media"""
        return self._album_name

    @property
    def app_name(self):
        """Name of the current running app."""
        app = None
        if self._media_source is not None:
            app = self._media_source
            if self._album_name is not None:
                app = app + " " + self._album_name
        return app

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_EXO

    @property
    def device_ip(self):
        """The device IP Address"""
        return self._device_ip

    @property
    def media_content_id(self):
        """The media content id"""
        return self._media_content_id

    @property
    def media_stream_image(self):
        """The media content id"""
        return self._stream_image

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        position = self._media_position
        if self._status == 3 and self._media_status_received_time is not None:
            position += (dt_util.utcnow() - self._media_status_received_time).total_seconds()
        return int(float(position))

    @property
    def device_state_attributes(self):
        """Return the specific state attributes of the player."""
        attr = {'device_ip': self._device_ip}
        # attr['device_mac'] = self._device_mac
        return attr

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._device_mac

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.
        Returns value from homeassistant.util.dt.utcnow().
        """
        return self._media_status_received_time

    def media_play(self):
        """Service to send the ExoPlayer the command for play/pause."""
        self.hass.services.call(
            'ais_ai_service',
            'publish_command_to_frame', {
                "key": 'pauseAudio',
                "val": False,
                "ip": self._device_ip
                }
            )
        self._playing = True
        self._status = 3

    def media_pause(self):
        """Service to send the ExoPlayer the command for play/pause."""
        # to have more accurate media_position
        self._fetch_status()
        self.hass.services.call(
            'ais_ai_service',
            'publish_command_to_frame', {
                "key": 'pauseAudio',
                "val": True,
                "ip": self._device_ip
                }
            )
        self._playing = False

    def media_stop(self):
        """Service to send the ExoPlayer the command for stop."""
        self.hass.services.call(
            'ais_ai_service',
            'publish_command_to_frame', {
                "key": 'pauseAudio',
                "val": True,
                "ip": self._device_ip
                }
            )
        self._playing = False

    def media_next_track(self):
        """Service to send the ExoPlayer the command for next track."""
        if self._media_source == ais_global.G_AN_LOCAL:
            self.hass.services.call('ais_drives_service', 'play_next')
        else:
            entity_id = ""
            if self._media_source == ais_global.G_AN_RADIO:
                entity_id = "input_select.radio_station_name"
            elif self._media_source == ais_global.G_AN_PODCAST:
                entity_id = "input_select.podcast_track"
            elif self._media_source == ais_global.G_AN_MUSIC:
                entity_id = "input_select.ais_music_track_name"
            elif self._media_source == ais_global.G_AN_SPOTIFY:
                entity_id = "input_select.ais_music_track_name"
            elif self._media_source == ais_global.G_AN_AUDIOBOOK:
                entity_id = "input_select.book_chapter"

            self.hass.services.call(
                'input_select',
                'select_next', {
                    "entity_id": entity_id})
            self.hass.block_till_done()
            name = self.hass.states.get(entity_id).state
            self.hass.block_till_done()
            if name == '-':
                self.hass.services.call(
                    'input_select',
                    'select_next', {
                        "entity_id": entity_id})
            self.hass.block_till_done()
            name = self.hass.states.get(entity_id).state
            name = 'Odtwarzam kolejny: ' + name
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": name})

    def media_previous_track(self):
        """Service to send the ExoPlayer the command for previous track."""
        if self._media_source == ais_global.G_AN_LOCAL:
            self.hass.services.call('ais_drives_service', 'play_prev')
        else:
            entity_id = ""
            if self._media_source == ais_global.G_AN_RADIO:
                entity_id = "input_select.radio_station_name"
            elif self._media_source == ais_global.G_AN_PODCAST:
                entity_id = "input_select.podcast_track"
            elif self._media_source == ais_global.G_AN_MUSIC:
                entity_id = "input_select.ais_music_track_name"
            elif self._media_source == ais_global.G_AN_SPOTIFY:
                entity_id = "input_select.ais_music_track_name"
            elif self._media_source == ais_global.G_AN_AUDIOBOOK:
                entity_id = "input_select.book_chapter"
            self.hass.services.call(
                'input_select',
                'select_previous', {
                    "entity_id": entity_id})
            self.hass.block_till_done()
            name = self.hass.states.get(entity_id).state
            if name == '-':
                self.hass.services.call(
                    'input_select',
                    'select_previous', {
                        "entity_id": entity_id})
            self.hass.block_till_done()
            name = self.hass.states.get(entity_id).state
            name = 'Odtwarzam poprzedni: ' + name
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": name})

    def play_media(self, media_type, media_content_id, **kwargs):
        """Send the media player the command for playing a media."""
        if media_type == 'ais_info':
            # set image and name
            j_info = json.loads(media_content_id)
            if "IMAGE_URL" not in j_info:
                self._stream_image = "http://localhost:8180/static/icons/tile-win-310x150.png"
            else:
                self._stream_image = j_info["IMAGE_URL"]
            self._media_title = j_info["NAME"]
            self._media_source = j_info["MEDIA_SOURCE"]
            self._currentplaylist = j_info["MEDIA_SOURCE"]
            if "ALBUM_NAME" in j_info:
                self._album_name = j_info["ALBUM_NAME"]
            else:
                self._album_name = None
            if "DURATION" in j_info:
                self._duration = j_info["DURATION"]

            try:
                j_media_info = {"media_title": self._media_title,
                                "media_source": self._media_source,
                                "media_stream_image": self._stream_image,
                                "media_album_name": self._album_name}
                self.hass.services.call(
                    'ais_ai_service',
                    'publish_command_to_frame', {
                        "key": 'setAudioInfo',
                        "val": j_media_info,
                        "ip": self._device_ip
                    }
                )
            except Exception as e:
                _LOGGER.info("problem to publish setAudioInfo: " + str(e))
        else:
            self._media_content_id = media_content_id
            self._media_position = 0
            self._media_status_received_time = dt_util.utcnow()
            self.hass.services.call(
                'ais_ai_service',
                'publish_command_to_frame', {
                    "key": 'playAudio',
                    "val": media_content_id,
                    "ip": self._device_ip
                    }
                )

            # go to media player context on localhost
            if self._device_ip == 'localhost':
                # refresh state
                self._playing = True
                self._status = 3
                old_state = self.hass.states.get('media_player.wbudowany_glosnik')
                self.hass.states.set(
                    'media_player.wbudowany_glosnik', STATE_PLAYING, old_state.attributes, force_update=True)
                self.hass.services.call(
                    'ais_ai_service',
                    'process_command_from_frame', {
                        "topic": 'ais/go_to_player',
                        "payload": ""
                    }
                )
