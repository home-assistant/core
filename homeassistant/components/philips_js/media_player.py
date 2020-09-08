"""Media Player component to integrate TVs exposing the Joint Space API."""
from datetime import timedelta
import logging

from haphilipsjs import PhilipsTV
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    BrowseMedia,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_CHANNEL,
    MEDIA_CLASS_CHANNELS,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_CHANNELS,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import call_later, track_time_interval
from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)

SUPPORT_PHILIPS_JS = (
    SUPPORT_TURN_OFF
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_BROWSE_MEDIA
)

CONF_ON_ACTION = "turn_on_action"

DEFAULT_NAME = "Philips TV"
DEFAULT_API_VERSION = "1"
DEFAULT_SCAN_INTERVAL = 30

DELAY_ACTION_DEFAULT = 2.0
DELAY_ACTION_ON = 10.0

PREFIX_SEPARATOR = ": "
PREFIX_SOURCE = "Input"
PREFIX_CHANNEL = "Channel"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_API_VERSION, default=DEFAULT_API_VERSION): cv.string,
        vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
    }
)


def _inverted(data):
    return {v: k for k, v in data.items()}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Philips TV platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    api_version = config.get(CONF_API_VERSION)
    turn_on_action = config.get(CONF_ON_ACTION)

    tvapi = PhilipsTV(host, api_version)
    domain = __name__.split(".")[-2]
    on_script = Script(hass, turn_on_action, name, domain) if turn_on_action else None

    add_entities([PhilipsTVMediaPlayer(tvapi, name, on_script)])


class PhilipsTVMediaPlayer(MediaPlayerEntity):
    """Representation of a Philips TV exposing the JointSpace API."""

    def __init__(self, tv, name, on_script):
        """Initialize the Philips TV."""
        self._tv = tv
        self._name = name
        self._sources = {}
        self._channels = {}
        self._on_script = on_script
        self._supports = SUPPORT_PHILIPS_JS
        if self._on_script:
            self._supports |= SUPPORT_TURN_ON
        self._update_task = None

    def _update_soon(self, delay):
        """Reschedule update task."""
        if self._update_task:
            self._update_task()
            self._update_task = None

        self.schedule_update_ha_state(force_refresh=False)

        def update_forced(event_time):
            self.schedule_update_ha_state(force_refresh=True)

        def update_and_restart(event_time):
            update_forced(event_time)
            self._update_task = track_time_interval(
                self.hass, update_forced, timedelta(seconds=DEFAULT_SCAN_INTERVAL)
            )

        call_later(self.hass, delay, update_and_restart)

    async def async_added_to_hass(self):
        """Start running updates once we are added to hass."""
        await self.hass.async_add_executor_job(self._update_soon, 0)

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def should_poll(self):
        """Device should be polled."""
        return False

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return self._supports

    @property
    def state(self):
        """Get the device state. An exception means OFF state."""
        if self._tv.on:
            return STATE_ON
        return STATE_OFF

    @property
    def source(self):
        """Return the current input source."""
        return self._sources.get(self._tv.source_id)

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._sources.values())

    def select_source(self, source):
        """Set the input source."""
        data = source.split(PREFIX_SEPARATOR, 1)
        if data[0] == PREFIX_SOURCE:  # Legacy way to set source
            source_id = _inverted(self._sources).get(data[1])
            if source_id:
                self._tv.setSource(source_id)
        elif data[0] == PREFIX_CHANNEL:  # Legacy way to set channel
            channel_id = _inverted(self._channels).get(data[1])
            if channel_id:
                self._tv.setChannel(channel_id)
        else:
            source_id = _inverted(self._sources).get(source)
            if source_id:
                self._tv.setSource(source_id)
        self._update_soon(DELAY_ACTION_DEFAULT)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._tv.volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._tv.muted

    def turn_on(self):
        """Turn on the device."""
        if self._on_script:
            self._on_script.run()
            self._update_soon(DELAY_ACTION_ON)

    def turn_off(self):
        """Turn off the device."""
        self._tv.sendKey("Standby")
        self._tv.on = False
        self._update_soon(DELAY_ACTION_DEFAULT)

    def volume_up(self):
        """Send volume up command."""
        self._tv.sendKey("VolumeUp")
        self._update_soon(DELAY_ACTION_DEFAULT)

    def volume_down(self):
        """Send volume down command."""
        self._tv.sendKey("VolumeDown")
        self._update_soon(DELAY_ACTION_DEFAULT)

    def mute_volume(self, mute):
        """Send mute command."""
        self._tv.setVolume(None, mute)
        self._update_soon(DELAY_ACTION_DEFAULT)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._tv.setVolume(volume, self._tv.muted)
        self._update_soon(DELAY_ACTION_DEFAULT)

    def media_previous_track(self):
        """Send rewind command."""
        self._tv.sendKey("Previous")
        self._update_soon(DELAY_ACTION_DEFAULT)

    def media_next_track(self):
        """Send fast forward command."""
        self._tv.sendKey("Next")
        self._update_soon(DELAY_ACTION_DEFAULT)

    @property
    def media_channel(self):
        """Get current channel if it's a channel."""
        if self.media_content_type == MEDIA_TYPE_CHANNEL:
            return self._channels.get(self._tv.channel_id)
        return None

    @property
    def media_title(self):
        """Title of current playing media."""
        if self.media_content_type == MEDIA_TYPE_CHANNEL:
            return self._channels.get(self._tv.channel_id)
        return self._sources.get(self._tv.source_id)

    @property
    def media_content_type(self):
        """Return content type of playing media."""
        if self._tv.source_id == "tv" or self._tv.source_id == "11":
            return MEDIA_TYPE_CHANNEL
        if self._tv.source_id is None and self._tv.channels:
            return MEDIA_TYPE_CHANNEL
        return None

    @property
    def media_content_id(self):
        """Content type of current playing media."""
        if self.media_content_type == MEDIA_TYPE_CHANNEL:
            return self._channels.get(self._tv.channel_id)
        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"channel_list": list(self._channels.values())}

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        _LOGGER.debug("Call play media type <%s>, Id <%s>", media_type, media_id)

        if media_type == MEDIA_TYPE_CHANNEL:
            channel_id = _inverted(self._channels).get(media_id)
            if channel_id:
                self._tv.setChannel(channel_id)
                self._update_soon(DELAY_ACTION_DEFAULT)
            else:
                _LOGGER.error("Unable to find channel <%s>", media_id)
        else:
            _LOGGER.error("Unsupported media type <%s>", media_type)

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""
        if media_content_id not in (None, ""):
            raise BrowseError(
                f"Media not found: {media_content_type} / {media_content_id}"
            )

        return BrowseMedia(
            title="Channels",
            media_class=MEDIA_CLASS_CHANNELS,
            media_content_id="",
            media_content_type=MEDIA_TYPE_CHANNELS,
            can_play=False,
            can_expand=True,
            children=[
                BrowseMedia(
                    title=channel,
                    media_class=MEDIA_CLASS_CHANNEL,
                    media_content_id=channel,
                    media_content_type=MEDIA_TYPE_CHANNEL,
                    can_play=True,
                    can_expand=False,
                )
                for channel in self._channels.values()
            ],
        )

    def update(self):
        """Get the latest data and update device state."""
        self._tv.update()

        self._sources = {
            srcid: source["name"] or f"Source {srcid}"
            for srcid, source in (self._tv.sources or {}).items()
        }

        self._channels = {
            chid: channel["name"] for chid, channel in (self._tv.channels or {}).items()
        }
