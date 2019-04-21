"""Provide functionality to interact with Cast devices on the network."""
import asyncio
import logging
import threading
from typing import Optional, Tuple

import attr
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, MediaPlayerDevice)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MOVIE, MEDIA_TYPE_MUSIC, MEDIA_TYPE_TVSHOW, SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET)
from homeassistant.const import (
    CONF_HOST, EVENT_HOMEASSISTANT_STOP, STATE_IDLE, STATE_OFF, STATE_PAUSED,
    STATE_PLAYING)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, dispatcher_send)
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
import homeassistant.util.dt as dt_util

from . import DOMAIN as CAST_DOMAIN

DEPENDENCIES = ('cast',)

_LOGGER = logging.getLogger(__name__)

CONF_IGNORE_CEC = 'ignore_cec'
CAST_SPLASH = 'https://home-assistant.io/images/cast/splash.png'

DEFAULT_PORT = 8009

SUPPORT_CAST = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PREVIOUS_TRACK | \
    SUPPORT_NEXT_TRACK | SUPPORT_PLAY_MEDIA | SUPPORT_STOP | SUPPORT_PLAY

# Stores a threading.Lock that is held by the internal pychromecast discovery.
INTERNAL_DISCOVERY_RUNNING_KEY = 'cast_discovery_running'
# Stores all ChromecastInfo we encountered through discovery or config as a set
# If we find a chromecast with a new host, the old one will be removed again.
KNOWN_CHROMECAST_INFO_KEY = 'cast_known_chromecasts'
# Stores UUIDs of cast devices that were added as entities. Doesn't store
# None UUIDs.
ADDED_CAST_DEVICES_KEY = 'cast_added_cast_devices'

# Dispatcher signal fired with a ChromecastInfo every time we discover a new
# Chromecast or receive it through configuration
SIGNAL_CAST_DISCOVERED = 'cast_discovered'

# Dispatcher signal fired with a ChromecastInfo every time a Chromecast is
# removed
SIGNAL_CAST_REMOVED = 'cast_removed'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_IGNORE_CEC, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
})


@attr.s(slots=True, frozen=True)
class ChromecastInfo:
    """Class to hold all data about a chromecast for creating connections.

    This also has the same attributes as the mDNS fields by zeroconf.
    """

    host = attr.ib(type=str)
    port = attr.ib(type=int)
    service = attr.ib(type=Optional[str], default=None)
    uuid = attr.ib(type=Optional[str], converter=attr.converters.optional(str),
                   default=None)  # always convert UUID to string if not None
    manufacturer = attr.ib(type=str, default='')
    model_name = attr.ib(type=str, default='')
    friendly_name = attr.ib(type=Optional[str], default=None)

    @property
    def is_audio_group(self) -> bool:
        """Return if this is an audio group."""
        return self.port != DEFAULT_PORT

    @property
    def is_information_complete(self) -> bool:
        """Return if all information is filled out."""
        return all(attr.astuple(self))

    @property
    def host_port(self) -> Tuple[str, int]:
        """Return the host+port tuple."""
        return self.host, self.port


def _fill_out_missing_chromecast_info(info: ChromecastInfo) -> ChromecastInfo:
    """Fill out missing attributes of ChromecastInfo using blocking HTTP."""
    if info.is_information_complete or info.is_audio_group:
        # We have all information, no need to check HTTP API. Or this is an
        # audio group, so checking via HTTP won't give us any new information.
        return info

    # Fill out missing information via HTTP dial.
    from pychromecast import dial

    http_device_status = dial.get_device_status(
        info.host, services=[info.service],
        zconf=ChromeCastZeroconf.get_zeroconf())
    if http_device_status is None:
        # HTTP dial didn't give us any new information.
        return info

    return ChromecastInfo(
        service=info.service, host=info.host, port=info.port,
        uuid=(info.uuid or http_device_status.uuid),
        friendly_name=(info.friendly_name or http_device_status.friendly_name),
        manufacturer=(info.manufacturer or http_device_status.manufacturer),
        model_name=(info.model_name or http_device_status.model_name)
    )


