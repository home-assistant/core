"""Data coordinators for the ring integration."""

from asyncio import TaskGroup
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, override

from ring_doorbell import (
    AuthenticationError,
    Ring,
    RingDevices,
    RingError,
    RingEvent,
    RingTimeout,
)
from ring_doorbell.listen import RingEventListener

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import (
    BaseDataUpdateCoordinatorProtocol,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONF_LISTEN_CREDENTIALS, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

LISTENER_CHECK_INTERVAL = timedelta(minutes=1)
LISTENER_MAX_RESTART_DELAY = timedelta(minutes=30)
LISTENER_RESTART_ISSUE_THRESHOLD = 5
LISTENER_ISSUE_ID = "event_listener_stopped"


@dataclass
class RingData:
    """Class to support type hinting of ring data collection."""

    api: Ring
    devices: RingDevices
    devices_coordinator: RingDataCoordinator
    listen_coordinator: RingListenCoordinator


type RingConfigEntry = ConfigEntry[RingData]


class RingDataCoordinator(DataUpdateCoordinator[RingDevices]):
    """Base class for device coordinators."""

    config_entry: RingConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RingConfigEntry,
        ring_api: Ring,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            name="devices",
            logger=_LOGGER,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.ring_api: Ring = ring_api
        self.first_call: bool = True

    async def _call_api[*_Ts, _R](
        self,
        target: Callable[[*_Ts], Coroutine[Any, Any, _R]],
        *args: *_Ts,
    ) -> _R:
        try:
            return await target(*args)
        except AuthenticationError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="api_authentication",
            ) from err
        except RingTimeout as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_timeout",
            ) from err
        except RingError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err

    @override
    async def _async_update_data(self) -> RingDevices:
        """Fetch data from API endpoint."""
        update_method: str = (
            "async_update_data" if self.first_call else "async_update_devices"
        )
        await self._call_api(getattr(self.ring_api, update_method))
        self.first_call = False
        devices: RingDevices = self.ring_api.devices()
        subscribed_device_ids = set(self.async_contexts())
        for device in devices.all_devices:
            # Don't update all devices in the ring api, only those that set
            # their device id as context when they subscribed.
            if device.id in subscribed_device_ids:
                try:
                    async with TaskGroup() as tg:
                        if device.has_capability("history"):
                            tg.create_task(
                                self._call_api(
                                    lambda device: device.async_history(limit=10),
                                    device,
                                )
                            )
                        tg.create_task(
                            self._call_api(
                                device.async_update_health_data,
                            )
                        )
                except ExceptionGroup as eg:
                    raise eg.exceptions[0]  # noqa: B904

        return devices


class RingListenCoordinator(BaseDataUpdateCoordinatorProtocol):
    """Global notifications coordinator."""

    config_entry: RingConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RingConfigEntry,
        ring_api: Ring,
        listen_credentials: dict[str, Any] | None,
        listen_credentials_updater: Callable[[dict[str, Any]], None],
    ) -> None:
        """Initialize my coordinator."""
        self.hass = hass
        self.logger = _LOGGER
        self.ring_api: Ring = ring_api
        self._listen_credentials_updater = listen_credentials_updater
        self.event_listener = RingEventListener(
            ring_api, listen_credentials, listen_credentials_updater
        )
        self._listeners: dict[CALLBACK_TYPE, tuple[CALLBACK_TYPE, object | None]] = {}
        self._listen_callback_id: int | None = None
        self._unsub_listener_check: CALLBACK_TYPE | None = None
        self._failed_restarts = 0
        self._next_restart: datetime | None = None
        self._restarting = False

        self.config_entry = config_entry
        self.start_timeout = 10
        self.config_entry.async_on_unload(self.async_shutdown)
        self.index_alerts()

    def index_alerts(self) -> None:
        "Index the active alerts."
        self.alerts = {
            (alert.doorbot_id, alert.kind): alert
            for alert in self.ring_api.active_alerts()
        }

    async def async_shutdown(self) -> None:
        """Cancel any scheduled call, and ignore new runs."""
        if self.event_listener.started:
            await self._async_stop_listen()
        ir.async_delete_issue(self.hass, DOMAIN, LISTENER_ISSUE_ID)

    async def _async_stop_listen(self) -> None:
        self.logger.debug("Stopped ring listener")
        if self._unsub_listener_check:
            self._unsub_listener_check()
            self._unsub_listener_check = None
        await self.event_listener.stop()
        self.logger.debug("Stopped ring listener")

    async def _async_start_listen(self) -> None:
        """Start listening for realtime events."""
        self.logger.debug("Starting ring listener.")
        await self.event_listener.start(
            timeout=self.start_timeout,
        )
        if self.event_listener.started is True:
            self.logger.debug("Started ring listener")
        else:
            self.logger.warning(
                "Ring event listener failed to start after %s seconds",
                self.start_timeout,
            )
        self._listen_callback_id = self.event_listener.add_notification_callback(
            self._on_event
        )
        self.index_alerts()
        # Update the listeners so they switch from Unavailable to Unknown
        self._async_update_listeners()
        if self._unsub_listener_check is None and self._listeners:
            self._unsub_listener_check = async_track_time_interval(
                self.hass,
                self._async_check_listener,
                LISTENER_CHECK_INTERVAL,
                name="Ring event listener check",
                cancel_on_shutdown=True,
            )

    async def _async_check_listener(self, now: datetime) -> None:
        """Restart the event listener if it has stopped receiving events."""
        if self.event_listener.started or self._restarting:
            return
        if self._next_restart and now < self._next_restart:
            return

        self.logger.info("Ring event listener is not running, restarting it")
        # Make the event entities unavailable while restarting.
        self._async_update_listeners()
        self._restarting = True
        try:
            await self.event_listener.stop()
            self.event_listener = RingEventListener(
                self.ring_api,
                self.config_entry.data.get(CONF_LISTEN_CREDENTIALS),
                self._listen_credentials_updater,
            )
            await self._async_start_listen()
        finally:
            self._restarting = False

        if self.event_listener.started:
            self._failed_restarts = 0
            self._next_restart = None
            ir.async_delete_issue(self.hass, DOMAIN, LISTENER_ISSUE_ID)
            return

        self._failed_restarts += 1
        self._next_restart = now + min(
            LISTENER_CHECK_INTERVAL * 2**self._failed_restarts,
            LISTENER_MAX_RESTART_DELAY,
        )
        if self._failed_restarts >= LISTENER_RESTART_ISSUE_THRESHOLD:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                LISTENER_ISSUE_ID,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=LISTENER_ISSUE_ID,
            )

    def _on_event(self, event: RingEvent) -> None:
        self.logger.debug("Ring event received: %s", event)
        self.index_alerts()
        self._async_update_listeners(event.doorbot_id)

    @callback
    def _async_update_listeners(self, doorbot_id: int | None = None) -> None:
        """Update all registered listeners."""
        for update_callback, device_api_id in list(self._listeners.values()):
            if not doorbot_id or device_api_id == doorbot_id:
                update_callback()

    @callback
    @override
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        """Listen for data updates."""
        start_listen = not self._listeners

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self._listeners.pop(remove_listener)
            if not self._listeners:
                self.config_entry.async_create_task(
                    self.hass,
                    self._async_stop_listen(),
                    "Ring event listener stop",
                    eager_start=True,
                )

        self._listeners[remove_listener] = (update_callback, context)

        # This is the first listener, start the event listener.
        if start_listen:
            self.config_entry.async_create_task(
                self.hass,
                self._async_start_listen(),
                "Ring event listener start",
                eager_start=True,
            )
        return remove_listener
