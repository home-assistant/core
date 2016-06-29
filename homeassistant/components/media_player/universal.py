"""
Combination of multiple media players into one for a universal controller.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.universal/
"""

import logging
# pylint: disable=import-error
from copy import copy

from homeassistant.components.media_player import (
    ATTR_APP_ID, ATTR_APP_NAME, ATTR_MEDIA_ALBUM_ARTIST, ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST, ATTR_MEDIA_CHANNEL, ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE, ATTR_MEDIA_DURATION, ATTR_MEDIA_EPISODE,
    ATTR_MEDIA_PLAYLIST, ATTR_MEDIA_SEASON, ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SERIES_TITLE, ATTR_MEDIA_TITLE, ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL, ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SUPPORTED_MEDIA_COMMANDS, DOMAIN, SERVICE_PLAY_MEDIA,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP, SUPPORT_SELECT_SOURCE, ATTR_INPUT_SOURCE,
    SERVICE_SELECT_SOURCE, MediaPlayerDevice)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_ENTITY_PICTURE, CONF_NAME, SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_PLAY, SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK, SERVICE_MEDIA_SEEK, SERVICE_TURN_OFF,
    SERVICE_TURN_ON, SERVICE_VOLUME_DOWN, SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET, SERVICE_VOLUME_UP, STATE_IDLE, STATE_OFF, STATE_ON,
    SERVICE_MEDIA_STOP)
from homeassistant.helpers.event import track_state_change
from homeassistant.helpers.service import call_from_config

ATTR_ACTIVE_CHILD = 'active_child'

CONF_ATTRS = 'attributes'
CONF_CHILDREN = 'children'
CONF_COMMANDS = 'commands'
CONF_PLATFORM = 'platform'
CONF_SERVICE = 'service'
CONF_SERVICE_DATA = 'service_data'
CONF_STATE = 'state'

