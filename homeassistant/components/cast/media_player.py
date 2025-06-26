"""Provide functionality to interact with Cast devices on the network."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from functools import wraps
import json
import logging
from typing import TYPE_CHECKING, Any, Concatenate

import pychromecast
from pychromecast.controllers.homeassistant import HomeAssistantController
from pychromecast.controllers.media import (
    MEDIA_PLAYER_ERROR_CODES,
    MEDIA_PLAYER_STATE_BUFFERING,
    MEDIA_PLAYER_STATE_PLAYING,
    MEDIA_PLAYER_STATE_UNKNOWN,
)
from pychromecast.controllers.multizone import MultizoneManager
from pychromecast.controllers.receiver import VOLUME_CONTROL_TYPE_FIXED
from pychromecast.error import PyChromecastError
from pychromecast.quick_play import quick_play
from pychromecast.socket_client import (
    CONNECTION_STATUS_CONNECTED,
    CONNECTION_STATUS_DISCONNECTED,
)
import yarl

from homeassistant.components import media_source, zeroconf
from homeassistant.components.media_player import (
    ATTR_MEDIA_EXTRA,
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CAST_APP_ID_HOMEASSISTANT_LOVELACE,
    CONF_UUID,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.network import NoURLAvailableError, get_url, is_hass_url
from homeassistant.util import dt as dt_util
from homeassistant.util.logging import async_create_catching_coro

from .const import (
    ADDED_CAST_DEVICES_KEY,
    CAST_MULTIZONE_MANAGER_KEY,
    CONF_IGNORE_CEC,
    DOMAIN,
    SIGNAL_CAST_DISCOVERED,
    SIGNAL_CAST_REMOVED,
    SIGNAL_HASS_CAST_SHOW_VIEW,
    HomeAssistantControllerData,
)
from .discovery import setup_internal_discovery
from .helpers import (
    CastStatusListener,
    ChromecastInfo,
    ChromeCastZeroconf,
    PlaylistError,
    PlaylistSupported,
    parse_playlist,
)

if TYPE_CHECKING:
    from . import CastProtocol

_LOGGER = logging.getLogger(__name__)

APP_IDS_UNRELIABLE_MEDIA_INFO = ("Netflix",)

CAST_SPLASH = "https://www.home-assistant.io/images/cast/splash.png"

type _FuncType[_T, **_P, _R] = Callable[Concatenate[_T, _P], _R]


def api_error[_CastDeviceT: CastDevice, **_P, _R](
    func: _FuncType[_CastDeviceT, _P, _R],
) -> _FuncType[_CastDeviceT, _P, _R]:
    """Handle PyChromecastError and reraise a HomeAssistantError."""

    @wraps(func)
    def wrapper(self: _CastDeviceT, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        """Wrap a CastDevice method."""
        try:
            return_value = func(self, *args, **kwargs)
        except PyChromecastError as err:
            raise HomeAssistantError(
                f"{self.__class__.__name__}.{func.__name__} Failed: {err}"
            ) from err

        return return_value

    return wrapper


@callback
def _async_create_cast_device(hass: HomeAssistant, info: ChromecastInfo):
    """Create a CastDevice entity or dynamic group from the chromecast object.

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

    if info.is_dynamic_group:
        # This is a dynamic group, do not add it but connect to the service.
        group = DynamicCastGroup(hass, info)
        group.async_setup()
        return None

    return CastMediaPlayerEntity(hass, info)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cast from a config entry."""
    hass.data.setdefault(ADDED_CAST_DEVICES_KEY, set())

    # Import CEC IGNORE attributes
    pychromecast.IGNORE_CEC += config_entry.data.get(CONF_IGNORE_CEC) or []

    wanted_uuids = config_entry.data.get(CONF_UUID) or None

    @callback
    def async_cast_discovered(discover: ChromecastInfo) -> None:
        """Handle discovery of a new chromecast."""
        # If wanted_uuids is set, we're only accepting specific cast devices identified
        # by UUID
        if wanted_uuids is not None and str(discover.uuid) not in wanted_uuids:
            # UUID not matching, ignore.
            return

        cast_device = _async_create_cast_device(hass, discover)
        if cast_device is not None:
            async_add_entities([cast_device])

    async_dispatcher_connect(hass, SIGNAL_CAST_DISCOVERED, async_cast_discovered)
    ChromeCastZeroconf.set_zeroconf(await zeroconf.async_get_instance(hass))
    hass.async_add_executor_job(setup_internal_discovery, hass, config_entry)


class CastDevice:
    """Representation of a Cast device or dynamic group on the network.

    This class is the holder of the pychromecast.Chromecast object and its
    socket client. It therefore handles all reconnects and audio groups changing
    "elected leader" itself.
    """

    _mz_only: bool

    def __init__(self, hass: HomeAssistant, cast_info: ChromecastInfo) -> None:
        """Initialize the cast device."""

        self.hass: HomeAssistant = hass
        self._cast_info = cast_info
        self._chromecast: pychromecast.Chromecast | None = None
        self.mz_mgr = None
        self._status_listener: CastStatusListener | None = None
        self._add_remove_handler: Callable[[], None] | None = None
        self._del_remove_handler: Callable[[], None] | None = None
        self._name: str | None = None

    def _async_setup(self, name: str) -> None:
        """Create chromecast object."""
        self._name = name
        self._add_remove_handler = async_dispatcher_connect(
            self.hass, SIGNAL_CAST_DISCOVERED, self._async_cast_discovered
        )
        self._del_remove_handler = async_dispatcher_connect(
            self.hass, SIGNAL_CAST_REMOVED, self._async_cast_removed
        )
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_stop)
        # async_create_background_task is used to avoid delaying startup wrapup if the device
        # is discovered already during startup but then fails to respond
        self.hass.async_create_background_task(
            async_create_catching_coro(self._async_connect_to_chromecast()),
            "cast-connect",
        )

    async def _async_tear_down(self) -> None:
        """Disconnect chromecast object and remove listeners."""
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

    async def _async_connect_to_chromecast(self):
        """Set up the chromecast object."""
        _LOGGER.debug(
            "[%s %s] Connecting to cast device by service %s",
            self._name,
            self._cast_info.friendly_name,
            self._cast_info.cast_info.services,
        )
        chromecast = await self.hass.async_add_executor_job(
            pychromecast.get_chromecast_from_cast_info,
            self._cast_info.cast_info,
            ChromeCastZeroconf.get_zeroconf(),
        )
        self._chromecast = chromecast

        if CAST_MULTIZONE_MANAGER_KEY not in self.hass.data:
            self.hass.data[CAST_MULTIZONE_MANAGER_KEY] = MultizoneManager()

        self.mz_mgr = self.hass.data[CAST_MULTIZONE_MANAGER_KEY]

        self._status_listener = CastStatusListener(
            self, chromecast, self.mz_mgr, self._mz_only
        )
        chromecast.start()

    async def _async_disconnect(self) -> None:
        """Disconnect Chromecast object if it is set."""
        if self._chromecast is not None:
            _LOGGER.debug(
                "[%s %s] Disconnecting from chromecast socket",
                self._name,
                self._cast_info.friendly_name,
            )
            await self.hass.async_add_executor_job(self._chromecast.disconnect)

        self._invalidate()

    def _invalidate(self) -> None:
        """Invalidate some attributes."""
        self._chromecast = None
        self.mz_mgr = None
        if self._status_listener is not None:
            self._status_listener.invalidate()
            self._status_listener = None

    @callback
    def _async_cast_discovered(self, discover: ChromecastInfo) -> None:
        """Handle discovery of new Chromecast."""
        if self._cast_info.uuid != discover.uuid:
            # Discovered is not our device.
            return

        _LOGGER.debug("Discovered chromecast with same UUID: %s", discover)
        self._cast_info = discover

    async def _async_cast_removed(self, discover: ChromecastInfo) -> None:
        """Handle removal of Chromecast."""

    async def _async_stop(self, event: Event) -> None:
        """Disconnect socket on Home Assistant stop."""
        await self._async_disconnect()

    def _get_chromecast(self) -> pychromecast.Chromecast:
        """Ensure chromecast is available, to facilitate type checking."""
        if self._chromecast is None:
            raise HomeAssistantError("Chromecast is not available.")
        return self._chromecast


class CastMediaPlayerEntity(CastDevice, MediaPlayerEntity):
    """Representation of a Cast device on the network."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_media_image_remotely_accessible = True
    _mz_only = False

    def __init__(self, hass: HomeAssistant, cast_info: ChromecastInfo) -> None:
        """Initialize the cast device."""

        CastDevice.__init__(self, hass, cast_info)

        self.cast_status = None
        self.media_status = None
        self.media_status_received = None
        self.mz_media_status: dict[str, pychromecast.controllers.media.MediaStatus] = {}
        self.mz_media_status_received: dict[str, datetime] = {}
        self._attr_available = False
        self._hass_cast_controller: HomeAssistantController | None = None

        self._cast_view_remove_handler: CALLBACK_TYPE | None = None
        self._attr_unique_id = str(cast_info.uuid)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(cast_info.uuid).replace("-", ""))},
            manufacturer=str(cast_info.cast_info.manufacturer),
            model=cast_info.cast_info.model_name,
            name=str(cast_info.friendly_name),
        )

        if cast_info.cast_info.cast_type in [
            pychromecast.const.CAST_TYPE_AUDIO,
            pychromecast.const.CAST_TYPE_GROUP,
        ]:
            self._attr_device_class = MediaPlayerDeviceClass.SPEAKER

    async def async_added_to_hass(self) -> None:
        """Create chromecast object when added to hass."""
        self._async_setup(self.entity_id)

        self._cast_view_remove_handler = async_dispatcher_connect(
            self.hass, SIGNAL_HASS_CAST_SHOW_VIEW, self._handle_signal_show_view
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect Chromecast object when removed."""
        await self._async_tear_down()

        if self._cast_view_remove_handler:
            self._cast_view_remove_handler()
            self._cast_view_remove_handler = None

    async def _async_connect_to_chromecast(self):
        """Set up the chromecast object."""
        await super()._async_connect_to_chromecast()

        self._attr_available = False
        self.cast_status = self._chromecast.status
        self.media_status = self._chromecast.media_controller.status
        self.async_write_ha_state()

    async def _async_disconnect(self):
        """Disconnect Chromecast object if it is set."""
        await super()._async_disconnect()

        self._attr_available = False
        self.async_write_ha_state()

    def _invalidate(self):
        """Invalidate some attributes."""
        super()._invalidate()

        self.cast_status = None
        self.media_status = None
        self.media_status_received = None
        self.mz_media_status = {}
        self.mz_media_status_received = {}
        self._hass_cast_controller = None

    # ========== Callbacks ==========
    def new_cast_status(self, cast_status):
        """Handle updates of the cast status."""
        self.cast_status = cast_status
        self._attr_volume_level = cast_status.volume_level if cast_status else None
        self._attr_is_volume_muted = (
            cast_status.volume_muted if self.cast_status else None
        )
        self.schedule_update_ha_state()

    def new_media_status(self, media_status):
        """Handle updates of the media status."""
        if (
            media_status
            and media_status.player_is_idle
            and media_status.idle_reason == "ERROR"
        ):
            external_url = None
            internal_url = None
            url_description = ""
            with suppress(NoURLAvailableError):  # external_url not configured
                external_url = get_url(self.hass, allow_internal=False)

            with suppress(NoURLAvailableError):  # internal_url not configured
                internal_url = get_url(self.hass, allow_external=False)

            if media_status.content_id:
                if external_url and media_status.content_id.startswith(external_url):
                    url_description = f" from external_url ({external_url})"
                if internal_url and media_status.content_id.startswith(internal_url):
                    url_description = f" from internal_url ({internal_url})"

            _LOGGER.error(
                (
                    "Failed to cast media %s%s. Please make sure the URL is: "
                    "Reachable from the cast device and either a publicly resolvable "
                    "hostname or an IP address"
                ),
                media_status.content_id,
                url_description,
            )

        self.media_status = media_status
        self.media_status_received = dt_util.utcnow()
        self.schedule_update_ha_state()

    def load_media_failed(self, queue_item_id, error_code):
        """Handle load media failed."""
        _LOGGER.debug(
            "[%s %s] Load media failed with code %s(%s) for queue_item_id %s",
            self.entity_id,
            self._cast_info.friendly_name,
            error_code,
            MEDIA_PLAYER_ERROR_CODES.get(error_code, "unknown code"),
            queue_item_id,
        )

    def new_connection_status(self, connection_status):
        """Handle updates of connection status."""
        _LOGGER.debug(
            "[%s %s] Received cast device connection status: %s",
            self.entity_id,
            self._cast_info.friendly_name,
            connection_status.status,
        )
        if connection_status.status == CONNECTION_STATUS_DISCONNECTED:
            self._attr_available = False
            self._invalidate()
            self.schedule_update_ha_state()
            return

        new_available = connection_status.status == CONNECTION_STATUS_CONNECTED
        if new_available != self.available:
            # Connection status callbacks happen often when disconnected.
            # Only update state when availability changed to put less pressure
            # on state machine.
            _LOGGER.debug(
                "[%s %s] Cast device availability changed: %s",
                self.entity_id,
                self._cast_info.friendly_name,
                connection_status.status,
            )
            self._attr_available = new_available
            if new_available and not self._cast_info.is_audio_group:
                # Poll current group status
                for group_uuid in self.mz_mgr.get_multizone_memberships(
                    self._cast_info.uuid
                ):
                    group_media_controller = self.mz_mgr.get_multizone_mediacontroller(
                        group_uuid
                    )
                    if not group_media_controller:
                        continue
                    self.multizone_new_media_status(
                        group_uuid, group_media_controller.status
                    )
            self.schedule_update_ha_state()

    def multizone_new_media_status(self, group_uuid, media_status):
        """Handle updates of audio group media status."""
        _LOGGER.debug(
            "[%s %s] Multizone %s media status: %s",
            self.entity_id,
            self._cast_info.friendly_name,
            group_uuid,
            media_status,
        )
        self.mz_media_status[group_uuid] = media_status
        self.mz_media_status_received[group_uuid] = dt_util.utcnow()
        self.schedule_update_ha_state()

    # ========== Service Calls ==========
    def _media_controller(self):
        """Return media controller.

        First try from our own cast, then groups which our cast is a member in.
        """
        media_status = self.media_status
        media_controller = self._chromecast.media_controller

        if (
            media_status is None
            or media_status.player_state == MEDIA_PLAYER_STATE_UNKNOWN
        ):
            groups = self.mz_media_status
            for k, val in groups.items():
                if val and val.player_state != MEDIA_PLAYER_STATE_UNKNOWN:
                    media_controller = self.mz_mgr.get_multizone_mediacontroller(k)
                    break

        return media_controller

    @api_error
    def _quick_play(self, app_name: str, data: dict[str, Any]) -> None:
        """Launch the app `app_name` and start playing media defined by `data`."""
        quick_play(self._get_chromecast(), app_name, data)

    @api_error
    def _quit_app(self) -> None:
        """Quit the currently running app."""
        self._get_chromecast().quit_app()

    @api_error
    def _start_app(self, app_id: str) -> None:
        """Start an app."""
        self._get_chromecast().start_app(app_id)

    def turn_on(self) -> None:
        """Turn on the cast device."""

        chromecast = self._get_chromecast()
        if not chromecast.is_idle:
            # Already turned on
            return

        if chromecast.app_id is not None:
            # Quit the previous app before starting splash screen or media player
            self._quit_app()

        # The only way we can turn the Chromecast is on is by launching an app
        if chromecast.cast_type == pychromecast.const.CAST_TYPE_CHROMECAST:
            app_data = {"media_id": CAST_SPLASH, "media_type": "image/png"}
            self._quick_play("default_media_receiver", app_data)
        else:
            self._start_app(pychromecast.config.APP_MEDIA_RECEIVER)

    @api_error
    def turn_off(self) -> None:
        """Turn off the cast device."""
        self._get_chromecast().quit_app()

    @api_error
    def mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        self._get_chromecast().set_volume_muted(mute)

    @api_error
    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._get_chromecast().set_volume(volume)

    @api_error
    def media_play(self) -> None:
        """Send play command."""
        media_controller = self._media_controller()
        media_controller.play()

    @api_error
    def media_pause(self) -> None:
        """Send pause command."""
        media_controller = self._media_controller()
        media_controller.pause()

    @api_error
    def media_stop(self) -> None:
        """Send stop command."""
        media_controller = self._media_controller()
        media_controller.stop()

    @api_error
    def media_previous_track(self) -> None:
        """Send previous track command."""
        media_controller = self._media_controller()
        media_controller.queue_prev()

    @api_error
    def media_next_track(self) -> None:
        """Send next track command."""
        media_controller = self._media_controller()
        media_controller.queue_next()

    @api_error
    def media_seek(self, position: float) -> None:
        """Seek the media to a specific location."""
        media_controller = self._media_controller()
        media_controller.seek(position)

    async def _async_root_payload(self, content_filter):
        """Generate root node."""
        children = []
        # Add media browsers
        for platform in self.hass.data[DOMAIN]["cast_platform"].values():
            children.extend(
                await platform.async_get_media_browser_root_object(
                    self.hass, self._chromecast.cast_type
                )
            )

        # Add media sources
        try:
            result = await media_source.async_browse_media(
                self.hass, None, content_filter=content_filter
            )
            children.extend(result.children)
        except BrowseError:
            if not children:
                raise

        # If there's only one media source, resolve it
        if len(children) == 1 and children[0].can_expand:
            return await self.async_browse_media(
                children[0].media_content_type,
                children[0].media_content_id,
            )

        return BrowseMedia(
            title="Cast",
            media_class=MediaClass.DIRECTORY,
            media_content_id="",
            media_content_type="",
            can_play=False,
            can_expand=True,
            children=sorted(children, key=lambda c: c.title),
        )

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        content_filter = None

        chromecast = self._get_chromecast()
        if chromecast.cast_type in (
            pychromecast.const.CAST_TYPE_AUDIO,
            pychromecast.const.CAST_TYPE_GROUP,
        ):

            def audio_content_filter(item):
                """Filter non audio content."""
                return item.media_content_type.startswith("audio/")

            content_filter = audio_content_filter

        if media_content_id is None:
            return await self._async_root_payload(content_filter)

        platform: CastProtocol
        assert media_content_type is not None
        for platform in self.hass.data[DOMAIN]["cast_platform"].values():
            browse_media = await platform.async_browse_media(
                self.hass,
                media_content_type,
                media_content_id,
                chromecast.cast_type,
            )
            if browse_media:
                return browse_media

        return await media_source.async_browse_media(
            self.hass, media_content_id, content_filter=content_filter
        )

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        chromecast = self._get_chromecast()
        # Handle media_source
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_type = sourced_media.mime_type
            media_id = sourced_media.url

        extra = kwargs.get(ATTR_MEDIA_EXTRA, {})

        # Handle media supported by a known cast app
        if media_type == DOMAIN:
            try:
                app_data = json.loads(media_id)
                if metadata := extra.get("metadata"):
                    app_data["metadata"] = metadata
            except json.JSONDecodeError:
                _LOGGER.error("Invalid JSON in media_content_id")
                raise

            # Special handling for passed `app_id` parameter. This will only launch
            # an arbitrary cast app, generally for UX.
            if "app_id" in app_data:
                app_id = app_data.pop("app_id")
                _LOGGER.debug("Starting Cast app by ID %s", app_id)
                await self.hass.async_add_executor_job(self._start_app, app_id)
                if app_data:
                    _LOGGER.warning(
                        "Extra keys %s were ignored. Please use app_name to cast media",
                        app_data.keys(),
                    )
                return

            app_name = app_data.pop("app_name")
            try:
                await self.hass.async_add_executor_job(
                    self._quick_play, app_name, app_data
                )
            except NotImplementedError:
                _LOGGER.error("App %s not supported", app_name)
            return

        # Try the cast platforms
        for platform in self.hass.data[DOMAIN]["cast_platform"].values():
            result = await platform.async_play_media(
                self.hass, self.entity_id, chromecast, media_type, media_id
            )
            if result:
                return

        # If media ID is a relative URL, we serve it from HA.
        media_id = async_process_play_media_url(self.hass, media_id)

        # Configure play command for when playing a HLS stream
        if is_hass_url(self.hass, media_id):
            parsed = yarl.URL(media_id)
            if parsed.path.startswith("/api/hls/"):
                extra = {
                    **extra,
                    "stream_type": "LIVE",
                    "media_info": {
                        "hlsVideoSegmentFormat": "fmp4",
                    },
                }
        elif media_id.endswith((".m3u", ".m3u8", ".pls")):
            try:
                playlist = await parse_playlist(self.hass, media_id)
                _LOGGER.debug(
                    "[%s %s] Playing item %s from playlist %s",
                    self.entity_id,
                    self._cast_info.friendly_name,
                    playlist[0].url,
                    media_id,
                )
                media_id = playlist[0].url
                if title := playlist[0].title:
                    extra = {
                        **extra,
                        "metadata": {"title": title},
                    }
            except PlaylistSupported as err:
                _LOGGER.debug(
                    "[%s %s] Playlist %s is supported: %s",
                    self.entity_id,
                    self._cast_info.friendly_name,
                    media_id,
                    err,
                )
            except PlaylistError as err:
                _LOGGER.warning(
                    "[%s %s] Failed to parse playlist %s: %s",
                    self.entity_id,
                    self._cast_info.friendly_name,
                    media_id,
                    err,
                )

        # Default to play with the default media receiver
        app_data = {"media_id": media_id, "media_type": media_type, **extra}
        _LOGGER.debug(
            "[%s %s] Playing %s with default_media_receiver",
            self.entity_id,
            self._cast_info.friendly_name,
            app_data,
        )
        await self.hass.async_add_executor_job(
            self._quick_play, "default_media_receiver", app_data
        )

    def _media_status(self):
        """Return media status.

        First try from our own cast, then groups which our cast is a member in.
        """
        media_status = self.media_status
        media_status_received = self.media_status_received

        if (
            media_status is None
            or media_status.player_state == MEDIA_PLAYER_STATE_UNKNOWN
        ):
            groups = self.mz_media_status
            for k, val in groups.items():
                if val and val.player_state != MEDIA_PLAYER_STATE_UNKNOWN:
                    media_status = val
                    media_status_received = self.mz_media_status_received[k]
                    break

        return (media_status, media_status_received)

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the player."""
        # The lovelace app loops media to prevent timing out, don't show that
        if self.app_id == CAST_APP_ID_HOMEASSISTANT_LOVELACE:
            return MediaPlayerState.PLAYING
        if (media_status := self._media_status()[0]) is not None:
            if media_status.player_state == MEDIA_PLAYER_STATE_PLAYING:
                return MediaPlayerState.PLAYING
            if media_status.player_state == MEDIA_PLAYER_STATE_BUFFERING:
                return MediaPlayerState.BUFFERING
            if media_status.player_is_paused:
                return MediaPlayerState.PAUSED
            if media_status.player_is_idle:
                return MediaPlayerState.IDLE
        if self.app_id is not None and self.app_id != pychromecast.IDLE_APP_ID:
            if self.app_id in APP_IDS_UNRELIABLE_MEDIA_INFO:
                # Some apps don't report media status, show the player as playing
                return MediaPlayerState.PLAYING
            return MediaPlayerState.IDLE
        if self._chromecast is not None and self._chromecast.is_idle:
            return MediaPlayerState.OFF
        return None

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        # The lovelace app loops media to prevent timing out, don't show that
        if self.app_id == CAST_APP_ID_HOMEASSISTANT_LOVELACE:
            return None
        media_status = self._media_status()[0]
        return media_status.content_id if media_status else None

    @property
    def media_content_type(self) -> MediaType | None:
        """Content type of current playing media."""
        # The lovelace app loops media to prevent timing out, don't show that
        if self.app_id == CAST_APP_ID_HOMEASSISTANT_LOVELACE:
            return None
        if (media_status := self._media_status()[0]) is None:
            return None
        if media_status.media_is_tvshow:
            return MediaType.TVSHOW
        if media_status.media_is_movie:
            return MediaType.MOVIE
        if media_status.media_is_musictrack:
            return MediaType.MUSIC

        chromecast = self._get_chromecast()
        if chromecast.cast_type in (
            pychromecast.const.CAST_TYPE_AUDIO,
            pychromecast.const.CAST_TYPE_GROUP,
        ):
            return MediaType.MUSIC

        return MediaType.VIDEO

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        # The lovelace app loops media to prevent timing out, don't show that
        if self.app_id == CAST_APP_ID_HOMEASSISTANT_LOVELACE:
            return None
        media_status = self._media_status()[0]
        return media_status.duration if media_status else None

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if (media_status := self._media_status()[0]) is None:
            return None

        images = media_status.images

        return images[0].url if images and images[0].url else None

    @property
    def media_title(self):
        """Title of current playing media."""
        media_status = self._media_status()[0]
        return media_status.title if media_status else None

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        media_status = self._media_status()[0]
        return media_status.artist if media_status else None

    @property
    def media_album_name(self):
        """Album of current playing media (Music track only)."""
        media_status = self._media_status()[0]
        return media_status.album_name if media_status else None

    @property
    def media_album_artist(self):
        """Album artist of current playing media (Music track only)."""
        media_status = self._media_status()[0]
        return media_status.album_artist if media_status else None

    @property
    def media_track(self):
        """Track number of current playing media (Music track only)."""
        media_status = self._media_status()[0]
        return media_status.track if media_status else None

    @property
    def media_series_title(self):
        """Return the title of the series of current playing media."""
        media_status = self._media_status()[0]
        return media_status.series_title if media_status else None

    @property
    def media_season(self):
        """Season of current playing media (TV Show only)."""
        media_status = self._media_status()[0]
        return media_status.season if media_status else None

    @property
    def media_episode(self):
        """Episode of current playing media (TV Show only)."""
        media_status = self._media_status()[0]
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
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        support = (
            MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.TURN_ON
        )
        media_status = self._media_status()[0]

        if (
            self.cast_status
            and self.cast_status.volume_control_type != VOLUME_CONTROL_TYPE_FIXED
        ):
            support |= (
                MediaPlayerEntityFeature.VOLUME_MUTE
                | MediaPlayerEntityFeature.VOLUME_SET
            )

        if media_status and self.app_id != CAST_APP_ID_HOMEASSISTANT_LOVELACE:
            support |= (
                MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.STOP
            )
            if media_status.supports_queue_next:
                support |= (
                    MediaPlayerEntityFeature.PREVIOUS_TRACK
                    | MediaPlayerEntityFeature.NEXT_TRACK
                )
            if media_status.supports_seek:
                support |= MediaPlayerEntityFeature.SEEK

        if "media_source" in self.hass.config.components:
            support |= MediaPlayerEntityFeature.BROWSE_MEDIA

        return support

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        # The lovelace app loops media to prevent timing out, don't show that
        if self.app_id == CAST_APP_ID_HOMEASSISTANT_LOVELACE:
            return None
        media_status = self._media_status()[0]
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
        if self.app_id == CAST_APP_ID_HOMEASSISTANT_LOVELACE:
            return None
        return self._media_status()[1]

    def _handle_signal_show_view(
        self,
        controller_data: HomeAssistantControllerData,
        entity_id: str,
        view_path: str,
        url_path: str | None,
    ):
        """Handle a show view signal."""
        if entity_id != self.entity_id or self._chromecast is None:
            return

        if self._hass_cast_controller is None:

            def unregister() -> None:
                """Handle request to unregister the handler."""
                if not self._hass_cast_controller or not self._chromecast:
                    return
                _LOGGER.debug(
                    "[%s %s] Unregistering HomeAssistantController",
                    self.entity_id,
                    self._cast_info.friendly_name,
                )

                self._chromecast.unregister_handler(self._hass_cast_controller)
                self._hass_cast_controller = None

            controller = HomeAssistantController(
                **controller_data, unregister=unregister
            )
            self._hass_cast_controller = controller
            self._chromecast.register_handler(controller)

        self._hass_cast_controller.show_lovelace_view(view_path, url_path)


class DynamicCastGroup(CastDevice):
    """Representation of a Cast device on the network - for dynamic cast groups."""

    _mz_only = True

    def async_setup(self):
        """Create chromecast object."""
        self._async_setup("Dynamic group")

    async def _async_cast_removed(self, discover: ChromecastInfo):
        """Handle removal of Chromecast."""
        if self._cast_info.uuid != discover.uuid:
            # Removed is not our device.
            return

        if not discover.cast_info.services:
            # Clean up the dynamic group
            _LOGGER.debug("Clean up dynamic group: %s", discover)
            await self._async_tear_down()
