"""Helpers to help coordinate updates."""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from time import monotonic
from typing import TYPE_CHECKING, Any, override

from aiohttp import ClientConnectorError, ServerDisconnectedError
from pyoverkiz.client import OverkizClient
from pyoverkiz.enums import EventName, ExecutionState, Protocol
from pyoverkiz.exceptions import (
    BadCredentialsError,
    InvalidEventListenerIdError,
    MaintenanceError,
    NotAuthenticatedError,
    ServiceUnavailableError,
    SomfyServiceError,
    TooManyConcurrentRequestsError,
    TooManyRequestsError,
)
from pyoverkiz.models import (
    Action,
    Command,
    Device,
    DeviceEvent,
    DeviceRemovedEvent,
    DeviceStateChangedEvent,
    ExecutionRegisteredEvent,
    ExecutionStateChangedEvent,
    Place,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.decorator import Registry

if TYPE_CHECKING:
    from . import OverkizDataConfigEntry

from .const import (
    DOMAIN,
    IGNORED_OVERKIZ_DEVICES,
    LOGGER,
    MIN_WRITE_INTERVAL,
    RATE_LIMIT_RETRY_AFTER,
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_EXECUTION,
)

# Events are a discriminated union; each handler narrows to its own subtype.
EVENT_HANDLERS: Registry[
    str, Callable[[OverkizDataUpdateCoordinator, Any], Coroutine[Any, Any, None]]
] = Registry()


class OverkizDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Class to manage fetching data from Overkiz platform."""

    config_entry: OverkizDataConfigEntry
    _default_update_interval: timedelta

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OverkizDataConfigEntry,
        logger: logging.Logger,
        *,
        client: OverkizClient,
        devices: list[Device],
        places: Place | None,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name="device events",
            update_interval=UPDATE_INTERVAL,
        )

        self.data = {}
        self.client = client
        self.devices: dict[str, Device] = {d.device_url: d for d in devices}
        self.executions: dict[str, list[dict[str, Any]]] = {}
        # Commands waiting for the running write of the same settings to end.
        self.pending_commands: dict[tuple[str, tuple[str, ...]], list[Command]] = {}
        # Writes that wait their turn, not yet registered as executions.
        self.writes_waiting: set[tuple[str, tuple[str, ...]]] = set()
        self._write_lock = asyncio.Lock()
        self._last_write_at: float | None = None
        # Once the config entry unloads, nothing deferred is sent any more.
        self._shutting_down = False
        self.areas = self._places_to_area(places) if places else None
        self._default_update_interval = UPDATE_INTERVAL

        self.is_stateless = all(
            device.identifier.protocol in (Protocol.RTS, Protocol.INTERNAL)
            for device in devices
            if device.widget not in IGNORED_OVERKIZ_DEVICES
            and device.ui_class not in IGNORED_OVERKIZ_DEVICES
        )

    @override
    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch Overkiz data via event listener."""
        try:
            events = await self.client.fetch_events()
        except (
            BadCredentialsError,
            NotAuthenticatedError,
            OAuth2TokenRequestReauthError,
        ) as exception:
            raise ConfigEntryAuthFailed("Invalid authentication.") from exception
        except OAuth2TokenRequestError as exception:
            raise UpdateFailed("Failed to refresh OAuth2 token.") from exception
        except TooManyConcurrentRequestsError as exception:
            raise UpdateFailed("Too many concurrent requests.") from exception
        except TooManyRequestsError as exception:
            raise UpdateFailed(
                "Too many requests, try again later.",
                retry_after=RATE_LIMIT_RETRY_AFTER.total_seconds(),
            ) from exception
        except MaintenanceError as exception:
            raise UpdateFailed("Server is down for maintenance.") from exception
        except ServiceUnavailableError as exception:
            raise UpdateFailed("Server is unavailable.") from exception
        except SomfyServiceError as exception:
            raise UpdateFailed("Somfy service error.") from exception
        except InvalidEventListenerIdError as exception:
            raise UpdateFailed(exception) from exception
        except (TimeoutError, ClientConnectorError) as exception:
            LOGGER.debug("Failed to connect", exc_info=True)
            raise UpdateFailed("Failed to connect.") from exception
        except ServerDisconnectedError:
            self.executions = {}

            # During the relogin, similar exceptions can be thrown.
            try:
                await self.client.login()
                self.devices = await self._get_devices()
            except (BadCredentialsError, NotAuthenticatedError) as exception:
                raise ConfigEntryAuthFailed("Invalid authentication.") from exception
            except TooManyRequestsError as exception:
                raise UpdateFailed("Too many requests, try again later.") from exception

            # What waited for a running write, which is forgotten now, is sent.
            for key in list(self.pending_commands):
                self.async_create_write_task(_send_pending_commands(self, key))

            return self.devices

        for event in events:
            LOGGER.debug(event)

            if event_handler := EVENT_HANDLERS.get(event.name):
                await event_handler(self, event)

        # Restore the default update interval if no executions are pending
        if not self.executions:
            self.update_interval = self._default_update_interval

        return self.devices

    async def _get_devices(self) -> dict[str, Device]:
        """Fetch devices."""
        LOGGER.debug("Fetching all devices and state via /setup/devices")
        return {d.device_url: d for d in await self.client.get_devices(refresh=True)}

    def _places_to_area(self, place: Place) -> dict[str, str]:
        """Convert places with sub_places to a flat dictionary [placeoid, label])."""
        areas = {}
        if isinstance(place, Place):
            areas[place.oid] = place.label

        if isinstance(place.sub_places, list):
            for sub_place in place.sub_places:
                areas.update(self._places_to_area(sub_place))

        return areas

    async def async_execute_throttled(self, actions: list[Action]) -> str:
        """Execute actions, at least MIN_WRITE_INTERVAL after the previous write."""
        async with self._write_lock:
            if (
                self._last_write_at is not None
                and (
                    wait := MIN_WRITE_INTERVAL.total_seconds()
                    - (monotonic() - self._last_write_at)
                )
                > 0
            ):
                await asyncio.sleep(wait)

            try:
                return await self.client.execute_action_group(
                    label="Home Assistant", actions=actions
                )
            finally:
                self._last_write_at = monotonic()

    def is_execution_running(self, key: tuple[str, tuple[str, ...]]) -> bool:
        """Return whether a write of the same settings waits or runs."""
        return key in self.writes_waiting or any(
            record.get("key") == key and monotonic() - record["started"] < 60
            for records in self.executions.values()
            for record in records
        )

    def is_same_as_running(
        self, key: tuple[str, tuple[str, ...]], commands: list[Command]
    ) -> bool:
        """Return whether the last running write of these settings has these values."""
        running = [
            record
            for records in self.executions.values()
            for record in records
            if record.get("key") == key and monotonic() - record["started"] < 60
        ]
        if not running or not (sent := running[-1].get("commands")):
            return False

        def values(commands: list[Command]) -> list[tuple[str, tuple[Any, ...]]]:
            return [
                (str(command.name), tuple(command.parameters or ()))
                for command in commands
                if not str(command.name).startswith("refresh")
            ]

        return values(sent) == values(commands)

    def discard_pending_commands(
        self, device_url: str, command_names: set[str]
    ) -> None:
        """Forget the writes of these commands that wait for a device."""
        for key in [
            key
            for key in self.pending_commands
            if key[0] == device_url and command_names.intersection(key[1])
        ]:
            del self.pending_commands[key]

    @callback
    def async_create_write_task(self, target: Coroutine[Any, Any, None]) -> None:
        """Run a deferred write, canceled when the config entry is unloaded."""
        if self._shutting_down:
            target.close()
            return
        self.config_entry.async_create_background_task(
            self.hass, target, "overkiz deferred write"
        )

    @callback
    def async_send_pending_commands(self, key: tuple[str, tuple[str, ...]]) -> None:
        """Send what waits for a write of these settings, if anything."""
        if key in self.pending_commands:
            self.async_create_write_task(_send_pending_commands(self, key))

    @override
    async def async_shutdown(self) -> None:
        """Forget the writes still waiting, then shut down."""
        self._shutting_down = True
        self.pending_commands.clear()
        await super().async_shutdown()

    @callback
    def async_execution_started(self) -> None:
        """Show the in-progress state and poll fast until executions finish."""
        self.async_update_listeners()
        if not self.is_stateless and self.update_interval != UPDATE_INTERVAL_EXECUTION:
            self.update_interval = UPDATE_INTERVAL_EXECUTION
            self._schedule_refresh()

    def set_update_interval(self, update_interval: timedelta) -> None:
        """Set the update interval and store this value."""
        self.update_interval = update_interval
        self._default_update_interval = update_interval


@EVENT_HANDLERS.register(EventName.DEVICE_AVAILABLE)
async def on_device_available(
    coordinator: OverkizDataUpdateCoordinator, event: DeviceEvent
) -> None:
    """Handle device available event."""
    if event.device_url in coordinator.devices:
        coordinator.devices[event.device_url].available = True


@EVENT_HANDLERS.register(EventName.DEVICE_UNAVAILABLE)
@EVENT_HANDLERS.register(EventName.DEVICE_DISABLED)
async def on_device_unavailable_disabled(
    coordinator: OverkizDataUpdateCoordinator, event: DeviceEvent
) -> None:
    """Handle device unavailable / disabled event."""
    if event.device_url in coordinator.devices:
        coordinator.devices[event.device_url].available = False


@EVENT_HANDLERS.register(EventName.DEVICE_CREATED)
@EVENT_HANDLERS.register(EventName.DEVICE_UPDATED)
async def on_device_created_updated(
    coordinator: OverkizDataUpdateCoordinator, event: DeviceEvent
) -> None:
    """Handle device unavailable / disabled event."""
    coordinator.hass.async_create_task(
        coordinator.hass.config_entries.async_reload(coordinator.config_entry.entry_id)
    )


@EVENT_HANDLERS.register(EventName.DEVICE_STATE_CHANGED)
async def on_device_state_changed(
    coordinator: OverkizDataUpdateCoordinator, event: DeviceStateChangedEvent
) -> None:
    """Handle device state changed event."""
    if event.device_url not in coordinator.devices:
        return

    for state in event.device_states:
        device = coordinator.devices[event.device_url]
        device.states[state.name] = state


@EVENT_HANDLERS.register(EventName.DEVICE_REMOVED)
async def on_device_removed(
    coordinator: OverkizDataUpdateCoordinator, event: DeviceRemovedEvent
) -> None:
    """Handle device removed event."""
    base_device_url = event.device_url.split("#")[0]
    registry = dr.async_get(coordinator.hass)

    if registered_device := registry.async_get_device_by_identifier(
        (DOMAIN, base_device_url), coordinator.config_entry.entry_id
    ):
        registry.async_remove_device(registered_device.id)

    if event.device_url in coordinator.devices:
        del coordinator.devices[event.device_url]


@EVENT_HANDLERS.register(EventName.EXECUTION_REGISTERED)
async def on_execution_registered(
    coordinator: OverkizDataUpdateCoordinator, event: ExecutionRegisteredEvent
) -> None:
    """Handle execution registered event."""
    if event.exec_id not in coordinator.executions:
        coordinator.executions[event.exec_id] = []

    if not coordinator.is_stateless:
        coordinator.update_interval = UPDATE_INTERVAL_EXECUTION


@EVENT_HANDLERS.register(EventName.EXECUTION_STATE_CHANGED)
async def on_execution_state_changed(
    coordinator: OverkizDataUpdateCoordinator, event: ExecutionStateChangedEvent
) -> None:
    """Handle execution changed event."""
    if event.new_state not in (ExecutionState.COMPLETED, ExecutionState.FAILED):
        return

    # The write is over: what waited for it is sent now.
    for record in coordinator.executions.pop(event.exec_id, None) or ():
        if (key := record.get("key")) is not None:
            coordinator.async_send_pending_commands(key)


async def _send_pending_commands(
    coordinator: OverkizDataUpdateCoordinator,
    key: tuple[str, tuple[str, ...]],
) -> None:
    """Send the commands that waited for the write of the same settings."""
    if (commands := coordinator.pending_commands.pop(key, None)) is None:
        return

    # Local import: the executor imports this module.
    from .executor import OverkizExecutor  # noqa: PLC0415

    try:
        await OverkizExecutor(key[0], coordinator).async_execute_commands(
            commands, coalesce=True
        )
    except HomeAssistantError:
        # The service call that gave these commands returned long ago.
        LOGGER.warning("Sending the waiting Overkiz commands failed", exc_info=True)
