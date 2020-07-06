
"""
MediaPlayer platform for Roon component

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.roon/
"""
import logging
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_ENQUEUE, SUPPORT_PLAY_MEDIA, SUPPORT_SELECT_SOURCE, SUPPORT_STOP, SUPPORT_SHUFFLE_SET,
    MEDIA_TYPE_MUSIC, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP, SUPPORT_PLAY)
from homeassistant.const import (
    STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING, DEVICE_DEFAULT_NAME)
from homeassistant.util.dt import utcnow
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import (DOMAIN, CONF_CUSTOM_PLAY_ACTION)

DEPENDENCIES = ['roon']

SUPPORT_ROON = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_STOP | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | SUPPORT_SHUFFLE_SET | \
    SUPPORT_SEEK | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_VOLUME_MUTE | \
    SUPPORT_PLAY | SUPPORT_PLAY_MEDIA | SUPPORT_SELECT_SOURCE | SUPPORT_VOLUME_STEP

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Old method of setting up Roon mediaplayers."""
    pass
    

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Roon MediaPlayer from Config Entry."""
    roon_server = hass.data[DOMAIN][config_entry.data["host"]]
    media_players = {}
    @callback
    def async_update_media_player(player_data):
        """Add or update Roon MediaPlayer."""
        dev_id = player_data['dev_id']
        if dev_id not in media_players:
            # new player!
            media_player = RoonDevice(roon_server, player_data)
            media_players[dev_id] = media_player
            async_add_entities([media_player])
        else:
            # update existing player
            media_player = media_players[dev_id]
            if media_player and media_player.entity_id:
                media_player.update_data(player_data)
                media_player.async_update_callback(media_player.unique_id)
    # start listening for players to be added or changed by the server component
    async_dispatcher_connect(hass, 'roon_media_player', async_update_media_player)


