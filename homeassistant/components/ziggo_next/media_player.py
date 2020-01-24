"""Support for interface with a Ziggo Mediabox Next."""
import logging
import random

from ziggonext import ONLINE_RUNNING, ONLINE_STANDBY, ZiggoNext

from homeassistant.components.media_player import MediaPlayerDevice
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_TVSHOW,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
)
from homeassistant.const import (
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
)

from .const import DOMAIN, ZIGGO_API

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    players = []
    api = hass.data[ZIGGO_API]
    for box_id in api.settopBoxes.keys():
        box = api.settopBoxes[box_id]
        players.append(ZiggoNextMediaPlayer(box_id, box.name, api))
    async_add_devices(players, update_before_add=True)


class ZiggoNextMediaPlayer(MediaPlayerDevice):
    """The home assistant media player."""

    @property
    def device_info(self):
        """Retusns device info."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.box_id)
            },
            "name": self.box_name,
            # "manufacturer": self.light.manufacturername,
            # "model": self.light.productname,
            # "sw_version": self.light.swversion,
            # "via_device": (hue.DOMAIN, self.api.bridgeid),
        }

    def __init__(self, box_id: str, name: str, api: ZiggoNext):
        """Init the media player."""
        self.api = api
        self.box_id = box_id
        self.box_name = name
        self.box_state = None
        self.box_info = None

    def update(self):
        """Update the box."""
        self.api.load_channels()
        box = self.api.settopBoxes[self.box_id]
        self.box_state = box.state
        self.box_info = box.info

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.box_name

    @property
    def state(self):
        """Return the state of the player."""
        if self.box_state == ONLINE_RUNNING:
            if self.box_info is not None and self.box_info.paused:
                return STATE_PAUSED
            return STATE_PLAYING
        elif self.box_state == ONLINE_STANDBY:
            return STATE_OFF
        return STATE_UNAVAILABLE

    @property
    def media_content_type(self):
        """Return the media type."""
        return MEDIA_TYPE_TVSHOW

    @property
    def supported_features(self):
        """Return the supported features."""
        return (
            SUPPORT_PLAY
            | SUPPORT_PAUSE
            | SUPPORT_TURN_ON
            | SUPPORT_TURN_OFF
            | SUPPORT_SELECT_SOURCE
            | SUPPORT_NEXT_TRACK
            | SUPPORT_PREVIOUS_TRACK
        )

    @property
    def available(self):
        """Return True if the device is available."""
        available = self.api.is_available(self.box_id)
        return available

    def turn_on(self):
        """Turn the media player on."""
        self.api.turn_on(self.box_id)

    def turn_off(self):
        """Turn the media player off."""
        self.api.turn_off(self.box_id)

    @property
    def media_image_url(self):
        """Return the media image URL."""
        if self.box_info.image is not None:
            return self.box_info.image + "?" + str(random.randrange(1000000))
        return None

    @property
    def media_title(self):
        """Return the media title."""
        return self.box_info.title

    @property
    def source(self):
        """Name of the current channel."""
        return self.box_info.channelTitle

    @property
    def source_list(self):
        """Return a list with available sources."""
        return [channel.title for channel in self.api.channels.values()]

    def select_source(self, source):
        """Select a new source."""
        self.api.select_source(source, self.box_id)

    def media_play(self):
        """Play selected box."""
        self.api.play(self.box_id)

    def media_pause(self):
        """Pause the given box."""
        self.api.pause(self.box_id)

    def media_next_track(self):
        """Send next track command."""
        self.api.next_channel(self.box_id)

    def media_previous_track(self):
        """Send previous track command."""
        self.api.previous_channel(self.box_id)

    @property
    def unique_id(self):
        """Return the unique id."""
        return self.box_id