def _discover_chromecast(hass: HomeAssistantType, info: ChromecastInfo):
    if info in hass.data[KNOWN_CHROMECAST_INFO_KEY]:
        _LOGGER.debug("Discovered previous chromecast %s", info)

    # Either discovered completely new chromecast or a "moved" one.
    info = _fill_out_missing_chromecast_info(info)
    _LOGGER.debug("Discovered chromecast %s", info)

    if info.uuid is not None:
        # Remove previous cast infos with same uuid from known chromecasts.
        same_uuid = set(x for x in hass.data[KNOWN_CHROMECAST_INFO_KEY]
                        if info.uuid == x.uuid)
        hass.data[KNOWN_CHROMECAST_INFO_KEY] -= same_uuid

    hass.data[KNOWN_CHROMECAST_INFO_KEY].add(info)
    dispatcher_send(hass, SIGNAL_CAST_DISCOVERED, info)


def _remove_chromecast(hass: HomeAssistantType, info: ChromecastInfo):
    # Removed chromecast
    _LOGGER.debug("Removed chromecast %s", info)

    dispatcher_send(hass, SIGNAL_CAST_REMOVED, info)


class ChromeCastZeroconf:
    """Class to hold a zeroconf instance."""

    __zconf = None

    @classmethod
    def set_zeroconf(cls, zconf):
        """Set zeroconf."""
        cls.__zconf = zconf

    @classmethod
    def get_zeroconf(cls):
        """Get zeroconf."""
        return cls.__zconf


def _setup_internal_discovery(hass: HomeAssistantType) -> None:
    """Set up the pychromecast internal discovery."""
    if INTERNAL_DISCOVERY_RUNNING_KEY not in hass.data:
        hass.data[INTERNAL_DISCOVERY_RUNNING_KEY] = threading.Lock()

    if not hass.data[INTERNAL_DISCOVERY_RUNNING_KEY].acquire(blocking=False):
        # Internal discovery is already running
        return

    import pychromecast

    def internal_add_callback(name):
        """Handle zeroconf discovery of a new chromecast."""
        mdns = listener.services[name]
        _discover_chromecast(hass, ChromecastInfo(
            service=name,
            host=mdns[0],
            port=mdns[1],
            uuid=mdns[2],
            model_name=mdns[3],
            friendly_name=mdns[4],
        ))

    def internal_remove_callback(name, mdns):
        """Handle zeroconf discovery of a removed chromecast."""
        _remove_chromecast(hass, ChromecastInfo(
            service=name,
            host=mdns[0],
            port=mdns[1],
            uuid=mdns[2],
            model_name=mdns[3],
            friendly_name=mdns[4],
        ))

    _LOGGER.debug("Starting internal pychromecast discovery.")
    listener, browser = pychromecast.start_discovery(internal_add_callback,
                                                     internal_remove_callback)
    ChromeCastZeroconf.set_zeroconf(browser.zc)

    def stop_discovery(event):
        """Stop discovery of new chromecasts."""
        _LOGGER.debug("Stopping internal pychromecast discovery.")
        pychromecast.stop_discovery(browser)
        hass.data[INTERNAL_DISCOVERY_RUNNING_KEY].release()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_discovery)


@callback
def _async_create_cast_device(hass: HomeAssistantType,
                              info: ChromecastInfo):
    """Create a CastDevice Entity from the chromecast object.

    Returns None if the cast device has already been added.
    """
    if info.uuid is None:
        # Found a cast without UUID, we don't store it because we won't be able
        # to update it anyway.
        return CastDevice(info)

    # Found a cast with UUID
    added_casts = hass.data[ADDED_CAST_DEVICES_KEY]
    if info.uuid in added_casts:
        # Already added this one, the entity will take care of moved hosts
        # itself
        return None
    # -> New cast device
    added_casts.add(info.uuid)
    return CastDevice(info)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up thet Cast platform.

    Deprecated.
    """
    _LOGGER.warning(
        'Setting configuration for Cast via platform is deprecated. '
        'Configure via Cast component instead.')
    await _async_setup_platform(
        hass, config, async_add_entities, discovery_info)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Cast from a config entry."""
    config = hass.data[CAST_DOMAIN].get('media_player', {})
    if not isinstance(config, list):
        config = [config]

    # no pending task
    done, _ = await asyncio.wait([
        _async_setup_platform(hass, cfg, async_add_entities, None)
        for cfg in config])
    if any([task.exception() for task in done]):
        exceptions = [task.exception() for task in done]
        for exception in exceptions:
            _LOGGER.debug("Failed to setup chromecast", exc_info=exception)
        raise PlatformNotReady


