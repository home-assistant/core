"""Support for the Mediaroom Set-up-box."""

from __future__ import annotations

import logging
from typing import Any

from pymediaroom import (
    COMMANDS,
    PyMediaroomError,
    Remote,
    State,
    install_mediaroom_protocol,
)
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_TIMEOUT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DATA_MEDIAROOM = "mediaroom_known_stb"
DEFAULT_NAME = "Mediaroom STB"
DEFAULT_TIMEOUT = 9
DISCOVERY_MEDIAROOM = "mediaroom_discovery_installed"

MEDIA_TYPE_MEDIAROOM = "mediaroom"

SIGNAL_STB_NOTIFY = "mediaroom_stb_discovered"


PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=False): cv.boolean,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Mediaroom platform."""
    if (known_hosts := hass.data.get(DATA_MEDIAROOM)) is None:
        known_hosts = hass.data[DATA_MEDIAROOM] = []
    if host := config.get(CONF_HOST):
        async_add_entities(
            [
                MediaroomDevice(
                    host=host,
                    device_id=None,
                    optimistic=config[CONF_OPTIMISTIC],
                    timeout=config[CONF_TIMEOUT],
                )
            ]
        )
        known_hosts.append(host)

    _LOGGER.debug("Trying to discover Mediaroom STB")

    def callback_notify(notify):
        """Process NOTIFY message from STB."""
        if notify.ip_address in known_hosts:
            dispatcher_send(hass, SIGNAL_STB_NOTIFY, notify)
            return

        _LOGGER.debug("Discovered new stb %s", notify.ip_address)
        known_hosts.append(notify.ip_address)
        new_stb = MediaroomDevice(
            host=notify.ip_address, device_id=notify.device_uuid, optimistic=False
        )
        async_add_entities([new_stb])

    if not config[CONF_OPTIMISTIC]:
        already_installed = hass.data.get(DISCOVERY_MEDIAROOM)
        if not already_installed:
            hass.data[DISCOVERY_MEDIAROOM] = await install_mediaroom_protocol(
                responses_callback=callback_notify
            )

            @callback
            def stop_discovery(event):
                """Stop discovery of new mediaroom STB's."""
                _LOGGER.debug("Stopping internal pymediaroom discovery")
                hass.data[DISCOVERY_MEDIAROOM].close()

            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_discovery)

            _LOGGER.debug("Auto discovery installed")


class MediaroomDevice(MediaPlayerEntity):
    """Representation of a Mediaroom set-up-box on the network."""

    _attr_media_content_type = MediaType.CHANNEL
    _attr_should_poll = False
    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.PLAY
    )

    def set_state(self, mediaroom_state):
        """Map pymediaroom state to HA state."""

        state_map = {
            State.OFF: MediaPlayerState.OFF,
            State.STANDBY: MediaPlayerState.STANDBY,
            State.PLAYING_LIVE_TV: MediaPlayerState.PLAYING,
            State.PLAYING_RECORDED_TV: MediaPlayerState.PLAYING,
            State.PLAYING_TIMESHIFT_TV: MediaPlayerState.PLAYING,
            State.STOPPED: MediaPlayerState.PAUSED,
            State.UNKNOWN: None,
        }

        self._attr_state = state_map[mediaroom_state]

    def __init__(self, host, device_id, optimistic=False, timeout=DEFAULT_TIMEOUT):
        """Initialize the device."""

        self.host = host
        self.stb = Remote(host)
        _LOGGER.info(
            "Found STB at %s%s", host, " - I'm optimistic" if optimistic else ""
        )
        self._channel = None
        self._optimistic = optimistic
        self._attr_state = (
            MediaPlayerState.PLAYING if optimistic else MediaPlayerState.STANDBY
        )
        self._name = f"Mediaroom {device_id if device_id else host}"
        self._available = True
        if device_id:
            self._unique_id = device_id
        else:
            self._unique_id = None

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    async def async_added_to_hass(self) -> None:
        """Retrieve latest state."""

        async def async_notify_received(notify):
            """Process STB state from NOTIFY message."""
            stb_state = self.stb.notify_callback(notify)
            # stb_state is None in case the notify is not from the current stb
            if not stb_state:
                return
            self.set_state(stb_state)
            _LOGGER.debug("STB(%s) is [%s]", self.host, self.state)
            self._available = True
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_STB_NOTIFY, async_notify_received
            )
        )

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media."""

        _LOGGER.debug(
            "STB(%s) Play media: %s (%s)", self.stb.stb_ip, media_id, media_type
        )
        command: str | int
        if media_type == MediaType.CHANNEL:
            if not media_id.isdigit():
                _LOGGER.error("Invalid media_id %s: Must be a channel number", media_id)
                return
            command = int(media_id)
        elif media_type == MEDIA_TYPE_MEDIAROOM:
            if media_id not in COMMANDS:
                _LOGGER.error("Invalid media_id %s: Must be a command", media_id)
                return
            command = media_id
        else:
            _LOGGER.error("Invalid media type %s", media_type)
            return

        try:
            await self.stb.send_cmd(command)
            if self._optimistic:
                self._attr_state = MediaPlayerState.PLAYING
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def media_channel(self):
        """Channel currently playing."""
        return self._channel

    async def async_turn_on(self) -> None:
        """Turn on the receiver."""

        try:
            self.set_state(await self.stb.turn_on())
            if self._optimistic:
                self._attr_state = MediaPlayerState.PLAYING
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn off the receiver."""

        try:
            self.set_state(await self.stb.turn_off())
            if self._optimistic:
                self._attr_state = MediaPlayerState.STANDBY
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        """Send play command."""

        try:
            _LOGGER.debug("media_play()")
            await self.stb.send_cmd("PlayPause")
            if self._optimistic:
                self._attr_state = MediaPlayerState.PLAYING
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        """Send pause command."""

        try:
            await self.stb.send_cmd("PlayPause")
            if self._optimistic:
                self._attr_state = MediaPlayerState.PAUSED
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        """Send stop command."""

        try:
            await self.stb.send_cmd("Stop")
            if self._optimistic:
                self._attr_state = MediaPlayerState.PAUSED
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_media_previous_track(self) -> None:
        """Send Program Down command."""

        try:
            await self.stb.send_cmd("ProgDown")
            if self._optimistic:
                self._attr_state = MediaPlayerState.PLAYING
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        """Send Program Up command."""

        try:
            await self.stb.send_cmd("ProgUp")
            if self._optimistic:
                self._attr_state = MediaPlayerState.PLAYING
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Send volume up command."""

        try:
            await self.stb.send_cmd("VolUp")
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_volume_down(self) -> None:
        """Send volume up command."""

        try:
            await self.stb.send_cmd("VolDown")
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""

        try:
            await self.stb.send_cmd("Mute")
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()
