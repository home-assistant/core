"""Base class for protect data.

This module provides centralized data management for UniFi Protect, including:
- RTSPS stream URL caching via the public API (get_rtsps_streams)
- WebSocket event handling and device updates
- Automatic stream cache refresh on WebSocket reconnect or IP changes
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Generator, Iterable
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, cast

from uiprotect import ProtectApiClient
from uiprotect.api import RTSPSStreams
from uiprotect.data import (
    NVR,
    Camera,
    Event,
    EventType,
    ModelType,
    ProtectAdoptableDeviceModel,
    WSSubscriptionMessage,
)
from uiprotect.exceptions import ClientError, NotAuthorized, NvrError
from uiprotect.utils import log_event
from uiprotect.websocket import WebsocketState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    AUTH_RETRIES,
    CONF_DISABLE_RTSP,
    CONF_MAX_MEDIA,
    DEFAULT_MAX_MEDIA,
    DEVICES_THAT_ADOPT,
    DISPATCH_ADD,
    DISPATCH_ADOPT,
    DISPATCH_CHANNELS,
    DISPATCH_STREAMS,
    DOMAIN,
)
from .utils import async_get_devices_by_type

_LOGGER = logging.getLogger(__name__)
type ProtectDeviceType = ProtectAdoptableDeviceModel | NVR
type UFPConfigEntry = ConfigEntry[ProtectData]


@callback
def async_last_update_was_successful(
    hass: HomeAssistant, entry: UFPConfigEntry
) -> bool:
    """Check if the last update was successful for a config entry."""
    return hasattr(entry, "runtime_data") and entry.runtime_data.last_update_success


@callback
def _async_dispatch_id(entry: UFPConfigEntry, dispatch: str) -> str:
    """Generate entry specific dispatch ID."""
    return f"{DOMAIN}.{entry.entry_id}.{dispatch}"


class ProtectData:
    """Coordinate updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        protect: ProtectApiClient,
        update_interval: timedelta,
        entry: UFPConfigEntry,
    ) -> None:
        """Initialize an subscriber."""
        self._entry = entry
        self._hass = hass
        self._update_interval = update_interval
        self._subscriptions: defaultdict[
            str, set[Callable[[ProtectDeviceType], None]]
        ] = defaultdict(set)
        self._pending_camera_ids: set[str] = set()
        self._unsubs: list[CALLBACK_TYPE] = []
        self._auth_failures = 0
        self._camera_rtsps_streams: dict[str, RTSPSStreams] = {}
        self._camera_rtsps_checked: set[str] = set()
        self.last_update_success = False
        self.api = protect
        self.adopt_signal = _async_dispatch_id(entry, DISPATCH_ADOPT)
        self.add_signal = _async_dispatch_id(entry, DISPATCH_ADD)
        self.channels_signal = _async_dispatch_id(entry, DISPATCH_CHANNELS)
        self.streams_signal = _async_dispatch_id(entry, DISPATCH_STREAMS)

    @property
    def config_entry(self) -> UFPConfigEntry:
        """Return the config entry."""
        return self._entry

    @property
    def disable_stream(self) -> bool:
        """Check if RTSP is disabled."""
        return self._entry.options.get(CONF_DISABLE_RTSP, False)  # type: ignore[no-any-return]

    @property
    def max_events(self) -> int:
        """Max number of events to load at once."""
        return self._entry.options.get(CONF_MAX_MEDIA, DEFAULT_MAX_MEDIA)  # type: ignore[no-any-return]

    def get_camera_rtsps_streams(self, camera_id: str) -> RTSPSStreams | None:
        """Get cached RTSPS streams for a camera."""
        return self._camera_rtsps_streams.get(camera_id)

    def is_camera_rtsps_checked(self, camera_id: str) -> bool:
        """Check if RTSPS streams have been fetched for a camera."""
        return camera_id in self._camera_rtsps_checked

    def set_camera_rtsps_streams(
        self, camera_id: str, streams: RTSPSStreams | None
    ) -> None:
        """Set cached RTSPS streams for a camera."""
        self._camera_rtsps_checked.add(camera_id)
        if streams is not None:
            self._camera_rtsps_streams[camera_id] = streams
        elif camera_id in self._camera_rtsps_streams:
            del self._camera_rtsps_streams[camera_id]

    @callback
    def async_update_camera_rtsps_streams(
        self, camera_id: str, streams: RTSPSStreams
    ) -> None:
        """Update cached RTSPS streams for a camera and signal entities to refresh."""
        self._camera_rtsps_checked.add(camera_id)
        self._camera_rtsps_streams[camera_id] = streams
        async_dispatcher_send(self._hass, self.streams_signal, camera_id)

    @callback
    def async_clear_rtsps_streams_cache(self) -> None:
        """Clear all cached RTSPS streams and signal entities to refresh."""
        self._camera_rtsps_streams.clear()
        self._camera_rtsps_checked.clear()
        async_dispatcher_send(self._hass, self.streams_signal)

    @callback
    def async_clear_camera_rtsps_streams(self, camera_id: str) -> None:
        """Clear cached RTSPS streams for a specific camera and signal to refresh."""
        self._camera_rtsps_checked.discard(camera_id)
        if camera_id in self._camera_rtsps_streams:
            del self._camera_rtsps_streams[camera_id]
            async_dispatcher_send(self._hass, self.streams_signal, camera_id)

    @callback
    def async_subscribe_adopt(
        self, add_callback: Callable[[ProtectAdoptableDeviceModel], None]
    ) -> None:
        """Add an callback for on device adopt."""
        self._entry.async_on_unload(
            async_dispatcher_connect(self._hass, self.adopt_signal, add_callback)
        )

    def get_by_types(
        self, device_types: Iterable[ModelType], ignore_unadopted: bool = True
    ) -> Generator[ProtectAdoptableDeviceModel]:
        """Get all devices matching types."""
        bootstrap = self.api.bootstrap
        for device_type in device_types:
            for device in async_get_devices_by_type(bootstrap, device_type).values():
                if ignore_unadopted and not device.is_adopted_by_us:
                    continue
                yield device

    def get_cameras(self, ignore_unadopted: bool = True) -> Generator[Camera]:
        """Get all cameras."""
        return cast(
            Generator[Camera], self.get_by_types({ModelType.CAMERA}, ignore_unadopted)
        )

    async def async_setup(self) -> None:
        """Subscribe and do the refresh."""
        self.last_update_success = True
        self._async_update_change(True, force_update=True)
        api = self.api
        self._unsubs = [
            api.subscribe_websocket_state(self._async_websocket_state_changed),
            api.subscribe_websocket(self._async_process_ws_message),
            async_track_time_interval(
                self._hass, self._async_poll, self._update_interval
            ),
        ]
        # Pre-fetch RTSPS streams for all cameras to avoid rate limiting
        # when individual camera entities are set up
        await self._async_fetch_all_rtsps_streams()

    async def _async_fetch_all_rtsps_streams(self) -> None:
        """Fetch RTSPS streams for all cameras sequentially to avoid rate limiting."""
        if self.disable_stream:
            return
        for camera in self.get_cameras():
            if camera.id in self._camera_rtsps_checked:
                continue
            try:
                streams = await camera.get_rtsps_streams()
                # Always mark as checked, even if streams is None
                self.set_camera_rtsps_streams(camera.id, streams)
            except NotAuthorized:
                _LOGGER.warning(
                    "Cannot fetch RTSPS streams without API key for %s",
                    camera.display_name,
                )
                break  # No point trying other cameras if auth is missing
            except (ClientError, NvrError) as ex:
                _LOGGER.debug(
                    "Error fetching RTSPS streams for %s: %s",
                    camera.display_name,
                    ex,
                )
                # Mark as checked to prevent repeated API calls from entities
                self.set_camera_rtsps_streams(camera.id, None)

    @callback
    def _async_websocket_state_changed(self, state: WebsocketState) -> None:
        """Handle a change in the websocket state."""
        was_connected = self.last_update_success
        is_connected = state is WebsocketState.CONNECTED
        self._async_update_change(is_connected)
        # Refresh RTSPS streams when reconnecting after a disconnect
        if is_connected and not was_connected:
            self.async_clear_rtsps_streams_cache()

    def _async_update_change(
        self,
        success: bool,
        force_update: bool = False,
        exception: Exception | None = None,
    ) -> None:
        """Process a change in update success."""
        was_success = self.last_update_success
        self.last_update_success = success

        if not success:
            level = logging.ERROR if was_success else logging.DEBUG
            title = self._entry.title
            _LOGGER.log(level, "%s: Connection lost", title, exc_info=exception)
            self._async_process_updates()
            return

        self._auth_failures = 0
        if not was_success:
            _LOGGER.warning("%s: Connection restored", self._entry.title)
            self._async_process_updates()
        elif force_update:
            self._async_process_updates()

    async def async_stop(self, *args: Any) -> None:
        """Stop processing data."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self.api.async_disconnect_ws()

    async def async_refresh(self) -> None:
        """Update the data."""
        try:
            await self.api.update()
        except NotAuthorized as ex:
            if self._auth_failures < AUTH_RETRIES:
                _LOGGER.exception("Auth error while updating")
                self._auth_failures += 1
            else:
                await self.async_stop()
                _LOGGER.exception("Reauthentication required")
                self._entry.async_start_reauth(self._hass)
            self._async_update_change(False, exception=ex)
        except ClientError as ex:
            self._async_update_change(False, exception=ex)
        else:
            self._async_update_change(True, force_update=True)

    @callback
    def async_add_pending_camera_id(self, camera_id: str) -> None:
        """Add pending camera.

        A "pending camera" is one that has been adopted by not had its camera channels
        initialized yet. Will cause Websocket code to check for channels to be
        initialized for the camera and issue a dispatch once they do.
        """
        self._pending_camera_ids.add(camera_id)

    @callback
    def _async_add_device(self, device: ProtectAdoptableDeviceModel) -> None:
        if device.is_adopted_by_us:
            _LOGGER.debug("Device adopted: %s", device.id)
            async_dispatcher_send(self._hass, self.adopt_signal, device)
        else:
            _LOGGER.debug("New device detected: %s", device.id)
            async_dispatcher_send(self._hass, self.add_signal, device)

    @callback
    def _async_remove_device(self, device: ProtectAdoptableDeviceModel) -> None:
        registry = dr.async_get(self._hass)
        device_entry = registry.async_get_device(
            connections={(dr.CONNECTION_NETWORK_MAC, device.mac)}
        )
        if device_entry:
            _LOGGER.debug("Device removed: %s", device.id)
            registry.async_update_device(
                device_entry.id, remove_config_entry_id=self._entry.entry_id
            )

    @callback
    def _async_update_device(
        self, device: ProtectAdoptableDeviceModel | NVR, changed_data: dict[str, Any]
    ) -> None:
        self._async_signal_device_update(device)
        if device.model is ModelType.CAMERA:
            if device.id in self._pending_camera_ids and "channels" in changed_data:
                self._pending_camera_ids.remove(device.id)
                async_dispatcher_send(self._hass, self.channels_signal, device)

            # Channels or IP address changed, invalidate stream URL cache for this camera
            if (
                "channels" in changed_data
                or "host" in changed_data
                or "connection_host" in changed_data
            ):
                self.async_clear_camera_rtsps_streams(device.id)

        # trigger update for all Cameras with LCD screens when NVR Doorbell settings updates
        if "doorbell_settings" in changed_data:
            _LOGGER.debug(
                "Doorbell messages updated. Updating devices with LCD screens"
            )
            self.api.bootstrap.nvr.update_all_messages()
            for camera in self.get_cameras():
                if camera.feature_flags.has_lcd_screen:
                    self._async_signal_device_update(camera)

    @callback
    def _async_process_ws_message(self, message: WSSubscriptionMessage) -> None:
        """Process a message from the websocket."""
        if (new_obj := message.new_obj) is None:
            if isinstance(message.old_obj, ProtectAdoptableDeviceModel):
                self._async_remove_device(message.old_obj)
            return

        model_type = new_obj.model
        if model_type is ModelType.EVENT:
            if TYPE_CHECKING:
                assert isinstance(new_obj, Event)
            if _LOGGER.isEnabledFor(logging.DEBUG):
                log_event(new_obj)
            if (
                (new_obj.type is EventType.DEVICE_ADOPTED)
                and (metadata := new_obj.metadata)
                and (device_id := metadata.device_id)
                and (device := self.api.bootstrap.get_device_from_id(device_id))
            ):
                self._async_add_device(device)
            elif camera := new_obj.camera:
                self._async_signal_device_update(camera)
            elif light := new_obj.light:
                self._async_signal_device_update(light)
            elif sensor := new_obj.sensor:
                self._async_signal_device_update(sensor)
            return

        if model_type is ModelType.LIVEVIEW and len(self.api.bootstrap.viewers) > 0:
            # alert user viewport needs restart so voice clients can get new options
            _LOGGER.warning(
                "Liveviews updated. Restart Home Assistant to update Viewport select"
                " options"
            )
            return

        if message.old_obj is None and isinstance(new_obj, ProtectAdoptableDeviceModel):
            self._async_add_device(new_obj)
            return

        if getattr(new_obj, "is_adopted_by_us", True) and hasattr(new_obj, "mac"):
            if TYPE_CHECKING:
                assert isinstance(new_obj, (ProtectAdoptableDeviceModel, NVR))
            self._async_update_device(new_obj, message.changed_data)

    @callback
    def _async_process_updates(self) -> None:
        """Process update from the protect data."""
        self._async_signal_device_update(self.api.bootstrap.nvr)
        for device in self.get_by_types(DEVICES_THAT_ADOPT):
            self._async_signal_device_update(device)

    @callback
    def _async_poll(self, now: datetime) -> None:
        """Poll the Protect API."""
        self._entry.async_create_background_task(
            self._hass,
            self.async_refresh(),
            name=f"{DOMAIN} {self._entry.title} refresh",
            eager_start=True,
        )

    @callback
    def async_subscribe(
        self, mac: str, update_callback: Callable[[ProtectDeviceType], None]
    ) -> CALLBACK_TYPE:
        """Add an callback subscriber."""
        self._subscriptions[mac].add(update_callback)
        return partial(self._async_unsubscribe, mac, update_callback)

    @callback
    def _async_unsubscribe(
        self, mac: str, update_callback: Callable[[ProtectDeviceType], None]
    ) -> None:
        """Remove a callback subscriber."""
        self._subscriptions[mac].remove(update_callback)
        if not self._subscriptions[mac]:
            del self._subscriptions[mac]

    @callback
    def _async_signal_device_update(self, device: ProtectDeviceType) -> None:
        """Call the callbacks for a device_id."""
        mac = device.mac
        if not (subscriptions := self._subscriptions.get(mac)):
            return
        _LOGGER.debug("Updating device: %s (%s)", device.name, mac)
        for update_callback in subscriptions:
            update_callback(device)


@callback
def async_ufp_instance_for_config_entry_ids(
    hass: HomeAssistant, config_entry_ids: set[str]
) -> ProtectApiClient | None:
    """Find the UFP instance for the config entry ids."""
    return next(
        iter(
            entry.runtime_data.api
            for entry_id in config_entry_ids
            if (entry := hass.config_entries.async_get_entry(entry_id))
            and entry.domain == DOMAIN
            and hasattr(entry, "runtime_data")
        ),
        None,
    )


@callback
def async_get_ufp_entries(hass: HomeAssistant) -> list[UFPConfigEntry]:
    """Get all the UFP entries."""
    return cast(
        list[UFPConfigEntry],
        [
            entry
            for entry in hass.config_entries.async_entries(
                DOMAIN, include_ignore=True, include_disabled=True
            )
            if hasattr(entry, "runtime_data")
        ],
    )


@callback
def async_get_data_for_nvr_id(hass: HomeAssistant, nvr_id: str) -> ProtectData | None:
    """Find the ProtectData instance for the NVR id."""
    return next(
        iter(
            entry.runtime_data
            for entry in async_get_ufp_entries(hass)
            if entry.runtime_data.api.bootstrap.nvr.id == nvr_id
        ),
        None,
    )


@callback
def async_get_data_for_entry_id(
    hass: HomeAssistant, entry_id: str
) -> ProtectData | None:
    """Find the ProtectData instance for a config entry id."""
    if (entry := hass.config_entries.async_get_entry(entry_id)) and hasattr(
        entry, "runtime_data"
    ):
        entry = cast(UFPConfigEntry, entry)
        return entry.runtime_data
    return None