async def _async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                                async_add_entities, discovery_info):
    """Set up the cast platform."""
    import pychromecast

    # Import CEC IGNORE attributes
    pychromecast.IGNORE_CEC += config.get(CONF_IGNORE_CEC, [])
    hass.data.setdefault(ADDED_CAST_DEVICES_KEY, set())
    hass.data.setdefault(KNOWN_CHROMECAST_INFO_KEY, set())

    info = None
    if discovery_info is not None:
        info = ChromecastInfo(host=discovery_info['host'],
                              port=discovery_info['port'])
    elif CONF_HOST in config:
        info = ChromecastInfo(host=config[CONF_HOST],
                              port=DEFAULT_PORT)

    @callback
    def async_cast_discovered(discover: ChromecastInfo) -> None:
        """Handle discovery of a new chromecast."""
        if info is not None and info.host_port != discover.host_port:
            # Not our requested cast device.
            return

        cast_device = _async_create_cast_device(hass, discover)
        if cast_device is not None:
            async_add_entities([cast_device])

    async_dispatcher_connect(
        hass, SIGNAL_CAST_DISCOVERED, async_cast_discovered)
    # Re-play the callback for all past chromecasts, store the objects in
    # a list to avoid concurrent modification resulting in exception.
    for chromecast in list(hass.data[KNOWN_CHROMECAST_INFO_KEY]):
        async_cast_discovered(chromecast)

    if info is None or info.is_audio_group:
        # If we were a) explicitly told to enable discovery or
        # b) have an audio group cast device, we need internal discovery.
        hass.async_add_job(_setup_internal_discovery, hass)
    else:
        info = await hass.async_add_job(_fill_out_missing_chromecast_info,
                                        info)
        if info.friendly_name is None:
            _LOGGER.debug("Cannot retrieve detail information for chromecast"
                          " %s, the device may not be online", info)

        hass.async_add_job(_discover_chromecast, hass, info)


class CastStatusListener:
    """Helper class to handle pychromecast status callbacks.

    Necessary because a CastDevice entity can create a new socket client
    and therefore callbacks from multiple chromecast connections can
    potentially arrive. This class allows invalidating past chromecast objects.
    """

    def __init__(self, cast_device, chromecast):
        """Initialize the status listener."""
        self._cast_device = cast_device
        self._valid = True

        chromecast.register_status_listener(self)
        chromecast.socket_client.media_controller.register_status_listener(
            self)
        chromecast.register_connection_listener(self)

    def new_cast_status(self, cast_status):
        """Handle reception of a new CastStatus."""
        if self._valid:
            self._cast_device.new_cast_status(cast_status)

    def new_media_status(self, media_status):
        """Handle reception of a new MediaStatus."""
        if self._valid:
            self._cast_device.new_media_status(media_status)

    def new_connection_status(self, connection_status):
        """Handle reception of a new ConnectionStatus."""
        if self._valid:
            self._cast_device.new_connection_status(connection_status)

    def invalidate(self):
        """Invalidate this status listener.

        All following callbacks won't be forwarded.
        """
        self._valid = False


