"""Base class for protect data."""

import asyncio
from collections import defaultdict
from collections.abc import Callable, Generator, Iterable
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, cast

from aiohttp.client_exceptions import ServerDisconnectedError
from uiprotect import EventChange, ProtectApiClient, ProtectEvent
from uiprotect.api import RTSPSStreams
from uiprotect.data import (
    NVR,
    Camera,
    Event,
    EventType,
    ModelType,
    ProtectAdoptableDeviceModel,
    PTZPatrol,
    PublicDeviceModel,
    WSAction,
    WSSubscriptionMessage,
)
from uiprotect.data.public_devices import PublicCamera
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
        self._public_event_subscriptions: defaultdict[
            tuple[str, EventType], set[Callable[[ProtectEvent], None]]
        ] = defaultdict(set)
        self._public_subscriptions: defaultdict[
            str, set[Callable[[PublicDeviceModel | None], None]]
        ] = defaultdict(set)
        self._pending_camera_ids: set[str] = set()
        self._unsubs: list[CALLBACK_TYPE] = []
        self._auth_failures = 0
        self.auth_retries = 0
        self.last_update_success = False
        self.last_public_update_success = False
        self.api = protect
        self.adopt_signal = _async_dispatch_id(entry, DISPATCH_ADOPT)
        self.add_signal = _async_dispatch_id(entry, DISPATCH_ADD)
        self.channels_signal = _async_dispatch_id(entry, DISPATCH_CHANNELS)
        # PTZ patrol cache: camera_id -> list of patrols
        self.ptz_patrols: dict[str, list[PTZPatrol]] = {}

    @property
    def disable_stream(self) -> bool:
        """Check if RTSP is disabled."""
        return self._entry.options.get(CONF_DISABLE_RTSP, False)  # type: ignore[no-any-return]

    @property
    def max_events(self) -> int:
        """Max number of events to load at once."""
        return self._entry.options.get(CONF_MAX_MEDIA, DEFAULT_MAX_MEDIA)  # type: ignore[no-any-return]

    def get_rtsps_streams(self, camera_id: str) -> RTSPSStreams | None:
        """Return the library-owned public-API RTSPS streams for a camera.

        The library primes ``PublicCamera.rtsps_streams`` during
        ``update_public()`` and keeps it fresh (reconnect refresh + create/delete
        write-through), so the integration reads it synchronously and stores
        nothing itself.
        """
        api = self.api
        if not api.has_public_bootstrap:
            return None
        camera = api.public_bootstrap.cameras.get(camera_id)
        return camera.rtsps_streams if camera is not None else None

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

    def get_public_cameras(
        self,
    ) -> Generator[tuple[PublicCamera | None, Camera | None]]:
        """Iterate cameras public-master with private-fill.

        The public bootstrap is the master list; the matching private camera is
        paired by shared id when present (hybrid) and ``None`` in public-only
        mode. An adopted private camera not (yet) mirrored into the public
        bootstrap is yielded as ``(None, private)`` so the caller can defer it.
        Adopted-filtering mirrors ``get_cameras`` whenever a private object is
        available.
        """
        api = self.api
        if not api.has_public_bootstrap:
            return
        # An API-key-only client never initializes the private bootstrap;
        # accessing it would raise.
        private_cameras: dict[str, Camera] = (
            {} if api.is_public_only else api.bootstrap.cameras
        )
        public_cameras = api.public_bootstrap.cameras
        for camera_id, public in public_cameras.items():
            private = private_cameras.get(camera_id)
            if private is not None and not private.is_adopted_by_us:
                continue
            yield public, private
        for camera_id, private in private_cameras.items():
            if camera_id in public_cameras or not private.is_adopted_by_us:
                continue
            yield None, private

    async def async_load_ptz_patrols(self) -> None:
        """Load PTZ patrols for all PTZ cameras."""
        await asyncio.gather(
            *(
                self.async_load_ptz_patrols_for_camera(camera)
                for camera in self.get_cameras()
            )
        )

    async def async_load_ptz_patrols_for_camera(self, camera: Camera) -> None:
        """Load PTZ patrols for a specific camera."""
        if camera.feature_flags.is_ptz:
            try:
                self.ptz_patrols[camera.id] = await camera.get_ptz_patrols()
            except ClientError:
                _LOGGER.debug(
                    "Failed to load PTZ patrols for camera %s",
                    camera.display_name,
                )
                self.ptz_patrols[camera.id] = []

    @callback
    def async_setup(self) -> None:
        """Subscribe and do the refresh."""
        self.last_update_success = True
        self.last_public_update_success = True
        self._async_update_change(True, force_update=True)
        api = self.api
        self._unsubs = [
            api.subscribe_websocket_state(self._async_websocket_state_changed),
            api.subscribe_websocket(self._async_process_ws_message),
            async_track_time_interval(
                self._hass, self._async_poll, self._update_interval
            ),
            # Subscribe to the public devices websocket unconditionally so that
            # it is active before update_public() primes the cache.
            # Per library docs: subscribe first, then call update_public().
            api.subscribe_devices_websocket(
                self._async_process_public_devices_ws_message
            ),
            api.subscribe_devices_websocket_state(self._async_public_ws_state_changed),
        ]

    @callback
    def async_subscribe_public_events(self) -> None:
        """Subscribe to the public events websocket.

        Must run *after* ``update_public()`` has primed the public bootstrap;
        the setup flow guarantees this (a failed prime aborts setup), and
        ``subscribe_events()`` raises otherwise. This is the source of truth for
        the event entities driven off the public websocket: the doorbell ring,
        and the smart-detect events (e.g. package) that the private API only
        surfaces as the unhandled ``smartDetectObject`` model. uiprotect owns
        websocket reconnection and keeps the callback attached, so this is a
        one-shot.
        """
        self._unsubs.append(self.api.subscribe_events(self._async_process_public_event))

    @callback
    def _async_process_public_devices_ws_message(
        self, message: WSSubscriptionMessage
    ) -> None:
        """Process a message from the public devices websocket.

        DEVICES_WS_SUBSCRIBED_MODELS is an empty set, which the API client treats
        as "all models", so messages are not pre-filtered. NVR messages signal the
        private NVR so alarm entities pick up the new arm state. Every other
        public device inherits ``PublicDeviceModel`` and is dispatched by mac.
        Frames without a merged object dispatch ``None`` and subscribers re-read
        the public bootstrap: on a delete the library has already removed the
        object (it reads as missing and entities go unavailable), while a frame
        the library could not merge leaves the previous object cached.
        """
        new_obj = message.new_obj
        if new_obj is None:
            old_obj = message.old_obj
            if isinstance(old_obj, PublicDeviceModel):
                self._async_signal_public_update(old_obj.mac, None)
            return
        if new_obj.model is ModelType.NVR:
            # An API-key-only client has no private NVR (reading it would raise).
            if not self.api.is_public_only:
                self._async_signal_device_update(self.api.bootstrap.nvr)
            return
        if isinstance(new_obj, PublicDeviceModel):
            if new_obj.model is ModelType.CAMERA:
                self._async_reenumerate_camera_on_public_change(new_obj, message)
            self._async_signal_public_update(new_obj.mac, new_obj)

    @callback
    def _async_reenumerate_camera_on_public_change(
        self, new_obj: PublicDeviceModel, message: WSSubscriptionMessage
    ) -> None:
        """Re-run camera enumeration when a public frame can add entities.

        Three cases dispatch the public camera to the channels signal:

        - A camera deferred at enumeration because its public mirror had not
          arrived yet (the private channels-update path cannot be relied on to
          fire again).
        - A camera whose RTSPS streams the library primes in the background
          after it comes online or is added, announced by an ``rtsps_streams``
          change: the quality tiers that just became active still need their
          entities.
        - In public-only mode, a newly added camera — there is no private
          adopt path that could discover it.

        The platform adds only entities that do not exist yet, so overlapping
        re-enumerations are safe.
        """
        if new_obj.id in self._pending_camera_ids:
            self._pending_camera_ids.remove(new_obj.id)
        elif "rtsps_streams" not in message.changed_data and not (
            self.api.is_public_only and message.action is WSAction.ADD
        ):
            return
        async_dispatcher_send(self._hass, self.channels_signal, new_obj)

    @callback
    def _async_process_public_event(
        self, event: ProtectEvent, change: EventChange
    ) -> None:
        """Dispatch a public events websocket event to its subscribers.

        Only the start of an event is dispatched, routed to the subscribers that
        registered for this device and event type; an entity that cares about a
        sub-type (e.g. a smart-detect object type) filters further itself.
        Subscriptions are keyed by ``device_id`` (the stable cross-API join key,
        shared by the private and public bootstraps), so the event routes
        directly without a bootstrap lookup.
        """
        if change is not EventChange.STARTED:
            return
        if not (
            subscriptions := self._public_event_subscriptions.get(
                (event.device_id, event.type)
            )
        ):
            return
        for update_callback in subscriptions:
            update_callback(event)

    @callback
    def _async_websocket_state_changed(self, state: WebsocketState) -> None:
        """Handle a change in the websocket state."""
        self._async_update_change(state is WebsocketState.CONNECTED)

    @callback
    def _async_public_ws_state_changed(self, state: WebsocketState) -> None:
        """Handle a change in the public devices websocket state."""
        success = state is WebsocketState.CONNECTED
        if success == self.last_public_update_success:
            return
        self.last_public_update_success = success
        self._async_process_public_updates()
        if success:
            # The library resyncs its public bootstrap on reconnect, but the
            # resync applies silently and races this callback, so the re-read
            # above may see the pre-disconnect cache. Refresh again behind a
            # guaranteed-fresh snapshot (``update_public`` is serialized) so a
            # change from the disconnect gap cannot stay stale.
            self._entry.async_create_background_task(
                self._hass,
                self._async_resignal_after_public_resync(),
                "unifiprotect public reconnect refresh",
            )

    async def _async_resignal_after_public_resync(self) -> None:
        """Re-signal public entities once a fresh public snapshot is applied."""
        try:
            await self.api.update_public()
        except NotAuthorized:
            # A revoked API key cannot self-recover.
            self._entry.async_start_reauth(self._hass)
            return
        except (TimeoutError, ClientError, ServerDisconnectedError) as err:
            # Transport errors retry on the next reconnect.
            _LOGGER.debug("Public refresh after reconnect failed: %s", err)
            return
        self._async_process_public_updates()
        # Existing subscriptions are refreshed above, but a camera that
        # appeared (or gained streams) during the gap still needs its
        # entities; the platform adds only the missing ones.
        if self.api.has_public_bootstrap:
            for public in list(self.api.public_bootstrap.cameras.values()):
                async_dispatcher_send(self._hass, self.channels_signal, public)

    @callback
    def _async_process_public_updates(self) -> None:
        """Re-signal public-API entities after a public websocket state change."""
        api = self.api
        if not api.has_public_bootstrap:
            return
        # The NVR alarm panel reads the public arm_mode, so refresh it too.
        # An API-key-only client has no private NVR (reading it would raise).
        if not api.is_public_only:
            self._async_signal_device_update(api.bootstrap.nvr)
        # Subscribers recompute from the public bootstrap on ``None``.
        for subscriptions in self._public_subscriptions.values():
            for update_callback in subscriptions:
                update_callback(None)

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
            if isinstance(device, Camera) and device.feature_flags.is_ptz:
                self._hass.async_create_task(
                    self._async_adopt_ptz_camera(device),
                    name="unifiprotect_adopt_ptz_camera",
                )
            else:
                async_dispatcher_send(self._hass, self.adopt_signal, device)
        else:
            _LOGGER.debug("New device detected: %s", device.id)
            async_dispatcher_send(self._hass, self.add_signal, device)

    async def _async_adopt_ptz_camera(self, camera: Camera) -> None:
        """Load PTZ patrol data and dispatch adopt signal for a PTZ camera."""
        await self.async_load_ptz_patrols_for_camera(camera)
        async_dispatcher_send(self._hass, self.adopt_signal, camera)

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

        # trigger update for all Cameras with LCD screens
        # when NVR Doorbell settings updates
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
        """Process an update from the private protect connection.

        Public-API entities (relay/siren/alarm) are driven by the public
        websocket via ``_async_process_public_updates``, not from here.
        """
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
    def async_subscribe_public_event(
        self,
        device_id: str,
        event_type: EventType,
        update_callback: Callable[[ProtectEvent], None],
    ) -> CALLBACK_TYPE:
        """Add a callback subscriber for public events of a type by device id."""
        key = (device_id, event_type)
        self._public_event_subscriptions[key].add(update_callback)
        return partial(self._async_unsubscribe_public_event, key, update_callback)

    @callback
    def _async_unsubscribe_public_event(
        self,
        key: tuple[str, EventType],
        update_callback: Callable[[ProtectEvent], None],
    ) -> None:
        """Remove a public event callback subscriber."""
        self._public_event_subscriptions[key].remove(update_callback)
        if not self._public_event_subscriptions[key]:
            del self._public_event_subscriptions[key]

    @callback
    def async_subscribe_public(
        self, mac: str, update_callback: Callable[[PublicDeviceModel | None], None]
    ) -> CALLBACK_TYPE:
        """Add a callback subscriber for public devices WS updates by mac."""
        self._public_subscriptions[mac].add(update_callback)
        return partial(self._async_unsubscribe_public, mac, update_callback)

    @callback
    def _async_unsubscribe_public(
        self, mac: str, update_callback: Callable[[PublicDeviceModel | None], None]
    ) -> None:
        """Remove a public callback subscriber."""
        self._public_subscriptions[mac].remove(update_callback)
        if not self._public_subscriptions[mac]:
            del self._public_subscriptions[mac]

    @callback
    def async_get_public_device(
        self, device: ProtectDeviceType | PublicDeviceModel
    ) -> PublicDeviceModel | None:
        """Return the public-API object matching a device, if available."""
        api = self.api
        if not api.has_public_bootstrap or device.model is None:
            return None
        # Migrated entities target dedicated public device models, which all
        # inherit from PublicDeviceModel (carrying mac/state).
        return cast(
            "PublicDeviceModel | None",
            api.public_bootstrap.get(device.model, device.id),
        )

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
    def _async_signal_public_update(
        self, mac: str, obj: PublicDeviceModel | None
    ) -> None:
        """Call the public-device callbacks for a mac.

        ``None`` means the object is gone from (or must be re-read from) the
        public bootstrap.
        """
        if not (subscriptions := self._public_subscriptions.get(mac)):
            return
        if obj is not None:
            _LOGGER.debug("Updating public device: %s (%s)", obj.id, mac)
        else:
            _LOGGER.debug("Re-reading public device from bootstrap: %s", mac)
        for update_callback in subscriptions:
            update_callback(obj)


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
