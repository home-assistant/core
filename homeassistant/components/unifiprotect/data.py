"""Base class for protect data."""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterable
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import Any, cast

from pyunifiprotect import ProtectApiClient
from pyunifiprotect.data import (
    NVR,
    Bootstrap,
    Camera,
    Event,
    EventType,
    Liveview,
    ModelType,
    ProtectAdoptableDeviceModel,
    WSSubscriptionMessage,
)
from pyunifiprotect.exceptions import ClientError, NotAuthorized
from pyunifiprotect.utils import log_event

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
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
    DOMAIN,
)
from .utils import async_dispatch_id as _ufpd, async_get_devices_by_type

_LOGGER = logging.getLogger(__name__)
ProtectDeviceType = ProtectAdoptableDeviceModel | NVR


@callback
def async_last_update_was_successful(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Check if the last update was successful for a config entry."""
    return bool(
        DOMAIN in hass.data
        and entry.entry_id in hass.data[DOMAIN]
        and hass.data[DOMAIN][entry.entry_id].last_update_success
    )


class ProtectData:
    """Coordinate updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        protect: ProtectApiClient,
        update_interval: timedelta,
        entry: ConfigEntry,
    ) -> None:
        """Initialize an subscriber."""
        super().__init__()

        self._hass = hass
        self._entry = entry
        self._hass = hass
        self._update_interval = update_interval
        self._subscriptions: dict[str, list[Callable[[ProtectDeviceType], None]]] = {}
        self._pending_camera_ids: set[str] = set()
        self._unsub_interval: CALLBACK_TYPE | None = None
        self._unsub_websocket: CALLBACK_TYPE | None = None
        self._auth_failures = 0

        self.last_update_success = False
        self.api = protect

    @property
    def disable_stream(self) -> bool:
        """Check if RTSP is disabled."""
        return self._entry.options.get(CONF_DISABLE_RTSP, False)

    @property
    def max_events(self) -> int:
        """Max number of events to load at once."""
        return self._entry.options.get(CONF_MAX_MEDIA, DEFAULT_MAX_MEDIA)

    def get_by_types(
        self, device_types: Iterable[ModelType], ignore_unadopted: bool = True
    ) -> Generator[ProtectAdoptableDeviceModel, None, None]:
        """Get all devices matching types."""
        for device_type in device_types:
            devices = async_get_devices_by_type(
                self.api.bootstrap, device_type
            ).values()
            for device in devices:
                if ignore_unadopted and not device.is_adopted_by_us:
                    continue
                yield device

    async def async_setup(self) -> None:
        """Subscribe and do the refresh."""
        self._unsub_websocket = self.api.subscribe_websocket(
            self._async_process_ws_message
        )
        await self.async_refresh()

    async def async_stop(self, *args: Any) -> None:
        """Stop processing data."""
        if self._unsub_websocket:
            self._unsub_websocket()
            self._unsub_websocket = None
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None
        await self.api.async_disconnect_ws()

    async def async_refresh(self, *_: Any, force: bool = False) -> None:
        """Update the data."""

        # if last update was failure, force until success
        if not self.last_update_success:
            force = True

        try:
            updates = await self.api.update(force=force)
        except NotAuthorized:
            if self._auth_failures < AUTH_RETRIES:
                _LOGGER.exception("Auth error while updating")
                self._auth_failures += 1
            else:
                await self.async_stop()
                _LOGGER.exception("Reauthentication required")
                self._entry.async_start_reauth(self._hass)
            self.last_update_success = False
        except ClientError:
            if self.last_update_success:
                _LOGGER.exception("Error while updating")
            self.last_update_success = False
            # manually trigger update to mark entities unavailable
            self._async_process_updates(self.api.bootstrap)
        else:
            self.last_update_success = True
            self._auth_failures = 0
            self._async_process_updates(updates)

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
            async_dispatcher_send(
                self._hass, _ufpd(self._entry, DISPATCH_ADOPT), device
            )
        else:
            _LOGGER.debug("New device detected: %s", device.id)
            async_dispatcher_send(self._hass, _ufpd(self._entry, DISPATCH_ADD), device)

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
        if (
            device.model is ModelType.CAMERA
            and device.id in self._pending_camera_ids
            and "channels" in changed_data
        ):
            self._pending_camera_ids.remove(device.id)
            async_dispatcher_send(
                self._hass, _ufpd(self._entry, DISPATCH_CHANNELS), device
            )

        # trigger update for all Cameras with LCD screens when NVR Doorbell settings updates
        if "doorbell_settings" in changed_data:
            _LOGGER.debug(
                "Doorbell messages updated. Updating devices with LCD screens"
            )
            self.api.bootstrap.nvr.update_all_messages()
            for camera in self.get_by_types({ModelType.CAMERA}):
                camera = cast(Camera, camera)
                if camera.feature_flags.has_lcd_screen:
                    self._async_signal_device_update(camera)

    @callback
    def _async_process_ws_message(self, message: WSSubscriptionMessage) -> None:
        if message.new_obj is None:
            if isinstance(message.old_obj, ProtectAdoptableDeviceModel):
                self._async_remove_device(message.old_obj)
            return

        obj = message.new_obj
        if isinstance(obj, (ProtectAdoptableDeviceModel, NVR)):
            if message.old_obj is None and isinstance(obj, ProtectAdoptableDeviceModel):
                self._async_add_device(obj)
            elif getattr(obj, "is_adopted_by_us", True):
                self._async_update_device(obj, message.changed_data)

        # trigger updates for camera that the event references
        elif isinstance(obj, Event):
            if _LOGGER.isEnabledFor(logging.DEBUG):
                log_event(obj)
            if obj.type is EventType.DEVICE_ADOPTED:
                if obj.metadata is not None and obj.metadata.device_id is not None:
                    device = self.api.bootstrap.get_device_from_id(
                        obj.metadata.device_id
                    )
                    if device is not None:
                        self._async_add_device(device)
            elif obj.camera is not None:
                self._async_signal_device_update(obj.camera)
            elif obj.light is not None:
                self._async_signal_device_update(obj.light)
            elif obj.sensor is not None:
                self._async_signal_device_update(obj.sensor)
        # alert user viewport needs restart so voice clients can get new options
        elif len(self.api.bootstrap.viewers) > 0 and isinstance(obj, Liveview):
            _LOGGER.warning(
                "Liveviews updated. Restart Home Assistant to update Viewport select"
                " options"
            )

    @callback
    def _async_process_updates(self, updates: Bootstrap | None) -> None:
        """Process update from the protect data."""

        # Websocket connected, use data from it
        if updates is None:
            return

        self._async_signal_device_update(self.api.bootstrap.nvr)
        for device in self.get_by_types(DEVICES_THAT_ADOPT):
            self._async_signal_device_update(device)

    @callback
    def _async_poll(self, now: datetime) -> None:
        """Poll the Protect API.

        If the websocket is connected, most of the time
        this will be a no-op. If the websocket is disconnected,
        this will trigger a reconnect and refresh.
        """
        self._entry.async_create_background_task(
            self._hass,
            self.async_refresh(),
            name=f"{DOMAIN} {self._entry.title} refresh",
            eager_start=True,
        )

    @callback
    def async_subscribe_device_id(
        self, mac: str, update_callback: Callable[[ProtectDeviceType], None]
    ) -> CALLBACK_TYPE:
        """Add an callback subscriber."""
        if not self._subscriptions:
            self._unsub_interval = async_track_time_interval(
                self._hass, self._async_poll, self._update_interval
            )
        self._subscriptions.setdefault(mac, []).append(update_callback)
        return partial(self.async_unsubscribe_device_id, mac, update_callback)

    @callback
    def async_unsubscribe_device_id(
        self, mac: str, update_callback: Callable[[ProtectDeviceType], None]
    ) -> None:
        """Remove a callback subscriber."""
        self._subscriptions[mac].remove(update_callback)
        if not self._subscriptions[mac]:
            del self._subscriptions[mac]
        if not self._subscriptions and self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None

    @callback
    def _async_signal_device_update(self, device: ProtectDeviceType) -> None:
        """Call the callbacks for a device_id."""
        if not (subscriptions := self._subscriptions.get(device.mac)):
            return
        _LOGGER.debug("Updating device: %s (%s)", device.name, device.mac)
        for update_callback in subscriptions:
            update_callback(device)


@callback
def async_ufp_instance_for_config_entry_ids(
    hass: HomeAssistant, config_entry_ids: set[str]
) -> ProtectApiClient | None:
    """Find the UFP instance for the config entry ids."""
    domain_data = hass.data[DOMAIN]
    for config_entry_id in config_entry_ids:
        if config_entry_id in domain_data:
            protect_data: ProtectData = domain_data[config_entry_id]
            return protect_data.api
    return None
