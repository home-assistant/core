"""
Support to interact with a ExoPlayer on Android via HTTO and MQTT.

"""
import asyncio
import json
import logging
from typing import Optional

import homeassistant.components.ais_dom.ais_global as ais_global
from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    MediaPlayerDevice,
)
from homeassistant.components.media_player.const import (
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_NAME,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

SUPPORT_EXO = (
    SUPPORT_PAUSE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
    | SUPPORT_STOP
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_SEEK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_SELECT_SOUND_MODE
    | SUPPORT_SHUFFLE_SET
)

DEFAULT_NAME = "AIS Dom Odtwarzacz"
ATTR_AIS_GROUP = "ais_exo_player_group"
ATTR_MASTER = "master"


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
        if _ip == "localhost":
            _mac = "1111111111111111111"
        else:
            _mac = config.get(CONF_IP_ADDRESS).replace(".", "")

    device = ExoPlayerDevice(_ip, _mac, name)
    _LOGGER.info("device: " + str(device))
    async_add_devices([device], True)

    def _update_state():
        # to keep groups in sync with player
        state = hass.states.get("media_player.wbudowany_glosnik").state
        attributes = hass.states.get("media_player.wbudowany_glosnik").attributes
        new_attr = {}
        list_idx = -1
        for itm in attributes:
            list_idx = list_idx + 1
            new_attr[list_idx] = attributes[itm]
        new_attr["ais_exo_player_group"] = ais_global.G_SPEAKERS_GROUP_LIST
        hass.states.async_set("media_player.wbudowany_glosnik", state, new_attr)

    # register services
    @asyncio.coroutine
    def join(service):
        def j(entity_id):
            if entity_id not in ais_global.G_SPEAKERS_GROUP_LIST:
                ais_global.G_SPEAKERS_GROUP_LIST.append(entity_id)

        player = service.data["entity_id"]
        if type(player) is str:
            j(player)
        if type(player) is list:
            for e in player:
                j(e)
        _update_state()

    @asyncio.coroutine
    def unjoin(service):
        player = None
        if "entity_id" in service.data:
            if type(service.data["entity_id"]) is str:
                player = service.data["entity_id"]
            if type(service.data["entity_id"]) is list:
                player = None

        if player is None:
            ais_global.G_SPEAKERS_GROUP_LIST = ["media_player.wbudowany_glosnik"]
        else:
            if player in ais_global.G_SPEAKERS_GROUP_LIST:
                ais_global.G_SPEAKERS_GROUP_LIST.remove(player)
        _update_state()

    hass.services.async_register("ais_exo_player", "join", join)
    hass.services.async_register("ais_exo_player", "unjoin", unjoin)


class ExoPlayerDevice(MediaPlayerDevice):
    """Representation of a ExoPlayer ."""

    def turn_on(self):
        pass

    def turn_off(self):
        pass

    def set_volume_level(self, volume):
        self._volume_level = volume
        vol = int(volume * 100)
        self._publish_command_to_frame("setVolume", vol)

    def select_sound_mode(self, sound_mode):
        self._sound_mode = sound_mode
        self.hass.services.call(
            "ais_amplifier_service", "change_sound_mode", {"mode": sound_mode}
        )

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
        self._sound_mode = "NORMAL"
        self._playlists = [
            ais_global.G_AN_RADIO,
            ais_global.G_AN_PODCAST,
            ais_global.G_AN_MUSIC,
            ais_global.G_AN_AUDIOBOOK,
            ais_global.G_AN_NEWS,
            ais_global.G_AN_LOCAL,
            ais_global.G_AN_SPOTIFY,
            ais_global.G_AN_FAVORITE,
        ]
        self._currentplaylist = None
        self._media_status_received_time = None
        self._media_position = 0
        self._duration = 0
        self._media_content_id = None
        self._volume_level = 0.5
        self._shuffle = False
        self._assistant_audio = False

        if device_ip == "localhost":
            self._is_master = True
        else:
            self._is_master = False

    def _publish_command_to_frame(self, key, val):
        if self._device_ip == "localhost":
            self.hass.services.call(
                "ais_ai_service",
                "publish_command_to_frame",
                {"key": key, "val": val, "ip": "localhost"},
            )
            for s in ais_global.G_SPEAKERS_GROUP_LIST:
                attr = self.hass.states.get(s).attributes
                if "device_ip" in attr and attr["device_ip"] != "localhost":
                    self.hass.services.call(
                        "ais_ai_service",
                        "publish_command_to_frame",
                        {"key": key, "val": val, "ip": attr["device_ip"]},
                    )
        else:
            self.hass.services.call(
                "ais_ai_service", "publish_command_to_frame", {"key": key, "val": val},
            )

    @asyncio.coroutine
    def async_added_to_hass(self):
        pass

    def _fetch_status(self):
        """Fetch status from ExoPlayer."""
        # INFO - we are not fetching the status from player
        # exp player and spotify is pushing the status to asystent domowy

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
        return float(self._duration) // 1000

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return self._shuffle

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        self._shuffle = shuffle
        self._publish_command_to_frame("setPlayerShuffle", self._shuffle)

    def media_seek(self, position):
        """Seek the media to a specific location."""
        if position == 0:
            self._publish_command_to_frame("seekTo", -5000)
        elif position == 1:
            self._publish_command_to_frame("seekTo", 5000)
        else:
            self._publish_command_to_frame("skipTo", position * 1000)
            self._media_status_received_time = dt_util.utcnow()
            self._media_position = position * 1000

    def volume_up(self):
        """Service to send the exo the command for volume up."""
        self._volume_level = min(self._volume_level + 0.1, 1)
        self._publish_command_to_frame("upVolume", True)

    def volume_down(self):
        """Service to send the exo the command for volume down."""
        self._volume_level = max(self._volume_level - 0.1, 0)
        self._publish_command_to_frame("downVolume", True)

    def mute_volume(self, mute):
        """Service to send the exo the command for mute."""
        pass
        # TODO

    @property
    def sound_mode(self):
        """Return the current matched sound mode."""
        return self._sound_mode

    @property
    def sound_mode_list(self):
        """Return a list of available sound modes."""
        return [
            "NORMAL",
            "BOOST",
            "TREBLE",
            "POP",
            "ROCK",
            "CLASSIC",
            "JAZZ",
            "DANCE",
            "R&P",
        ]

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
                app = str(app) + " " + str(self._album_name)
        return app

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_EXO

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
        position = float(self._media_position) // 1000
        # if self._status == 3 and self._media_status_received_time is not None:
        #     position += (dt_util.utcnow() - self._media_status_received_time).total_seconds()
        return int(position)

    @property
    def device_state_attributes(self):
        """Return the specific state attributes of the player."""
        attr = {"device_ip": self._device_ip}
        # attr['device_mac'] = self._device_mac
        """List members in group."""
        attr[ATTR_AIS_GROUP] = ais_global.G_SPEAKERS_GROUP_LIST

        if self._device_ip == "localhost":
            attr["friendly_name"] = "Podłączony głośnik"
        else:
            attr["friendly_name"] = self._name
        attr[ATTR_MASTER] = self._is_master

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
        self._publish_command_to_frame("pauseAudio", False)
        self._playing = True
        self._status = 3

    def media_pause(self):
        """Service to send the ExoPlayer the command for play/pause."""
        # to have more accurate media_position
        self._fetch_status()
        self._publish_command_to_frame("pauseAudio", True)
        self._playing = False

    def media_stop(self):
        """Service to send the ExoPlayer the command for stop."""
        self._publish_command_to_frame("pauseAudio", True)
        self._playing = False

    def media_next_track(self):
        """Service to send the ExoPlayer the command for next track."""
        if self._media_source == ais_global.G_AN_LOCAL:
            self.hass.services.call("ais_drives_service", "play_next")
        else:
            self.hass.services.call(
                "ais_cloud", "play_next", {"media_source": self._media_source}
            )

    def media_previous_track(self):
        """Service to send the ExoPlayer the command for previous track."""
        if self._media_source == ais_global.G_AN_LOCAL:
            self.hass.services.call("ais_drives_service", "play_prev")
        else:
            self.hass.services.call(
                "ais_cloud", "play_prev", {"media_source": self._media_source}
            )

    def play_media(self, media_type, media_content_id, **kwargs):
        """Send the media player the command for playing a media."""
        if media_type == "ais_content_info":
            j_info = json.loads(media_content_id)
            # set image and name and id on list to be able to set correct bookmark and favorites
            ais_global.G_CURR_MEDIA_CONTENT = j_info
            # play
            self._media_content_id = j_info["media_content_id"]
            self._media_status_received_time = dt_util.utcnow()
            if "media_position_ms" in j_info:
                self._media_position = j_info["media_position_ms"]
            else:
                self._media_position = 0
            if "IMAGE_URL" not in j_info:
                self._stream_image = "/static/icons/tile-win-310x150.png"
            else:
                self._stream_image = j_info["IMAGE_URL"]
            self._media_title = j_info["NAME"]
            if j_info["MEDIA_SOURCE"] == ais_global.G_AN_GOOGLE_ASSISTANT:
                # do no change self._media_source
                self._assistant_audio = True
            else:
                self._assistant_audio = False
                self._media_source = j_info["MEDIA_SOURCE"]
            self._currentplaylist = j_info["MEDIA_SOURCE"]
            if "ALBUM_NAME" in j_info:
                self._album_name = j_info["ALBUM_NAME"]
            else:
                self._album_name = 0
            if "DURATION" in j_info:
                self._duration = j_info["DURATION"]

            j_media_info = {
                "media_title": self._media_title,
                "media_source": self._media_source,
                "media_stream_image": self._stream_image,
                "media_album_name": self._album_name,
                "media_content_id": self._media_content_id,
                "setPlayerShuffle": self._shuffle,
                "setMediaPosition": self._media_position,
            }

            self._publish_command_to_frame("playAudioFullInfo", j_media_info)

            # go to media player context on localhost
            if self._device_ip == "localhost":
                # refresh state
                self._playing = True
                self._status = 3
                old_state = self.hass.states.get("media_player.wbudowany_glosnik")
                self.hass.states.set(
                    "media_player.wbudowany_glosnik",
                    STATE_PLAYING,
                    old_state.attributes,
                    force_update=True,
                )
                self.hass.services.call(
                    "ais_ai_service",
                    "process_command_from_frame",
                    {"topic": "ais/go_to_player", "payload": ""},
                )

        elif media_type == "ais_info":
            # TODO remove this - it is only used in one case - for local media_extractor
            # set only the audio info
            j_info = json.loads(media_content_id)
            ais_global.G_CURR_MEDIA_CONTENT = j_info
            if "IMAGE_URL" not in j_info:
                self._stream_image = "/static/icons/tile-win-310x150.png"
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
                j_media_info = {
                    "media_title": self._media_title,
                    "media_source": self._media_source,
                    "media_stream_image": self._stream_image,
                    "media_album_name": self._album_name,
                }
                self._publish_command_to_frame("setAudioInfo", j_media_info)
            except Exception as e:
                _LOGGER.debug("problem to publish setAudioInfo: " + str(e))

            # go to media player context on localhost
            if self._device_ip == "localhost":
                # refresh state
                self._playing = True
                self._status = 3
                old_state = self.hass.states.get("media_player.wbudowany_glosnik")
                self.hass.states.set(
                    "media_player.wbudowany_glosnik",
                    STATE_PLAYING,
                    old_state.attributes,
                    force_update=True,
                )
                self.hass.services.call(
                    "ais_ai_service",
                    "process_command_from_frame",
                    {"topic": "ais/go_to_player", "payload": ""},
                )

        elif media_type == "exo_info":
            self._media_status_received_time = dt_util.utcnow()
            try:
                message = json.loads(media_content_id.decode("utf8").replace("'", '"'))
            except Exception as e:
                message = json.loads(media_content_id)
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

            # spotify info
            if self._media_source == ais_global.G_AN_SPOTIFY:
                # shuffle
                self._shuffle = message.get("isShuffling", False)
                # mark track on Spotify list
                state = self.hass.states.get("sensor.spotifylist")
                attr = state.attributes
                for i in range(len(attr)):
                    track = attr.get(i)
                    if track["uri"] == message.get("media_content_id", ""):
                        self.hass.states.async_set("sensor.spotifylist", i, attr)
                        break

            if "giveMeNextOne" in message:
                play_next = message.get("giveMeNextOne", False)
                # play next audio only if the current was not from assistant
                if play_next is True and self._assistant_audio is False:
                    # TODO remove bookmark
                    self.hass.async_add_job(
                        self.hass.services.async_call(
                            "media_player",
                            "media_next_track",
                            {"entity_id": "media_player.wbudowany_glosnik"},
                        )
                    )
        else:
            # TODO remove this - it is only used in one case - for local media_extractor
            # play only
            self._media_content_id = media_content_id
            self._media_position = 0
            self._media_status_received_time = dt_util.utcnow()
            self._publish_command_to_frame("playAudio", media_content_id)