OFF_STATES = [STATE_IDLE, STATE_OFF]
REQUIREMENTS = []
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the universal media players."""
    if not validate_config(config):
        return

    player = UniversalMediaPlayer(hass,
                                  config[CONF_NAME],
                                  config[CONF_CHILDREN],
                                  config[CONF_COMMANDS],
                                  config[CONF_ATTRS])

    add_devices([player])


def validate_config(config):
    """Validate universal media player configuration."""
    del config[CONF_PLATFORM]

    # Validate name
    if CONF_NAME not in config:
        _LOGGER.error('Universal Media Player configuration requires name')
        return False

    validate_children(config)
    validate_commands(config)
    validate_attributes(config)

    del_keys = []
    for key in config:
        if key not in [CONF_NAME, CONF_CHILDREN, CONF_COMMANDS, CONF_ATTRS]:
            _LOGGER.warning(
                'Universal Media Player (%s) unrecognized parameter %s',
                config[CONF_NAME], key)
            del_keys.append(key)
    for key in del_keys:
        del config[key]

    return True


def validate_children(config):
    """Validate children."""
    if CONF_CHILDREN not in config:
        _LOGGER.info(
            'No children under Universal Media Player (%s)', config[CONF_NAME])
        config[CONF_CHILDREN] = []
    elif not isinstance(config[CONF_CHILDREN], list):
        _LOGGER.warning(
            'Universal Media Player (%s) children not list in config. '
            'They will be ignored.',
            config[CONF_NAME])
        config[CONF_CHILDREN] = []


def validate_commands(config):
    """Validate commands."""
    if CONF_COMMANDS not in config:
        config[CONF_COMMANDS] = {}
    elif not isinstance(config[CONF_COMMANDS], dict):
        _LOGGER.warning(
            'Universal Media Player (%s) specified commands not dict in '
            'config. They will be ignored.',
            config[CONF_NAME])
        config[CONF_COMMANDS] = {}


def validate_attributes(config):
    """Validate attributes."""
    if CONF_ATTRS not in config:
        config[CONF_ATTRS] = {}
    elif not isinstance(config[CONF_ATTRS], dict):
        _LOGGER.warning(
            'Universal Media Player (%s) specified attributes '
            'not dict in config. They will be ignored.',
            config[CONF_NAME])
        config[CONF_ATTRS] = {}

    for key, val in config[CONF_ATTRS].items():
        attr = val.split('|', 1)
        if len(attr) == 1:
            attr.append(None)
        config[CONF_ATTRS][key] = attr


class UniversalMediaPlayer(MediaPlayerDevice):
    """Representation of an universal media player."""

    # pylint: disable=too-many-public-methods
    def __init__(self, hass, name, children, commands, attributes):
        """Initialize the Universal media device."""
        # pylint: disable=too-many-arguments
        self.hass = hass
        self._name = name
        self._children = children
        self._cmds = commands
        self._attrs = attributes
        self._child_state = None

        def on_dependency_update(*_):
            """Update ha state when dependencies update."""
            self.update_ha_state(True)

        depend = copy(children)
        for entity in attributes.values():
            depend.append(entity[0])

        track_state_change(hass, depend, on_dependency_update)

    def _entity_lkp(self, entity_id, state_attr=None):
        """Look up an entity state."""
        state_obj = self.hass.states.get(entity_id)

        if state_obj is None:
            return

        if state_attr:
            return state_obj.attributes.get(state_attr)
        return state_obj.state

    def _override_or_child_attr(self, attr_name):
        """Return either the override or the active child for attr_name."""
        if attr_name in self._attrs:
            return self._entity_lkp(self._attrs[attr_name][0],
                                    self._attrs[attr_name][1])

        return self._child_attr(attr_name)

    def _child_attr(self, attr_name):
        """Return the active child's attributes."""
        active_child = self._child_state
        return active_child.attributes.get(attr_name) if active_child else None

    def _call_service(self, service_name, service_data=None,
                      allow_override=False):
        """Call either a specified or active child's service."""
        if allow_override and service_name in self._cmds:
            call_from_config(
                self.hass, self._cmds[service_name], blocking=True)
            return

        if service_data is None:
            service_data = {}

        active_child = self._child_state
        service_data[ATTR_ENTITY_ID] = active_child.entity_id

        self.hass.services.call(DOMAIN, service_name, service_data,
                                blocking=True)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def master_state(self):
        """Return the master state for entity or None."""
        if CONF_STATE in self._attrs:
            master_state = self._entity_lkp(self._attrs[CONF_STATE][0],
                                            self._attrs[CONF_STATE][1])
            return master_state if master_state else STATE_OFF
        else:
            return None

    @property
    def name(self):
        """Return the name of universal player."""
        return self._name

    @property
    def state(self):
        """Current state of media player.

        Off if master state is off
        else Status of first active child
        else master state or off
        """
        master_state = self.master_state  # avoid multiple lookups
        if master_state == STATE_OFF:
            return STATE_OFF

        active_child = self._child_state
        if active_child:
            return active_child.state

        return master_state if master_state else STATE_OFF

    @property
    def volume_level(self):
        """Volume level of entity specified in attributes or active child."""
        return self._child_attr(ATTR_MEDIA_VOLUME_LEVEL)

    @property
    def is_volume_muted(self):
        """Boolean if volume is muted."""
        return self._override_or_child_attr(ATTR_MEDIA_VOLUME_MUTED) \
            in [True, STATE_ON]

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._child_attr(ATTR_MEDIA_CONTENT_ID)

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return self._child_attr(ATTR_MEDIA_CONTENT_TYPE)

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._child_attr(ATTR_MEDIA_DURATION)

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._child_attr(ATTR_ENTITY_PICTURE)

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._child_attr(ATTR_MEDIA_TITLE)

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        return self._child_attr(ATTR_MEDIA_ARTIST)

    @property
    def media_album_name(self):
        """Album name of current playing media (Music track only)."""
        return self._child_attr(ATTR_MEDIA_ALBUM_NAME)

    @property
    def media_album_artist(self):
        """Album artist of current playing media (Music track only)."""
        return self._child_attr(ATTR_MEDIA_ALBUM_ARTIST)

    @property
    def media_track(self):
        """Track number of current playing media (Music track only)."""
        return self._child_attr(ATTR_MEDIA_TRACK)

    @property
    def media_series_title(self):
        """The title of the series of current playing media (TV Show only)."""
        return self._child_attr(ATTR_MEDIA_SERIES_TITLE)

    @property
    def media_season(self):
        """Season of current playing media (TV Show only)."""
        return self._child_attr(ATTR_MEDIA_SEASON)

    @property
    def media_episode(self):
        """Episode of current playing media (TV Show only)."""
        return self._child_attr(ATTR_MEDIA_EPISODE)

    @property
    def media_channel(self):
        """Channel currently playing."""
        return self._child_attr(ATTR_MEDIA_CHANNEL)

    @property
    def media_playlist(self):
        """Title of Playlist currently playing."""
        return self._child_attr(ATTR_MEDIA_PLAYLIST)

    @property
    def app_id(self):
        """ID of the current running app."""
        return self._child_attr(ATTR_APP_ID)

    @property
    def app_name(self):
        """Name of the current running app."""
        return self._child_attr(ATTR_APP_NAME)

    @property
    def current_source(self):
        """"Return the current input source of the device."""
        return self._child_attr(ATTR_INPUT_SOURCE)

    @property
    def supported_media_commands(self):
        """Flag media commands that are supported."""
        flags = self._child_attr(ATTR_SUPPORTED_MEDIA_COMMANDS) or 0

        if SERVICE_TURN_ON in self._cmds:
            flags |= SUPPORT_TURN_ON
        if SERVICE_TURN_OFF in self._cmds:
            flags |= SUPPORT_TURN_OFF

        if any([cmd in self._cmds for cmd in [SERVICE_VOLUME_UP,
                                              SERVICE_VOLUME_DOWN]]):
            flags |= SUPPORT_VOLUME_STEP
            flags &= ~SUPPORT_VOLUME_SET

        if SERVICE_VOLUME_MUTE in self._cmds and \
                ATTR_MEDIA_VOLUME_MUTED in self._attrs:
            flags |= SUPPORT_VOLUME_MUTE

        if SUPPORT_SELECT_SOURCE in self._cmds:
            flags |= SUPPORT_SELECT_SOURCE

        return flags

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        active_child = self._child_state
        return {ATTR_ACTIVE_CHILD: active_child.entity_id} \
            if active_child else {}

    def turn_on(self):
        """Turn the media player on."""
        self._call_service(SERVICE_TURN_ON, allow_override=True)

    def turn_off(self):
        """Turn the media player off."""
        self._call_service(SERVICE_TURN_OFF, allow_override=True)

    def mute_volume(self, is_volume_muted):
        """Mute the volume."""
        data = {ATTR_MEDIA_VOLUME_MUTED: is_volume_muted}
        self._call_service(SERVICE_VOLUME_MUTE, data, allow_override=True)

    def set_volume_level(self, volume_level):
        """Set volume level, range 0..1."""
        data = {ATTR_MEDIA_VOLUME_LEVEL: volume_level}
        self._call_service(SERVICE_VOLUME_SET, data)

    def media_play(self):
        """Send play commmand."""
        self._call_service(SERVICE_MEDIA_PLAY)

    def media_pause(self):
        """Send pause command."""
        self._call_service(SERVICE_MEDIA_PAUSE)

    def media_stop(self):
        """Send stop command."""
        self._call_service(SERVICE_MEDIA_STOP)

    def media_previous_track(self):
        """Send previous track command."""
        self._call_service(SERVICE_MEDIA_PREVIOUS_TRACK)

    def media_next_track(self):
        """Send next track command."""
        self._call_service(SERVICE_MEDIA_NEXT_TRACK)

    def media_seek(self, position):
        """Send seek command."""
        data = {ATTR_MEDIA_SEEK_POSITION: position}
        self._call_service(SERVICE_MEDIA_SEEK, data)

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        data = {ATTR_MEDIA_CONTENT_TYPE: media_type,
                ATTR_MEDIA_CONTENT_ID: media_id}
        self._call_service(SERVICE_PLAY_MEDIA, data)

    def volume_up(self):
        """Turn volume up for media player."""
        self._call_service(SERVICE_VOLUME_UP, allow_override=True)

    def volume_down(self):
        """Turn volume down for media player."""
        self._call_service(SERVICE_VOLUME_DOWN, allow_override=True)

    def media_play_pause(self):
        """Play or pause the media player."""
        self._call_service(SERVICE_MEDIA_PLAY_PAUSE)

    def select_source(self, source):
        """Set the input source."""
        data = {ATTR_INPUT_SOURCE: source}
        self._call_service(SERVICE_SELECT_SOURCE, data)

    def update(self):
        """Update state in HA."""
        for child_name in self._children:
            child_state = self.hass.states.get(child_name)
            if child_state and child_state.state not in OFF_STATES:
                self._child_state = child_state
                return
        self._child_state = None
