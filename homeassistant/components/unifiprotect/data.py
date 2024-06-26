"""Base class for protect data."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, cast

from typing_extensions import Generator
from uiprotect import ProtectApiClient
from uiprotect.data import (
    NVR,
    Camera,
    Event,
    EventType,
    ModelType,
    ProtectAdoptableDeviceModel,
    WSSubscriptionMessage,
)
from uiprotect.exceptions import ClientError, NotAuthorized
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
        self.last_update_success = False
        self.api = protect
        self.adopt_signal = _async_dispatch_id(entry, DISPATCH_ADOPT)
        self.add_signal = _async_dispatch_id(entry, DISPATCH_ADD)
        self.channels_signal = _async_dispatch_id(entry, DISPATCH_CHANNELS)

    @property
    def disable_stream(self) -> bool:
        """Check if RTSP is disabled."""
        return self._entry.options.get(CONF_DISABLE_RTSP, False)

    @property
    def max_events(self) -> int:
        """Max number of events to load at once."""
        return self._entry.options.get(CONF_MAX_MEDIA, DEFAULT_MAX_MEDIA)

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

    @callback
    def async_setup(self) -> None:
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

    @callback
    def _async_websocket_state_changed(self, state: WebsocketState) -> None:
        """Handle a change in the websocket state."""
        self._async_update_change(state is WebsocketState.CONNECTED)

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
            _LOGGER.info("%s: Connection restored", self._entry.title)
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
        if (
            device.model is ModelType.CAMERA
            and device.id in self._pending_camera_ids
            and "channels" in changed_data
        ):
            self._pending_camera_ids.remove(device.id)
            async_dispatcher_send(self._hass, self.channels_signal, device)

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
