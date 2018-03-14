"""
Support for the Mediaroom Set-up-box.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.mediaroom/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_CHANNEL, SUPPORT_PAUSE, SUPPORT_PLAY_MEDIA,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_STOP, PLATFORM_SCHEMA,
    SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK, SUPPORT_PLAY,
    SUPPORT_VOLUME_STEP, SUPPORT_VOLUME_MUTE,
    MediaPlayerDevice)
from homeassistant.helpers.dispatcher import (dispatcher_send,
                                              async_dispatcher_connect)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_OPTIMISTIC, CONF_TIMEOUT,
    STATE_PAUSED, STATE_PLAYING, STATE_STANDBY,
    STATE_ON, STATE_OFF, STATE_UNAVAILABLE,
    EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv
REQUIREMENTS = ['pymediaroom==0.5']

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mediaroom"
NOTIFICATION_TITLE = 'Mediaroom Media Player Setup'
NOTIFICATION_ID = 'mediaroom_notification'
DEFAULT_NAME = 'Mediaroom STB'
DEFAULT_TIMEOUT = 9
DATA_MEDIAROOM = "mediaroom_known_stb"
SIGNAL_STB_NOTIFY = 'stb_discovered'

SUPPORT_MEDIAROOM = SUPPORT_PAUSE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
    SUPPORT_VOLUME_STEP | SUPPORT_VOLUME_MUTE | \
    SUPPORT_PLAY_MEDIA | SUPPORT_STOP | SUPPORT_NEXT_TRACK | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=False): cv.boolean,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
})

async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Mediaroom platform."""
    known_hosts = hass.data.get(DATA_MEDIAROOM)
    if known_hosts is None:
        known_hosts = hass.data[DATA_MEDIAROOM] = []

    host = config.get(CONF_HOST, None)
    if host:
        async_add_devices([MediaroomDevice( 
                                            host=host, 
                                            device_id=None, 
                                            optimistic=config.get(CONF_OPTIMISTIC), 
                                            timeout=config.get(CONF_TIMEOUT)
                                            )])
        hass.data[DATA_MEDIAROOM].append(host)

    _LOGGER.debug("Trying to discover Mediaroom STB")
    
    def callback_notify(notify):
        if notify.ip_address in hass.data[DATA_MEDIAROOM]:
            dispatcher_send(hass, SIGNAL_STB_NOTIFY, notify)
            return
        
        _LOGGER.debug("Discovered new stb %s", notify.ip_address)

        hass.data[DATA_MEDIAROOM].append(notify.ip_address)
        
        new_stb = MediaroomDevice(
                    host=notify.ip_address,
                    device_id=notify.device_uuid,
                    optimistic=False
                    )

        async_add_devices([new_stb])

    from pymediaroom import installMediaroomProtocol
    mr_protocol = await installMediaroomProtocol(
                            responses_callback=callback_notify)
    _LOGGER.debug("Auto discovery installed")

class MediaroomDevice(MediaPlayerDevice):
    """Representation of a Mediaroom set-up-box on the network."""

    def __init__(self, host, device_id, optimistic=False, timeout=DEFAULT_TIMEOUT):
        """Initialize the device."""
        from pymediaroom import Remote

        self.host = host
        self.stb = Remote(host)
        _LOGGER.info(
            "Found STB at %s%s", host,
            " - I'm optimistic" if optimistic else "")
        self._is_standby = not optimistic
        self._current = None
        self._optimistic = optimistic
        self._state = STATE_STANDBY
        self._name = '{}_{}'.format(DOMAIN, device_id)
        if device_id:
            self._unique_id = device_id 
        else:
            self._unique_id = self.stb.get_device_id()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    async def async_added_to_hass(self):
        """Retrieve latest state."""
        from pymediaroom import installMediaroomProtocol 
        
        def async_notify_received(notify):
            _LOGGER.debug(notify)

            if notify.ip_address != self.host:
                return

            if notify.tune:
                self._state = STATE_PLAYING 
            else:
                self._state = STATE_STANDBY
            _LOGGER.debug(
                    "STB(%s) is [%s]",
                    self.host, self._state)

        async_dispatcher_connect(self.hass, SIGNAL_STB_NOTIFY,
                                 async_notify_received)

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play media."""
        from pymediaroom import PyMediaroomError 
        
        try:
            _LOGGER.debug(
                "STB(%s) Play media: %s (%s)",
                self.stb.stb_ip, media_id, media_type)
            if media_type != MEDIA_TYPE_CHANNEL:
                _LOGGER.error('invalid media type')
                return
            if media_id.isdigit():
                media_id = int(media_id)
            else:
                return
            await self.stb.send_cmd(media_id)
            self._state = STATE_PLAYING
        except PyMediaroomError as e:
            self._state = STATE_UNAVAILABLE

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    # MediaPlayerDevice properties and methods
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

    async def async_turn_on(self):
        """Turn on the receiver."""
        from pymediaroom import PyMediaroomError 
        
        try:
            await self.stb.send_cmd('Power')
            self._state = STATE_ON
        except PyMediaroomError as e:
            self._state = STATE_UNAVAILABLE

    async def async_turn_off(self):
        """Turn off the receiver."""
        from pymediaroom import PyMediaroomError 
        
        try:
            await self.stb.send_cmd('Power')
            self._state = STATE_STANDBY
        except PyMediaroomError as e:
            self._state = STATE_UNAVAILABLE

    async def async_media_play(self):
        """Send play command."""
        from pymediaroom import PyMediaroomError 
        
        try:
            _LOGGER.debug("media_play()")
            await self.stb.send_cmd('PlayPause')
            self._state = STATE_PLAYING
        except PyMediaroomError as e:
            self._state = STATE_UNAVAILABLE

    async def async_media_pause(self):
        """Send pause command."""
        from pymediaroom import PyMediaroomError 
        
        try:
            await self.stb.send_cmd('PlayPause')
            self._state = STATE_PAUSED
        except PyMediaroomError as e:
            self._state = STATE_UNAVAILABLE

    async def async_media_stop(self):
        """Send stop command."""
        from pymediaroom import PyMediaroomError 
        
        try:
            await self.stb.send_cmd('Stop')
            self._state = STATE_PAUSED
        except PyMediaroomError as e:
            self._state = STATE_UNAVAILABLE

    async def async_media_previous_track(self):
        """Send Program Down command."""
        from pymediaroom import PyMediaroomError 
        
        try:
            await self.stb.send_cmd('ProgDown')
            self._state = STATE_PLAYING
        except PyMediaroomError as e:
            self._state = STATE_UNAVAILABLE

    async def async_media_next_track(self):
        """Send Program Up command."""
        from pymediaroom import PyMediaroomError 
        
        try:
            await self.stb.send_cmd('ProgUp')
            self._state = STATE_PLAYING
        except PyMediaroomError as e:
            self._state = STATE_UNAVAILABLE

    async def async_volume_up(self):
        """Send volume up command."""
        from pymediaroom import PyMediaroomError 
        
        try:
            await self.stb.send_cmd('VolUp')
        except PyMediaroomError as e:
            self._state = STATE_UNAVAILABLE

    async def async_volume_down(self):
        """Send volume up command."""
        from pymediaroom import PyMediaroomError 
        
        try:
            await self.stb.send_cmd('VolDown')
        except PyMediaroomError as e:
            self._state = STATE_UNAVAILABLE

    async def async_mute_volume(self, mute):
        """Send mute command."""
        from pymediaroom import PyMediaroomError 
        
        try:
            await self.stb.send_cmd('Mute')
        except PyMediaroomError as e:
            self._state = STATE_UNAVAILABLE
