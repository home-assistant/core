"""Support for the Mediaroom Set-up-box."""
import logging

from pymediaroom import PyMediaroomError, Remote, State, install_mediaroom_protocol
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerDevice
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_CHANNEL,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_TIMEOUT,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send

_LOGGER = logging.getLogger(__name__)

DATA_MEDIAROOM = "mediaroom_known_stb"
DEFAULT_NAME = "Mediaroom STB"
DEFAULT_TIMEOUT = 9
DISCOVERY_MEDIAROOM = "mediaroom_discovery_installed"

SIGNAL_STB_NOTIFY = "mediaroom_stb_discovered"
SUPPORT_MEDIAROOM = (
    SUPPORT_PAUSE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_STOP
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_PLAY
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=False): cv.boolean,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Mediaroom platform."""
    known_hosts = hass.data.get(DATA_MEDIAROOM)
    if known_hosts is None:
        known_hosts = hass.data[DATA_MEDIAROOM] = []
    host = config.get(CONF_HOST, None)
    if host:
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
        hass.data[DATA_MEDIAROOM].append(host)

    _LOGGER.debug("Trying to discover Mediaroom STB")

    def callback_notify(notify):
        """Process NOTIFY message from STB."""
        if notify.ip_address in hass.data[DATA_MEDIAROOM]:
            dispatcher_send(hass, SIGNAL_STB_NOTIFY, notify)
            return

        _LOGGER.debug("Discovered new stb %s", notify.ip_address)
        hass.data[DATA_MEDIAROOM].append(notify.ip_address)
        new_stb = MediaroomDevice(
            host=notify.ip_address, device_id=notify.device_uuid, optimistic=False
        )
        async_add_entities([new_stb])

    if not config[CONF_OPTIMISTIC]:

        already_installed = hass.data.get(DISCOVERY_MEDIAROOM, None)
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


class MediaroomDevice(MediaPlayerDevice):
    """Representation of a Mediaroom set-up-box on the network."""

    def set_state(self, mediaroom_state):
        """Map pymediaroom state to HA state."""

        state_map = {
            State.OFF: STATE_OFF,
            State.STANDBY: STATE_STANDBY,
            State.PLAYING_LIVE_TV: STATE_PLAYING,
            State.PLAYING_RECORDED_TV: STATE_PLAYING,
            State.PLAYING_TIMESHIFT_TV: STATE_PLAYING,
            State.STOPPED: STATE_PAUSED,
            State.UNKNOWN: STATE_UNAVAILABLE,
        }

        self._state = state_map[mediaroom_state]

    def __init__(self, host, device_id, optimistic=False, timeout=DEFAULT_TIMEOUT):
        """Initialize the device."""

        self.host = host
        self.stb = Remote(host)
        _LOGGER.info(
            "Found STB at %s%s", host, " - I'm optimistic" if optimistic else ""
        )
        self._channel = None
        self._optimistic = optimistic
        self._state = STATE_PLAYING if optimistic else STATE_STANDBY
        self._name = f"Mediaroom {device_id if device_id else host}"
        self._available = True
        if device_id:
            self._unique_id = device_id
        else:
            self._unique_id = None

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    async def async_added_to_hass(self):
        """Retrieve latest state."""

        async def async_notify_received(notify):
            """Process STB state from NOTIFY message."""
            stb_state = self.stb.notify_callback(notify)
            # stb_state is None in case the notify is not from the current stb
            if not stb_state:
                return
            self.set_state(stb_state)
            _LOGGER.debug("STB(%s) is [%s]", self.host, self._state)
            self._available = True
            self.async_write_ha_state()

        async_dispatcher_connect(self.hass, SIGNAL_STB_NOTIFY, async_notify_received)

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play media."""

        _LOGGER.debug(
            "STB(%s) Play media: %s (%s)", self.stb.stb_ip, media_id, media_type
        )
        if media_type != MEDIA_TYPE_CHANNEL:
            _LOGGER.error("invalid media type")
            return
        if not media_id.isdigit():
            _LOGGER.error("media_id must be a channel number")
            return

        try:
            await self.stb.send_cmd(int(media_id))
            if self._optimistic:
                self._state = STATE_PLAYING
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
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_MEDIAROOM

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        return MEDIA_TYPE_CHANNEL

    @property
    def media_channel(self):
        """Channel currently playing."""
        return self._channel

    async def async_turn_on(self):
        """Turn on the receiver."""

        try:
            self.set_state(await self.stb.turn_on())
            if self._optimistic:
                self._state = STATE_PLAYING
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_turn_off(self):
        """Turn off the receiver."""

        try:
            self.set_state(await self.stb.turn_off())
            if self._optimistic:
                self._state = STATE_STANDBY
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_media_play(self):
        """Send play command."""

        try:
            _LOGGER.debug("media_play()")
            await self.stb.send_cmd("PlayPause")
            if self._optimistic:
                self._state = STATE_PLAYING
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_media_pause(self):
        """Send pause command."""

        try:
            await self.stb.send_cmd("PlayPause")
            if self._optimistic:
                self._state = STATE_PAUSED
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_media_stop(self):
        """Send stop command."""

        try:
            await self.stb.send_cmd("Stop")
            if self._optimistic:
                self._state = STATE_PAUSED
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_media_previous_track(self):
        """Send Program Down command."""

        try:
            await self.stb.send_cmd("ProgDown")
            if self._optimistic:
                self._state = STATE_PLAYING
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_media_next_track(self):
        """Send Program Up command."""

        try:
            await self.stb.send_cmd("ProgUp")
            if self._optimistic:
                self._state = STATE_PLAYING
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_volume_up(self):
        """Send volume up command."""

        try:
            await self.stb.send_cmd("VolUp")
            self._available = True
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_volume_down(self):
        """Send volume up command."""

        try:
            await self.stb.send_cmd("VolDown")
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()

    async def async_mute_volume(self, mute):
        """Send mute command."""

        try:
            await self.stb.send_cmd("Mute")
        except PyMediaroomError:
            self._available = False
        self.async_write_ha_state()
