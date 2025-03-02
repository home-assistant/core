"""Data coordinators for the ring integration."""

from __future__ import annotations

from asyncio import TaskGroup
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

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
from homeassistant.helpers.update_coordinator import (
    BaseDataUpdateCoordinatorProtocol,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


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
        self.event_listener = RingEventListener(
            ring_api, listen_credentials, listen_credentials_updater
        )
        self._listeners: dict[CALLBACK_TYPE, tuple[CALLBACK_TYPE, object | None]] = {}
        self._listen_callback_id: int | None = None

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

    async def _async_stop_listen(self) -> None:
        self.logger.debug("Stopped ring listener")
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
