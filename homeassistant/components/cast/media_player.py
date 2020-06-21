"""Provide functionality to interact with Cast devices on the network."""
import asyncio
import json
import logging
from typing import Optional

import pychromecast
from pychromecast.controllers.homeassistant import HomeAssistantController
from pychromecast.controllers.multizone import MultizoneManager
from pychromecast.quick_play import quick_play
from pychromecast.socket_client import (
    CONNECTION_STATUS_CONNECTED,
    CONNECTION_STATUS_DISCONNECTED,
)
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_TVSHOW,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.const import (
    CONF_HOST,
    EVENT_HOMEASSISTANT_STOP,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
import homeassistant.util.dt as dt_util
from homeassistant.util.logging import async_create_catching_coro

from .const import (
    ADDED_CAST_DEVICES_KEY,
    CAST_MULTIZONE_MANAGER_KEY,
    DEFAULT_PORT,
    DOMAIN as CAST_DOMAIN,
    KNOWN_CHROMECAST_INFO_KEY,
    SIGNAL_CAST_DISCOVERED,
    SIGNAL_CAST_REMOVED,
    SIGNAL_HASS_CAST_SHOW_VIEW,
)
from .discovery import setup_internal_discovery
from .helpers import CastStatusListener, ChromecastInfo, ChromeCastZeroconf

_LOGGER = logging.getLogger(__name__)

CONF_IGNORE_CEC = "ignore_cec"
CAST_SPLASH = "https://www.home-assistant.io/images/cast/splash.png"

SUPPORT_CAST = (
    SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_STOP
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_IGNORE_CEC, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)


@callback
def _async_create_cast_device(hass: HomeAssistantType, info: ChromecastInfo):
    """Create a CastDevice Entity from the chromecast object.

    Returns None if the cast device has already been added.
    """
    _LOGGER.debug("_async_create_cast_device: %s", info)
    if info.uuid is None:
        _LOGGER.error("_async_create_cast_device uuid none: %s", info)
        return None

    # Found a cast with UUID
    added_casts = hass.data[ADDED_CAST_DEVICES_KEY]
    if info.uuid in added_casts:
        # Already added this one, the entity will take care of moved hosts
        # itself
        return None
    # -> New cast device
    added_casts.add(info.uuid)
    return CastDevice(info)


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up thet Cast platform.

    Deprecated.
    """
    _LOGGER.warning(
        "Setting configuration for Cast via platform is deprecated. "
        "Configure via Cast integration instead."
    )
    await _async_setup_platform(hass, config, async_add_entities, discovery_info)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Cast from a config entry."""
    config = hass.data[CAST_DOMAIN].get("media_player", {})
    if not isinstance(config, list):
        config = [config]

    # no pending task
    done, _ = await asyncio.wait(
        [_async_setup_platform(hass, cfg, async_add_entities, None) for cfg in config]
    )
    if any([task.exception() for task in done]):
        exceptions = [task.exception() for task in done]
        for exception in exceptions:
            _LOGGER.debug("Failed to setup chromecast", exc_info=exception)
        raise PlatformNotReady


async def _async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info
):
    """Set up the cast platform."""
    # Import CEC IGNORE attributes
    pychromecast.IGNORE_CEC += config.get(CONF_IGNORE_CEC, [])
    hass.data.setdefault(ADDED_CAST_DEVICES_KEY, set())
    hass.data.setdefault(KNOWN_CHROMECAST_INFO_KEY, set())

    info = None
    if discovery_info is not None:
        info = ChromecastInfo(host=discovery_info["host"], port=discovery_info["port"])
    elif CONF_HOST in config:
        info = ChromecastInfo(host=config[CONF_HOST], port=DEFAULT_PORT)

    @callback
    def async_cast_discovered(discover: ChromecastInfo) -> None:
        """Handle discovery of a new chromecast."""
        if info is not None and info.host_port != discover.host_port:
            # Waiting for a specific cast device, this is not it.
            return

        cast_device = _async_create_cast_device(hass, discover)
        if cast_device is not None:
            async_add_entities([cast_device])

    async_dispatcher_connect(hass, SIGNAL_CAST_DISCOVERED, async_cast_discovered)
    # Re-play the callback for all past chromecasts, store the objects in
    # a list to avoid concurrent modification resulting in exception.
    for chromecast in list(hass.data[KNOWN_CHROMECAST_INFO_KEY]):
        async_cast_discovered(chromecast)

    ChromeCastZeroconf.set_zeroconf(await zeroconf.async_get_instance(hass))
    hass.async_add_executor_job(setup_internal_discovery, hass)


