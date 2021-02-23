"""Media Player component to integrate TVs exposing the Joint Space API."""
from typing import Any, Dict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player import (
    DEVICE_CLASS_TV,
    PLATFORM_SCHEMA,
    BrowseMedia,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_CHANNEL,
    MEDIA_CLASS_DIRECTORY,
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
from homeassistant.components.philips_js import PhilipsTVDataUpdateCoordinator
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LOGGER as _LOGGER
from .const import CONF_SYSTEM, DOMAIN

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

DEFAULT_API_VERSION = 1

PREFIX_SEPARATOR = ": "
PREFIX_SOURCE = "Input"
PREFIX_CHANNEL = "Channel"

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_HOST),
    cv.deprecated(CONF_NAME),
    cv.deprecated(CONF_API_VERSION),
    cv.deprecated(CONF_ON_ACTION),
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Remove(CONF_NAME): cv.string,
            vol.Optional(CONF_API_VERSION, default=DEFAULT_API_VERSION): vol.Coerce(
                int
            ),
            vol.Remove(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
        }
    ),
)


def _inverted(data):
    return {v: k for k, v in data.items()}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Philips TV platform."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Set up the configuration entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            PhilipsTVMediaPlayer(
                coordinator,
                config_entry.data[CONF_SYSTEM],
                config_entry.unique_id,
            )
        ]
    )


class PhilipsTVMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a Philips TV exposing the JointSpace API."""

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
        system: Dict[str, Any],
        unique_id: str,
    ):
        """Initialize the Philips TV."""
        self._tv = coordinator.api
        self._coordinator = coordinator
        self._sources = {}
        self._channels = {}
        self._supports = SUPPORT_PHILIPS_JS
        self._system = system
        self._unique_id = unique_id
        super().__init__(coordinator)
        self._update_from_coordinator()

    def _update_soon(self):
        """Reschedule update task."""
        self.hass.add_job(self.coordinator.async_request_refresh)

    @property
    def name(self):
        """Return the device name."""
        return self._system["name"]

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        supports = self._supports
        if self._coordinator.turn_on:
            supports |= SUPPORT_TURN_ON
        return supports

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
        self._update_soon()

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._tv.volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._tv.muted

    async def async_turn_on(self):
        """Turn on the device."""
        await self._coordinator.turn_on.async_run(self.hass, self._context)

    def turn_off(self):
        """Turn off the device."""
        self._tv.sendKey("Standby")
        self._tv.on = False
        self._update_soon()

    def volume_up(self):
        """Send volume up command."""
        self._tv.sendKey("VolumeUp")
        self._update_soon()

    def volume_down(self):
        """Send volume down command."""
        self._tv.sendKey("VolumeDown")
        self._update_soon()

    def mute_volume(self, mute):
        """Send mute command."""
        self._tv.setVolume(None, mute)
        self._update_soon()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._tv.setVolume(volume, self._tv.muted)
        self._update_soon()

    def media_previous_track(self):
        """Send rewind command."""
        self._tv.sendKey("Previous")
        self._update_soon()

    def media_next_track(self):
        """Send fast forward command."""
        self._tv.sendKey("Next")
        self._update_soon()

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

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TV

    @property
    def unique_id(self):
        """Return unique identifier if known."""
        return self._unique_id

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "name": self._system["name"],
            "identifiers": {
                (DOMAIN, self._unique_id),
            },
            "model": self._system.get("model"),
            "manufacturer": "Philips",
            "sw_version": self._system.get("softwareversion"),
        }

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        _LOGGER.debug("Call play media type <%s>, Id <%s>", media_type, media_id)

        if media_type == MEDIA_TYPE_CHANNEL:
            channel_id = _inverted(self._channels).get(media_id)
            if channel_id:
                self._tv.setChannel(channel_id)
                self._update_soon()
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
            media_class=MEDIA_CLASS_DIRECTORY,
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

    def _update_from_coordinator(self):
        self._sources = {
            srcid: source.get("name") or f"Source {srcid}"
            for srcid, source in (self._tv.sources or {}).items()
        }

        self._channels = {
            chid: channel.get("name") or f"Channel {chid}"
            for chid, channel in (self._tv.channels or {}).items()
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator()
        super()._handle_coordinator_update()
