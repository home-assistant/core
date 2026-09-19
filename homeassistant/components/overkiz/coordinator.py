"""Helpers to help coordinate updates."""

from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
import time
from typing import TYPE_CHECKING, Any, override

from aiohttp import ClientConnectorError, ClientError, ServerDisconnectedError
from pyoverkiz.client import OverkizClient
from pyoverkiz.enums import EventName, ExecutionState, Protocol
from pyoverkiz.exceptions import (
    BadCredentialsError,
    InvalidEventListenerIdError,
    MaintenanceError,
    NotAuthenticatedError,
    OverkizError,
    ServiceUnavailableError,
    TooManyConcurrentRequestsError,
    TooManyRequestsError,
)
from pyoverkiz.models import (
    Device,
    DeviceEvent,
    DeviceRemovedEvent,
    DeviceStateChangedEvent,
    ExecutionRegisteredEvent,
    ExecutionStateChangedEvent,
    Place,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
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
    EXECUTION_TTL,
    IGNORED_OVERKIZ_DEVICES,
    LOGGER,
    UPDATE_INTERVAL,
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
        self.executions: dict[str, list[dict[str, str]]] = {}
        self._executions_registered_at: dict[str, float] = {}
        self._execution_ttl: float = EXECUTION_TTL
        self._need_full_resync: bool = False
        self.areas = self._places_to_area(places) if places else None
        self._default_update_interval = UPDATE_INTERVAL

        self.is_stateless = all(
            device.identifier.protocol in (Protocol.RTS, Protocol.INTERNAL)
            for device in devices
            if device.widget not in IGNORED_OVERKIZ_DEVICES
            and device.ui_class not in IGNORED_OVERKIZ_DEVICES
        )

    def _handle_error_reset(self) -> None:
        """Reset execution state and restore update interval on error."""
        self.executions.clear()
        self._executions_registered_at.clear()
        self.update_interval = self._default_update_interval

    def track_execution(self, exec_id: str) -> None:
        """Track execution registration timestamp."""
        if exec_id not in self.executions:
            self.executions[exec_id] = []
        self._executions_registered_at.setdefault(exec_id, time.monotonic())

    def untrack_execution(self, exec_id: str) -> None:
        """Remove tracked execution."""
        self.executions.pop(exec_id, None)
        self._executions_registered_at.pop(exec_id, None)

    def _cleanup_stale_executions(self) -> None:
        """Clean up executions that have exceeded their TTL."""
        now = time.monotonic()
        stale_exec_ids = [
            exec_id
            for exec_id, reg_time in self._executions_registered_at.items()
            if now - reg_time > self._execution_ttl
        ]
        for exec_id in stale_exec_ids:
            LOGGER.debug("Cleaning up stale execution %s", exec_id)
            self.executions.pop(exec_id, None)
            self._executions_registered_at.pop(exec_id, None)

        # Track timestamp for any execution added without a timestamp
        for exec_id in list(self.executions):
            if exec_id not in self._executions_registered_at:
                self._executions_registered_at[exec_id] = now

    @override
    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch Overkiz data via event listener."""
        # Resynchronize full device state if connection was dropped or listener was invalidated
        if self._need_full_resync:
            try:
                self.devices = await self._get_devices()
            except (BadCredentialsError, OAuth2TokenRequestReauthError) as exception:
                self._handle_error_reset()
                raise ConfigEntryAuthFailed("Invalid authentication.") from exception
            except (
                NotAuthenticatedError,
                OAuth2TokenRequestError,
                TooManyConcurrentRequestsError,
                TooManyRequestsError,
                MaintenanceError,
                ServiceUnavailableError,
                TimeoutError,
                ClientError,
                OverkizError,
            ) as exception:
                LOGGER.debug("Failed to fetch devices during resync", exc_info=True)
                self._handle_error_reset()
                raise UpdateFailed(
                    f"Failed to resync devices: {exception}"
                ) from exception
            else:
                self._need_full_resync = False

        try:
            events = await self.client.fetch_events()
        except (
            BadCredentialsError,
            OAuth2TokenRequestReauthError,
        ) as exception:
            self._handle_error_reset()
            raise ConfigEntryAuthFailed("Invalid authentication.") from exception
        except NotAuthenticatedError:
            self._handle_error_reset()
            self._need_full_resync = True
            try:
                await self.client.login()
                self.devices = await self._get_devices()
            except (BadCredentialsError, OAuth2TokenRequestReauthError) as exception:
                raise ConfigEntryAuthFailed("Invalid authentication.") from exception
            except (
                NotAuthenticatedError,
                OAuth2TokenRequestError,
                TooManyConcurrentRequestsError,
                TooManyRequestsError,
                MaintenanceError,
                ServiceUnavailableError,
                TimeoutError,
                ClientError,
                OverkizError,
            ) as exception:
                LOGGER.debug(
                    "Failed to relogin after session expiration", exc_info=True
                )
                raise UpdateFailed(
                    f"Failed to re-authenticate: {exception}"
                ) from exception
            else:
                self._need_full_resync = False
                return self.devices
        except OAuth2TokenRequestError as exception:
            self._handle_error_reset()
            raise UpdateFailed("Failed to refresh OAuth2 token.") from exception
        except TooManyConcurrentRequestsError as exception:
            self._handle_error_reset()
            raise UpdateFailed("Too many concurrent requests.") from exception
        except TooManyRequestsError as exception:
            self._handle_error_reset()
            raise UpdateFailed("Too many requests, try again later.") from exception
        except MaintenanceError as exception:
            self._handle_error_reset()
            raise UpdateFailed("Server is down for maintenance.") from exception
        except ServiceUnavailableError as exception:
            self._handle_error_reset()
            raise UpdateFailed("Server is unavailable.") from exception
        except InvalidEventListenerIdError as exception:
            self._handle_error_reset()
            self._need_full_resync = True
            raise UpdateFailed(str(exception)) from exception
        except (TimeoutError, ClientConnectorError) as exception:
            LOGGER.debug("Failed to connect", exc_info=True)
            self._handle_error_reset()
            self._need_full_resync = True
            raise UpdateFailed("Failed to connect.") from exception
        except ServerDisconnectedError:
            LOGGER.debug("Server disconnected, attempting reconnection", exc_info=True)
            self._handle_error_reset()
            self._need_full_resync = True

            try:
                await self.client.login()
                self.devices = await self._get_devices()
            except (BadCredentialsError, OAuth2TokenRequestReauthError) as exception:
                raise ConfigEntryAuthFailed("Invalid authentication.") from exception
            except (
                NotAuthenticatedError,
                OAuth2TokenRequestError,
                TooManyConcurrentRequestsError,
                TooManyRequestsError,
                MaintenanceError,
                ServiceUnavailableError,
                TimeoutError,
                ClientError,
                OverkizError,
            ) as exception:
                LOGGER.debug(
                    "Failed to reconnect after server disconnect", exc_info=True
                )
                raise UpdateFailed(f"Failed to reconnect: {exception}") from exception
            else:
                self._need_full_resync = False
                return self.devices
        except (ClientError, OverkizError) as exception:
            LOGGER.debug("Overkiz / transport error", exc_info=True)
            self._handle_error_reset()
            self._need_full_resync = True
            raise UpdateFailed(
                f"Error fetching Overkiz data: {exception}"
            ) from exception

        for event in events:
            LOGGER.debug(event)

            if event_handler := EVENT_HANDLERS.get(event.name):
                await event_handler(self, event)

        # Clean up stale executions and restore update interval if no executions are pending
        self._cleanup_stale_executions()
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
    coordinator.track_execution(event.exec_id)

    if not coordinator.is_stateless:
        coordinator.update_interval = timedelta(seconds=1)


@EVENT_HANDLERS.register(EventName.EXECUTION_STATE_CHANGED)
async def on_execution_state_changed(
    coordinator: OverkizDataUpdateCoordinator, event: ExecutionStateChangedEvent
) -> None:
    """Handle execution changed event."""
    if event.exec_id in coordinator.executions and event.new_state in [
        ExecutionState.COMPLETED,
        ExecutionState.FAILED,
    ]:
        coordinator.untrack_execution(event.exec_id)