class RoonDevice(MediaPlayerEntity):
    """Representation of an Roon device."""

    def __init__(self, server, player_data):
        """Initialize Roon device object."""
        self._sources = []
        self._server = server
        self._available = True
        self._last_position_update = None
        self._supports_standby = False
        self._state = STATE_IDLE
        self._last_playlist = None
        self.update_data(player_data)
        

    @property
    def hidden(self):
        """Return True if entity should be hidden from UI."""
        return not self._available

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_ROON

    @property
    def device_info(self):
        """Return the device info."""
        dev_model = "player"
        if self.player_data.get('source_controls'):
            dev_model = self.player_data['source_controls'][0].get('display_name')
        return {
            'identifiers': {
                (DOMAIN, self.unique_id)
            },
            'name': self.name,
            'manufacturer': "RoonLabs",
            'model': dev_model,
            'via_hub': (DOMAIN, self._server.host)
        }

    async def async_update(self):
        """Retrieve the current state of the player."""
        self.update_data(self.player_data)

    def update_data(self, player_data=None):
        """ Update session object. """
        if player_data:
            self.player_data = player_data
        if not self.player_data["is_available"]:
            # this player was removed
            self._available = False
            self._state = STATE_OFF
        else:
            self._available = True
            self._sources = self.get_sync_zones()
            # determine player state
            self.update_state()
            if self.state == STATE_PLAYING:
                self._last_position_update = utcnow()
        
    def update_state(self):
        ''' update the power state and player state '''
        cur_state = self._state
        new_state = ""
        # power state from source control (if supported)
        if 'source_controls' in self.player_data:
            for source in self.player_data["source_controls"]:
                if source["supports_standby"]:
                    if not source["status"] == "indeterminate":
                        self._supports_standby = True
                        if source["status"] in ["standby", "deselected"]:
                            new_state = STATE_OFF
                        break
        # determine player state
        if not new_state:
            if self.player_data['state'] == 'playing':
                new_state = STATE_PLAYING
            elif self.player_data['state'] == 'loading':
                new_state = STATE_PLAYING
            elif self.player_data['state'] == 'stopped':
                new_state = STATE_IDLE
            elif self.player_data['state'] == 'paused':
                new_state = STATE_PAUSED
            else:
                new_state = STATE_IDLE
        self._state = new_state

    async def async_added_to_hass(self):
        """Register callback."""
        _LOGGER.info("New Roon Device %s initialized with ID: %s" % (self.entity_id, self.unique_id))

    @callback
    def async_update_callback(self, msg):
        """Handle device updates."""
        self.async_schedule_update_ha_state()

    def get_sync_zones(self):
        ''' get available sync slaves'''
        sync_zones = [self.name]
        for zone in self._server.zones.values():
            for output in zone["outputs"]:
                if output["output_id"] in self.player_data["can_group_with_output_ids"] and zone['display_name'] not in sync_zones:
                    sync_zones.append( zone["display_name"] )
        _LOGGER.debug("sync_slaves for player %s: %s" % (self.name, sync_zones))
        return sync_zones

    @property
    def media_position_updated_at(self):
        """
        When was the position of the current playing media valid.
        Returns value from homeassistant.util.dt.utcnow().
        """
        return self._last_position_update

    @property
    def last_changed(self):
        ''' when was the object last updated on the server'''
        return self.player_data["last_changed"]

    @property
    def unique_id(self):
        """Return the id of this roon client."""
        return self.player_data['dev_id']

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def zone_id(self):
        """ Return current session Id. """
        try:
            return self.player_data['zone_id']
        except KeyError:
            return None

    @property
    def output_id(self):
        """ Return current session Id. """
        try:
            return self.player_data['output_id']
        except KeyError:
            return None

    @property
    def name(self):
        """ Return device name."""
        try:
            return self.player_data['display_name']
        except KeyError:
            return DEVICE_DEFAULT_NAME

    @property
    def media_title(self):
        """ Return title currently playing."""
        try:
            return self.player_data['now_playing']['three_line']['line1']
        except KeyError:
            return None

    @property
    def media_album_name(self):
        """Album name of current playing media (Music track only)."""
        try:
            return self.player_data['now_playing']['three_line']['line3']
        except KeyError:
            return None

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        try:
            return self.player_data['now_playing']['three_line']['line2']
        except KeyError:
            return None

    @property
    def media_album_artist(self):
        """Album artist of current playing media (Music track only)."""
        return self.media_artist

    @property
    def media_playlist(self):
        """Title of Playlist currently playing."""
        return self._last_playlist

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        try:
            image_id = self.player_data['now_playing']['image_key']
            url = self._server.roonapi.get_image(image_id)
            return url
        except KeyError:
            return None

    @property
    def media_position(self):
        """ Return position currently playing."""
        try:
            return int(self.player_data['now_playing']['seek_position'])
        except (KeyError, TypeError):
            return 0

    @property
    def media_duration(self):
        """ Return total runtime length."""
        try:
            return int(
                self.player_data['now_playing']['length'])
        except (KeyError, TypeError):
            return 0

    @property
    def media_percent_played(self):
        """ Return media percent played. """
        try:
            return (self.media_position / self.media_runtime) * 100
        except (KeyError, TypeError):
            return 0

    @property
    def volume_level(self):
        """ Return current volume level"""
        try:
            if self.player_data["volume"]["type"] == "db":
                return (int(float(self.player_data['volume']['value'] / 80) * 100) + 100) / 100
            return int(self.player_data['volume']['value']) / 100
        except (KeyError, TypeError):
            return 0

    @property
    def is_volume_muted(self):
        """ Return mute state """
        try:
            return self.player_data['volume']['is_muted']
        except (KeyError, TypeError):
            return False

    @property
    def volume_step(self):
        """ Return volume step size"""
        try:
            return int(
                self.player_data['volume']['step'])
        except (KeyError, TypeError):
            return 0

    @property
    def supports_standby(self):
        '''return power state of source controls'''
        return self._supports_standby

    @property
    def state(self):
        """ Return current playstate of the device. """
        return self._state

    @property
    def is_nowplaying(self):
        """ Return true if an item is currently active. """
        return self.state == STATE_PLAYING

    @property
    def source(self):
        """Name of the current input source."""
        return self.player_data['zone_name']

    @property
    def source_list(self):
        """List of available input sources."""
        return self._sources
        
    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        try:
            return self.player_data['settings']['shuffle']
        except (KeyError, TypeError):
            return False

    @property
    def repeat(self):
        """Boolean if repeat is enabled."""
        try:
            return self.player_data['settings']['loop']
        except (KeyError, TypeError):
            return False

    def media_play(self):
        """ Send play command to device. """
        self._server.roonapi.playback_control(self.output_id, "play")

    def media_pause(self):
        """ Send pause command to device. """
        self._server.roonapi.playback_control(self.output_id, "pause")

    def media_play_pause(self):
        """ toggle play command to device. """
        self._server.roonapi.playback_control(self.output_id, "playpause")

    def media_stop(self):
        """ Send stop command to device. """
        self._server.roonapi.playback_control(self.output_id, "stop")

    def media_next_track(self):
        """ Send next track command to device. """
        self._server.roonapi.playback_control(self.output_id, "next")

    def media_previous_track(self):
        """ Send previous track command to device. """
        self._server.roonapi.playback_control(self.output_id, "previous")

    def media_seek(self, position):
        """ Send seek command to device. """
        self._server.roonapi.seek(self.output_id, position)

    def set_volume_level(self, volume):
        """ Send new volume_level to device. """
        volume = int(volume * 100)
        try:
            self._server.roonapi.change_volume(self.output_id, volume)
        except Exception as exc:
            _LOGGER.error("set_volume_level failed for entity %s \n %s" %(self.entity_id, str(exc)))

    def mute_volume(self, mute=True):
        """ Send mute/unmute to device. """
        self._server.roonapi.mute(self.output_id, mute)

    def volume_up(self):
        """ Send new volume_level to device. """
        self._server.roonapi.change_volume(self.output_id, 3, "relative")

    def volume_down(self):
        """ Send new volume_level to device. """
        self._server.roonapi.change_volume(self.output_id, -3, "relative")

    def turn_on(self):
        """ Turn on device (if supported) """
        if self.supports_standby and 'source_controls' in self.player_data:
            for source in self.player_data["source_controls"]:
                if source["supports_standby"] and source["status"] != "indeterminate":
                    self._server.roonapi.convenience_switch(self.output_id, source["control_key"])
                    break
        else:
            return self.media_play()

    def turn_off(self):
        """ Turn off device (if supported) """
        if self.supports_standby and 'source_controls' in self.player_data:
            for source in self.player_data["source_controls"]:
                if source["supports_standby"] and not source["status"] == "indeterminate":
                    self._server.roonapi.standby(self.output_id, source["control_key"])
                    break
        else:
            return self.media_stop()

    def set_shuffle(self, shuffle):
        """ Set shuffle state on zone """
        self._server.roonapi.shuffle(self.output_id, shuffle)

    def select_source(self, source):
        '''select source on player (used to sync/unsync)'''
        _LOGGER.info("select source called - unsync %s" %(self.name))
        if source == self.name:
            self._server.roonapi.ungroup_outputs([self.output_id])
        else:
            _LOGGER.info("select source called - sync %s with %s" %(self.name, source))
            output_ids = []
            for zone_id, zone in self._server.zones.items():
                if zone["display_name"].lower() == source.lower():
                    for output in zone["outputs"]:
                        output_ids.append(output["output_id"])
                    output_ids.append(self.output_id)
                    self._server.roonapi.group_outputs(output_ids)
                    break

    def play_media(self, media_type, media_id, **kwargs):
        """
            Send the play_media command to the media player.
            Roon itself doesn't support playback of media by filename/url so this a bit of a workaround.
        """
        media_type = media_type.lower()
        if media_type == "radio":
            if self._server.roonapi.play_radio(self.zone_id, media_id):
                self._last_playlist = media_id
                self._last_media = media_id
        elif media_type == "playlist":
            if self._server.roonapi.play_playlist(self.zone_id, media_id, shuffle=False):
                self._last_playlist = media_id
        elif media_type == "shuffleplaylist":
            if self._server.roonapi.play_playlist(self.zone_id, media_id, shuffle=True):
                self._last_playlist = media_id
        elif media_type == "queueplaylist":
            self._server.roonapi.queue_playlist(self.zone_id, media_id)
        elif media_type == "genre":
            self._server.roonapi.play_genre(self.zone_id, media_id)
        elif self._server.custom_play_action:
            # reroute the play request to the given custom script
            _LOGGER.debug("Playback requested. Will forward to custom script/action: %s" % self._server.custom_play_action)
            data = {
                "entity_id": self.entity_id,
                "media_type": media_type,
                "media_id": media_id,
            }
            _domain, _entity = self._server.custom_play_action.split(".")
            self.hass.services.call(_domain, _entity, data, blocking=False)
        else:
            _LOGGER.info("Playback requested of unsupported type: %s --> %s" %(media_type, media_id))
