"""Helpers to help coordinate updates."""

from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from aiohttp import ClientConnectorError, ServerDisconnectedError
from pyoverkiz.client import OverkizClient
from pyoverkiz.enums import EventName, ExecutionState, FailureType, Protocol
from pyoverkiz.exceptions import (
    BadCredentialsError,
    InvalidEventListenerIdError,
    MaintenanceError,
    NotAuthenticatedError,
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
    Gateway,
    GatewayEvent,
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
    IGNORED_OVERKIZ_DEVICES,
    LOGGER,
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_EXECUTION,
    UPDATE_INTERVAL_RATE_LIMITED_MAX,
)

# A command can fail because the device refused it (a priority lock, an open
# door) or because the gateway never reached it. Only the latter says anything
# about availability; the rest leave a reachable device reachable.
UNREACHABLE_FAILURE_TYPES = {
    FailureType.ACTUATORNOANSWER,
    FailureType.ACTUATORUNKNOWN,
    FailureType.ADDRESS_UNKNOWN,
    FailureType.PEER_DOWN,
    FailureType.TIME_OUT_ON_COMMAND_PROGRESS,
    FailureType.TIME_OUT_ON_TRANSMIT,
    FailureType.TIME_OUT_ON_TRANSMITTED_COMMAND,
}

# Events are a discriminated union; each handler narrows to its own subtype.
EVENT_HANDLERS: Registry[
    str, Callable[[OverkizDataUpdateCoordinator, Any], Coroutine[Any, Any, None]]
] = Registry()


class OverkizDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Class to manage fetching data from Overkiz platform."""

    config_entry: OverkizDataConfigEntry
    _default_update_interval: timedelta
    _rate_limited_interval: timedelta | None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OverkizDataConfigEntry,
        logger: logging.Logger,
        *,
        client: OverkizClient,
        devices: list[Device],
        gateways: list[Gateway],
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
        # A gateway reports its devices' states from cache while it is
        # unreachable, so nothing in the device payload reveals the outage.
        self.unreachable_gateways: set[str] = {
            gateway.gateway_id for gateway in gateways if gateway.alive is False
        }
        # Kept apart from Device.available so recovery only ever clears what
        # this integration inferred, never what the server reported.
        self.unreachable_devices: set[str] = set()
        self.areas = self._places_to_area(places) if places else None
        self._default_update_interval = UPDATE_INTERVAL
        self._rate_limited_interval = None

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
            self._back_off()
            raise UpdateFailed("Too many requests, try again later.") from exception
        except MaintenanceError as exception:
            raise UpdateFailed("Server is down for maintenance.") from exception
        except ServiceUnavailableError as exception:
            raise UpdateFailed("Server is unavailable.") from exception
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
                self._back_off()
                raise UpdateFailed("Too many requests, try again later.") from exception

            self._on_successful_update()

            return self.devices

        for event in events:
            LOGGER.debug(event)

            if event_handler := EVENT_HANDLERS.get(event.name):
                await event_handler(self, event)

        self._on_successful_update()

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

    def _on_successful_update(self) -> None:
        """Clear the rate limit back off and restore the polling cadence.

        Every path that returns data has to go through this, including the
        reconnect after a ServerDisconnectedError.
        """
        self._rate_limited_interval = None

        if self.executions and not self.is_stateless:
            self.update_interval = UPDATE_INTERVAL_EXECUTION
        else:
            self.update_interval = self._default_update_interval

    def _back_off(self) -> None:
        """Poll less often while the server is rate limiting us.

        DataUpdateCoordinator otherwise retries at the unchanged interval.
        """
        # An all-assumed-state hub already polls hourly, so the cap has to
        # respect the configured interval or backing off would speed it up.
        maximum = max(UPDATE_INTERVAL_RATE_LIMITED_MAX, self._default_update_interval)
        previous = self._rate_limited_interval or self._default_update_interval
        self._rate_limited_interval = min(previous * 2, maximum)
        self.update_interval = self._rate_limited_interval

    def set_update_interval(self, update_interval: timedelta) -> None:
        """Set the update interval and store this value."""
        self.update_interval = update_interval
        self._default_update_interval = update_interval


@EVENT_HANDLERS.register(EventName.GATEWAY_DOWN)
async def on_gateway_down(
    coordinator: OverkizDataUpdateCoordinator, event: GatewayEvent
) -> None:
    """Handle gateway down event."""
    coordinator.unreachable_gateways.add(event.gateway_id)


@EVENT_HANDLERS.register(EventName.GATEWAY_ALIVE)
async def on_gateway_alive(
    coordinator: OverkizDataUpdateCoordinator, event: GatewayEvent
) -> None:
    """Handle gateway alive event."""
    coordinator.unreachable_gateways.discard(event.gateway_id)


@EVENT_HANDLERS.register(EventName.DEVICE_AVAILABLE)
async def on_device_available(
    coordinator: OverkizDataUpdateCoordinator, event: DeviceEvent
) -> None:
    """Handle device available event."""
    coordinator.unreachable_devices.discard(event.device_url)

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

    # A state coming from the device is proof it is reachable again, and that
    # its gateway carried it. GATEWAY_ALIVE is otherwise the only way out of
    # unreachable_gateways, so a missed one would strand every entity on it.
    coordinator.unreachable_devices.discard(event.device_url)
    coordinator.unreachable_gateways.discard(
        coordinator.devices[event.device_url].identifier.gateway_id
    )

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


@EVENT_HANDLERS.register(EventName.EXECUTION_STATE_CHANGED)
async def on_execution_state_changed(
    coordinator: OverkizDataUpdateCoordinator, event: ExecutionStateChangedEvent
) -> None:
    """Handle execution changed event."""
    if event.exec_id not in coordinator.executions or event.new_state not in [
        ExecutionState.COMPLETED,
        ExecutionState.FAILED,
    ]:
        return

    executions = coordinator.executions.pop(event.exec_id)
    device_urls = {execution["device_url"] for execution in executions}

    # The only place an unreachable device is reported. The server keeps
    # answering for it and DeviceUnavailableEvent never fires, so without this
    # the entity stays available and every command is silently dropped.
    # The action queue merges concurrent action groups into one execution, and
    # the failure it reports is execution-wide: nothing says which of the
    # devices answered and which did not. Only a completion speaks for all of
    # them, so leave a merged failure alone in either direction.
    if event.new_state is ExecutionState.FAILED and len(device_urls) > 1:
        return

    unreachable = (
        event.new_state is ExecutionState.FAILED
        and event.failure_type_code in UNREACHABLE_FAILURE_TYPES
    )

    for device_url in device_urls:
        if not unreachable:
            coordinator.unreachable_devices.discard(device_url)
        # A one-way protocol cannot acknowledge, so a failure there says
        # nothing about whether the device is reachable.
        elif (device := coordinator.devices.get(device_url)) and (
            device.identifier.protocol is not Protocol.RTS
        ):
            LOGGER.debug("Device %s is unreachable: %s", device_url, event.failure_type)
            coordinator.unreachable_devices.add(device_url)