class CastDevice(MediaPlayerDevice):
    """Representation of a Cast device on the network.

    This class is the holder of the pychromecast.Chromecast object and its
    socket client. It therefore handles all reconnects and audio group changing
    "elected leader" itself.
    """

    def __init__(self, cast_info):
        """Initialize the cast device."""
        import pychromecast  # noqa: pylint: disable=unused-import
        self._cast_info = cast_info  # type: ChromecastInfo
        self.services = None
        if cast_info.service:
            self.services = set()
            self.services.add(cast_info.service)
        self._chromecast = None  # type: Optional[pychromecast.Chromecast]
        self.cast_status = None
        self.media_status = None
        self.media_status_received = None
        self._available = False  # type: bool
        self._status_listener = None  # type: Optional[CastStatusListener]
        self._add_remove_handler = None
        self._del_remove_handler = None

    async def async_added_to_hass(self):
        """Create chromecast object when added to hass."""
        @callback
        def async_cast_discovered(discover: ChromecastInfo):
            """Handle discovery of new Chromecast."""
            if self._cast_info.uuid is None:
                # We can't handle empty UUIDs
                return
            if self._cast_info.uuid != discover.uuid:
                # Discovered is not our device.
                return
            if self.services is None:
                _LOGGER.warning(
                    "[%s %s (%s:%s)] Received update for manually added Cast",
                    self.entity_id, self._cast_info.friendly_name,
                    self._cast_info.host, self._cast_info.port)
                return
            _LOGGER.debug("Discovered chromecast with same UUID: %s", discover)
            self.hass.async_create_task(self.async_set_cast_info(discover))

        def async_cast_removed(discover: ChromecastInfo):
            """Handle removal of Chromecast."""
            if self._cast_info.uuid is None:
                # We can't handle empty UUIDs
                return
            if self._cast_info.uuid != discover.uuid:
                # Removed is not our device.
                return
            _LOGGER.debug("Removed chromecast with same UUID: %s", discover)
            self.hass.async_create_task(self.async_del_cast_info(discover))

        async def async_stop(event):
            """Disconnect socket on Home Assistant stop."""
            await self._async_disconnect()

        self._add_remove_handler = async_dispatcher_connect(
            self.hass, SIGNAL_CAST_DISCOVERED,
            async_cast_discovered)
        self._del_remove_handler = async_dispatcher_connect(
            self.hass, SIGNAL_CAST_REMOVED,
            async_cast_removed)
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop)
        self.hass.async_create_task(self.async_set_cast_info(self._cast_info))

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect Chromecast object when removed."""
        await self._async_disconnect()
        if self._cast_info.uuid is not None:
            # Remove the entity from the added casts so that it can dynamically
            # be re-added again.
            self.hass.data[ADDED_CAST_DEVICES_KEY].remove(self._cast_info.uuid)
        if self._add_remove_handler:
            self._add_remove_handler()
        if self._del_remove_handler:
            self._del_remove_handler()

    async def async_set_cast_info(self, cast_info):
        """Set the cast information and set up the chromecast object."""
        import pychromecast
        self._cast_info = cast_info

        if self.services is not None:
            if cast_info.service not in self.services:
                _LOGGER.debug("[%s %s (%s:%s)] Got new service: %s (%s)",
                              self.entity_id, self._cast_info.friendly_name,
                              self._cast_info.host, self._cast_info.port,
                              cast_info.service, self.services)

            self.services.add(cast_info.service)

        if self._chromecast is not None:
            # Only setup the chromecast once, added elements to services
            # will automatically be picked up.
            return

        # pylint: disable=protected-access
        if self.services is None:
            _LOGGER.debug(
                "[%s %s (%s:%s)] Connecting to cast device by host %s",
                self.entity_id, self._cast_info.friendly_name,
                self._cast_info.host, self._cast_info.port, cast_info)
            chromecast = await self.hass.async_add_job(
                pychromecast._get_chromecast_from_host, (
                    cast_info.host, cast_info.port, cast_info.uuid,
                    cast_info.model_name, cast_info.friendly_name
                ))
        else:
            _LOGGER.debug(
                "[%s %s (%s:%s)] Connecting to cast device by service %s",
                self.entity_id, self._cast_info.friendly_name,
                self._cast_info.host, self._cast_info.port, self.services)
            chromecast = await self.hass.async_add_job(
                pychromecast._get_chromecast_from_service, (
                    self.services, ChromeCastZeroconf.get_zeroconf(),
                    cast_info.uuid, cast_info.model_name,
                    cast_info.friendly_name
                ))
        self._chromecast = chromecast
        self._status_listener = CastStatusListener(self, chromecast)
        self._available = False
        self.cast_status = chromecast.status
        self.media_status = chromecast.media_controller.status
        self._chromecast.start()
        self.async_schedule_update_ha_state()

    async def async_del_cast_info(self, cast_info):
        """Remove the service."""
        self.services.discard(cast_info.service)
        _LOGGER.debug("[%s %s (%s:%s)] Remove service: %s (%s)",
                      self.entity_id, self._cast_info.friendly_name,
                      self._cast_info.host, self._cast_info.port,
                      cast_info.service, self.services)

    async def _async_disconnect(self):
        """Disconnect Chromecast object if it is set."""
        if self._chromecast is None:
            # Can't disconnect if not connected.
            return
        _LOGGER.debug("[%s %s (%s:%s)] Disconnecting from chromecast socket.",
                      self.entity_id, self._cast_info.friendly_name,
                      self._cast_info.host, self._cast_info.port)
        self._available = False
        self.async_schedule_update_ha_state()

        await self.hass.async_add_job(self._chromecast.disconnect)

        self._invalidate()

        self.async_schedule_update_ha_state()

    def _invalidate(self):
        """Invalidate some attributes."""
        self._chromecast = None
        self.cast_status = None
        self.media_status = None
        self.media_status_received = None
        if self._status_listener is not None:
            self._status_listener.invalidate()
            self._status_listener = None

    # ========== Callbacks ==========
    def new_cast_status(self, cast_status):
        """Handle updates of the cast status."""
        self.cast_status = cast_status
        self.schedule_update_ha_state()

    def new_media_status(self, media_status):
        """Handle updates of the media status."""
        self.media_status = media_status
        self.media_status_received = dt_util.utcnow()
        self.schedule_update_ha_state()

    def new_connection_status(self, connection_status):
        """Handle updates of connection status."""
        from pychromecast.socket_client import CONNECTION_STATUS_CONNECTED, \
            CONNECTION_STATUS_DISCONNECTED

        _LOGGER.debug(
            "[%s %s (%s:%s)] Received cast device connection status: %s",
            self.entity_id, self._cast_info.friendly_name,
            self._cast_info.host, self._cast_info.port,
            connection_status.status)
        if connection_status.status == CONNECTION_STATUS_DISCONNECTED:
            self._available = False
            self._invalidate()
            self.schedule_update_ha_state()
            return

        new_available = connection_status.status == CONNECTION_STATUS_CONNECTED
        if new_available != self._available:
            # Connection status callbacks happen often when disconnected.
            # Only update state when availability changed to put less pressure
            # on state machine.
            _LOGGER.debug(
                "[%s %s (%s:%s)] Cast device availability changed: %s",
                self.entity_id, self._cast_info.friendly_name,
                self._cast_info.host, self._cast_info.port,
                connection_status.status)
            info = self._cast_info
            if info.friendly_name is None and not info.is_audio_group:
                # We couldn't find friendly_name when the cast was added, retry
                self._cast_info = _fill_out_missing_chromecast_info(info)
            self._available = new_available
            self.schedule_update_ha_state()

    # ========== Service Calls ==========
    def turn_on(self):
        """Turn on the cast device."""
        import pychromecast

        if not self._chromecast.is_idle:
            # Already turned on
            return

        if self._chromecast.app_id is not None:
            # Quit the previous app before starting splash screen
            self._chromecast.quit_app()

        # The only way we can turn the Chromecast is on is by launching an app
        self._chromecast.play_media(CAST_SPLASH,
                                    pychromecast.STREAM_TYPE_BUFFERED)

    def turn_off(self):
        """Turn off the cast device."""
        self._chromecast.quit_app()

    def mute_volume(self, mute):
        """Mute the volume."""
        self._chromecast.set_volume_muted(mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._chromecast.set_volume(volume)

    def media_play(self):
        """Send play command."""
        self._chromecast.media_controller.play()

    def media_pause(self):
        """Send pause command."""
        self._chromecast.media_controller.pause()

    def media_stop(self):
        """Send stop command."""
        self._chromecast.media_controller.stop()

    def media_previous_track(self):
        """Send previous track command."""
        self._chromecast.media_controller.rewind()

    def media_next_track(self):
        """Send next track command."""
        self._chromecast.media_controller.skip()

    def media_seek(self, position):
        """Seek the media to a specific location."""
        self._chromecast.media_controller.seek(position)

    def play_media(self, media_type, media_id, **kwargs):
        """Play media from a URL."""
        self._chromecast.media_controller.play_media(media_id, media_type)

    # ========== Properties ==========
    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._cast_info.friendly_name

    @property
    def device_info(self):
        """Return information about the device."""
        cast_info = self._cast_info

        if cast_info.model_name == "Google Cast Group":
            return None

        return {
            'name': cast_info.friendly_name,
            'identifiers': {
                (CAST_DOMAIN, cast_info.uuid.replace('-', ''))
            },
            'model': cast_info.model_name,
            'manufacturer': cast_info.manufacturer,
        }

    @property
    def state(self):
        """Return the state of the player."""
        if self.media_status is None:
            return None
        if self.media_status.player_is_playing:
            return STATE_PLAYING
        if self.media_status.player_is_paused:
            return STATE_PAUSED
        if self.media_status.player_is_idle:
            return STATE_IDLE
        if self._chromecast is not None and self._chromecast.is_idle:
            return STATE_OFF
        return None

    @property
    def available(self):
        """Return True if the cast device is connected."""
        return self._available

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self.cast_status.volume_level if self.cast_status else None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self.cast_status.volume_muted if self.cast_status else None

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self.media_status.content_id if self.media_status else None

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self.media_status is None:
            return None
        if self.media_status.media_is_tvshow:
            return MEDIA_TYPE_TVSHOW
        if self.media_status.media_is_movie:
            return MEDIA_TYPE_MOVIE
        if self.media_status.media_is_musictrack:
            return MEDIA_TYPE_MUSIC
        return None

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self.media_status.duration if self.media_status else None

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self.media_status is None:
            return None

        images = self.media_status.images

        return images[0].url if images and images[0].url else None

    @property
    def media_title(self):
        """Title of current playing media."""
        return self.media_status.title if self.media_status else None

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        return self.media_status.artist if self.media_status else None

    @property
    def media_album_name(self):
        """Album of current playing media (Music track only)."""
        return self.media_status.album_name if self.media_status else None

    @property
    def media_album_artist(self):
        """Album artist of current playing media (Music track only)."""
        return self.media_status.album_artist if self.media_status else None

    @property
    def media_track(self):
        """Track number of current playing media (Music track only)."""
        return self.media_status.track if self.media_status else None

    @property
    def media_series_title(self):
        """Return the title of the series of current playing media."""
        return self.media_status.series_title if self.media_status else None

    @property
    def media_season(self):
        """Season of current playing media (TV Show only)."""
        return self.media_status.season if self.media_status else None

    @property
    def media_episode(self):
        """Episode of current playing media (TV Show only)."""
        return self.media_status.episode if self.media_status else None

    @property
    def app_id(self):
        """Return the ID of the current running app."""
        return self._chromecast.app_id if self._chromecast else None

    @property
    def app_name(self):
        """Name of the current running app."""
        return self._chromecast.app_display_name if self._chromecast else None

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_CAST

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self.media_status is None or \
            not (self.media_status.player_is_playing or
                 self.media_status.player_is_paused or
                 self.media_status.player_is_idle):
            return None
        return self.media_status.current_time

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        return self.media_status_received

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._cast_info.uuid