class CastDevice(MediaPlayerEntity):
    """Representation of a Cast device on the network.

    This class is the holder of the pychromecast.Chromecast object and its
    socket client. It therefore handles all reconnects and audio group changing
    "elected leader" itself.
    """

    def __init__(self, cast_info: ChromecastInfo):
        """Initialize the cast device."""

        self._cast_info = cast_info
        self.services = None
        if cast_info.service:
            self.services = set()
            self.services.add(cast_info.service)
        self._chromecast: Optional[pychromecast.Chromecast] = None
        self.cast_status = None
        self.media_status = None
        self.media_status_received = None
        self.mz_media_status = {}
        self.mz_media_status_received = {}
        self.mz_mgr = None
        self._available = False
        self._status_listener: Optional[CastStatusListener] = None
        self._hass_cast_controller: Optional[HomeAssistantController] = None

        self._add_remove_handler = None
        self._del_remove_handler = None
        self._cast_view_remove_handler = None

    async def async_added_to_hass(self):
        """Create chromecast object when added to hass."""
        self._add_remove_handler = async_dispatcher_connect(
            self.hass, SIGNAL_CAST_DISCOVERED, self._async_cast_discovered
        )
        self._del_remove_handler = async_dispatcher_connect(
            self.hass, SIGNAL_CAST_REMOVED, self._async_cast_removed
        )
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_stop)
        self.hass.async_create_task(
            async_create_catching_coro(self.async_set_cast_info(self._cast_info))
        )

        self._cast_view_remove_handler = async_dispatcher_connect(
            self.hass, SIGNAL_HASS_CAST_SHOW_VIEW, self._handle_signal_show_view
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect Chromecast object when removed."""
        await self._async_disconnect()
        if self._cast_info.uuid is not None:
            # Remove the entity from the added casts so that it can dynamically
            # be re-added again.
            self.hass.data[ADDED_CAST_DEVICES_KEY].remove(self._cast_info.uuid)
        if self._add_remove_handler:
            self._add_remove_handler()
            self._add_remove_handler = None
        if self._del_remove_handler:
            self._del_remove_handler()
            self._del_remove_handler = None
        if self._cast_view_remove_handler:
            self._cast_view_remove_handler()
            self._cast_view_remove_handler = None

    async def async_set_cast_info(self, cast_info):
        """Set the cast information and set up the chromecast object."""

        self._cast_info = cast_info

        if self.services is not None:
            if cast_info.service not in self.services:
                _LOGGER.debug(
                    "[%s %s (%s:%s)] Got new service: %s (%s)",
                    self.entity_id,
                    self._cast_info.friendly_name,
                    self._cast_info.host,
                    self._cast_info.port,
                    cast_info.service,
                    self.services,
                )

            self.services.add(cast_info.service)

        if self._chromecast is not None:
            # Only setup the chromecast once, added elements to services
            # will automatically be picked up.
            return

        _LOGGER.debug(
            "[%s %s (%s:%s)] Connecting to cast device by service %s",
            self.entity_id,
            self._cast_info.friendly_name,
            self._cast_info.host,
            self._cast_info.port,
            self.services,
        )
        chromecast = await self.hass.async_add_executor_job(
            pychromecast.get_chromecast_from_service,
            (
                self.services,
                ChromeCastZeroconf.get_zeroconf(),
                cast_info.uuid,
                cast_info.model_name,
                cast_info.friendly_name,
            ),
        )
        self._chromecast = chromecast

        if CAST_MULTIZONE_MANAGER_KEY not in self.hass.data:
            self.hass.data[CAST_MULTIZONE_MANAGER_KEY] = MultizoneManager()

        self.mz_mgr = self.hass.data[CAST_MULTIZONE_MANAGER_KEY]

        self._status_listener = CastStatusListener(self, chromecast, self.mz_mgr)
        self._available = False
        self.cast_status = chromecast.status
        self.media_status = chromecast.media_controller.status
        self._chromecast.start()
        self.async_write_ha_state()

    async def async_del_cast_info(self, cast_info):
        """Remove the service."""
        self.services.discard(cast_info.service)
        _LOGGER.debug(
            "[%s %s (%s:%s)] Remove service: %s (%s)",
            self.entity_id,
            self._cast_info.friendly_name,
            self._cast_info.host,
            self._cast_info.port,
            cast_info.service,
            self.services,
        )

    async def _async_disconnect(self):
        """Disconnect Chromecast object if it is set."""
        if self._chromecast is None:
            # Can't disconnect if not connected.
            return
        _LOGGER.debug(
            "[%s %s (%s:%s)] Disconnecting from chromecast socket.",
            self.entity_id,
            self._cast_info.friendly_name,
            self._cast_info.host,
            self._cast_info.port,
        )
        self._available = False
        self.async_write_ha_state()

        await self.hass.async_add_executor_job(self._chromecast.disconnect)

        self._invalidate()

        self.async_write_ha_state()

    def _invalidate(self):
        """Invalidate some attributes."""
        self._chromecast = None
        self.cast_status = None
        self.media_status = None
        self.media_status_received = None
        self.mz_media_status = {}
        self.mz_media_status_received = {}
        self.mz_mgr = None
        self._hass_cast_controller = None
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
        _LOGGER.debug(
            "[%s %s (%s:%s)] Received cast device connection status: %s",
            self.entity_id,
            self._cast_info.friendly_name,
            self._cast_info.host,
            self._cast_info.port,
            connection_status.status,
        )
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
                self.entity_id,
                self._cast_info.friendly_name,
                self._cast_info.host,
                self._cast_info.port,
                connection_status.status,
            )
            self._available = new_available
            self.schedule_update_ha_state()

    def multizone_new_media_status(self, group_uuid, media_status):
        """Handle updates of audio group media status."""
        _LOGGER.debug(
            "[%s %s (%s:%s)] Multizone %s media status: %s",
            self.entity_id,
            self._cast_info.friendly_name,
            self._cast_info.host,
            self._cast_info.port,
            group_uuid,
            media_status,
        )
        self.mz_media_status[group_uuid] = media_status
        self.mz_media_status_received[group_uuid] = dt_util.utcnow()
        self.schedule_update_ha_state()

    # ========== Service Calls ==========
    def _media_controller(self):
        """
        Return media status.

        First try from our own cast, then groups which our cast is a member in.
        """
        media_status = self.media_status
        media_controller = self._chromecast.media_controller

        if media_status is None or media_status.player_state == "UNKNOWN":
            groups = self.mz_media_status
            for k, val in groups.items():
                if val and val.player_state != "UNKNOWN":
                    media_controller = self.mz_mgr.get_multizone_mediacontroller(k)
                    break

        return media_controller

    def turn_on(self):
        """Turn on the cast device."""

        if not self._chromecast.is_idle:
            # Already turned on
            return

        if self._chromecast.app_id is not None:
            # Quit the previous app before starting splash screen
            self._chromecast.quit_app()

        # The only way we can turn the Chromecast is on is by launching an app
        self._chromecast.play_media(CAST_SPLASH, pychromecast.STREAM_TYPE_BUFFERED)

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
        media_controller = self._media_controller()
        media_controller.play()

    def media_pause(self):
        """Send pause command."""
        media_controller = self._media_controller()
        media_controller.pause()

    def media_stop(self):
        """Send stop command."""
        media_controller = self._media_controller()
        media_controller.stop()

    def media_previous_track(self):
        """Send previous track command."""
        media_controller = self._media_controller()
        media_controller.queue_prev()

    def media_next_track(self):
        """Send next track command."""
        media_controller = self._media_controller()
        media_controller.queue_next()

    def media_seek(self, position):
        """Seek the media to a specific location."""
        media_controller = self._media_controller()
        media_controller.seek(position)

    def play_media(self, media_type, media_id, **kwargs):
        """Play media from a URL."""
        # We do not want this to be forwarded to a group
        if media_type == CAST_DOMAIN:
            try:
                app_data = json.loads(media_id)
            except json.JSONDecodeError:
                _LOGGER.error("Invalid JSON in media_content_id")
                raise

            # Special handling for passed `app_id` parameter. This will only launch
            # an arbitrary cast app, generally for UX.
            if "app_id" in app_data:
                app_id = app_data.pop("app_id")
                _LOGGER.info("Starting Cast app by ID %s", app_id)
                self._chromecast.start_app(app_id)
                if app_data:
                    _LOGGER.warning(
                        "Extra keys %s were ignored. Please use app_name to cast media.",
                        app_data.keys(),
                    )
                return

            app_name = app_data.pop("app_name")
            try:
                quick_play(self._chromecast, app_name, app_data)
            except NotImplementedError:
                _LOGGER.error("App %s not supported", app_name)
        else:
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
            "name": cast_info.friendly_name,
            "identifiers": {(CAST_DOMAIN, cast_info.uuid.replace("-", ""))},
            "model": cast_info.model_name,
            "manufacturer": cast_info.manufacturer,
        }

    def _media_status(self):
        """
        Return media status.

        First try from our own cast, then groups which our cast is a member in.
        """
        media_status = self.media_status
        media_status_received = self.media_status_received

        if media_status is None or media_status.player_state == "UNKNOWN":
            groups = self.mz_media_status
            for k, val in groups.items():
                if val and val.player_state != "UNKNOWN":
                    media_status = val
                    media_status_received = self.mz_media_status_received[k]
                    break

        return (media_status, media_status_received)

    @property
    def state(self):
        """Return the state of the player."""
        media_status, _ = self._media_status()

        if media_status is None:
            return None
        if media_status.player_is_playing:
            return STATE_PLAYING
        if media_status.player_is_paused:
            return STATE_PAUSED
        if media_status.player_is_idle:
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
        media_status, _ = self._media_status()
        return media_status.content_id if media_status else None

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        media_status, _ = self._media_status()
        if media_status is None:
            return None
        if media_status.media_is_tvshow:
            return MEDIA_TYPE_TVSHOW
        if media_status.media_is_movie:
            return MEDIA_TYPE_MOVIE
        if media_status.media_is_musictrack:
            return MEDIA_TYPE_MUSIC
        return None

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        media_status, _ = self._media_status()
        return media_status.duration if media_status else None

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        media_status, _ = self._media_status()
        if media_status is None:
            return None

        images = media_status.images

        return images[0].url if images and images[0].url else None

    @property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        return True

    @property
    def media_title(self):
        """Title of current playing media."""
        media_status, _ = self._media_status()
        return media_status.title if media_status else None

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        media_status, _ = self._media_status()
        return media_status.artist if media_status else None

    @property
    def media_album_name(self):
        """Album of current playing media (Music track only)."""
        media_status, _ = self._media_status()
        return media_status.album_name if media_status else None

    @property
    def media_album_artist(self):
        """Album artist of current playing media (Music track only)."""
        media_status, _ = self._media_status()
        return media_status.album_artist if media_status else None

    @property
    def media_track(self):
        """Track number of current playing media (Music track only)."""
        media_status, _ = self._media_status()
        return media_status.track if media_status else None

    @property
    def media_series_title(self):
        """Return the title of the series of current playing media."""
        media_status, _ = self._media_status()
        return media_status.series_title if media_status else None

    @property
    def media_season(self):
        """Season of current playing media (TV Show only)."""
        media_status, _ = self._media_status()
        return media_status.season if media_status else None

    @property
    def media_episode(self):
        """Episode of current playing media (TV Show only)."""
        media_status, _ = self._media_status()
        return media_status.episode if media_status else None

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
        support = SUPPORT_CAST
        media_status, _ = self._media_status()

        if media_status:
            if media_status.supports_queue_next:
                support |= SUPPORT_PREVIOUS_TRACK
            if media_status.supports_queue_next:
                support |= SUPPORT_NEXT_TRACK
            if media_status.supports_seek:
                support |= SUPPORT_SEEK

        return support

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        media_status, _ = self._media_status()
        if media_status is None or not (
            media_status.player_is_playing
            or media_status.player_is_paused
            or media_status.player_is_idle
        ):
            return None
        return media_status.current_time

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        _, media_status_recevied = self._media_status()
        return media_status_recevied

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._cast_info.uuid

    async def _async_cast_discovered(self, discover: ChromecastInfo):
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
                self.entity_id,
                self._cast_info.friendly_name,
                self._cast_info.host,
                self._cast_info.port,
            )
            return

        _LOGGER.debug("Discovered chromecast with same UUID: %s", discover)
        await self.async_set_cast_info(discover)

    async def _async_cast_removed(self, discover: ChromecastInfo):
        """Handle removal of Chromecast."""
        if self._cast_info.uuid is None:
            # We can't handle empty UUIDs
            return

        if self._cast_info.uuid != discover.uuid:
            # Removed is not our device.
            return

        _LOGGER.debug("Removed chromecast with same UUID: %s", discover)
        await self.async_del_cast_info(discover)

    async def _async_stop(self, event):
        """Disconnect socket on Home Assistant stop."""
        await self._async_disconnect()

    def _handle_signal_show_view(
        self,
        controller: HomeAssistantController,
        entity_id: str,
        view_path: str,
        url_path: Optional[str],
    ):
        """Handle a show view signal."""
        if entity_id != self.entity_id:
            return

        if self._hass_cast_controller is None:
            self._hass_cast_controller = controller
            self._chromecast.register_handler(controller)

        self._hass_cast_controller.show_lovelace_view(view_path, url_path)
