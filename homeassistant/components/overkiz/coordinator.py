"""Helpers to help coordinate updates."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientConnectorError, ServerDisconnectedError
from pyoverkiz.client import OverkizClient
from pyoverkiz.enums import EventName, ExecutionState, Protocol
from pyoverkiz.exceptions import (
    BadCredentialsException,
    InvalidEventListenerIdException,
    MaintenanceException,
    NotAuthenticatedException,
    TooManyConcurrentRequestsException,
    TooManyRequestsException,
)
from pyoverkiz.models import Device, Event, Place

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.decorator import Registry

from .const import DOMAIN, IGNORED_OVERKIZ_DEVICES, LOGGER

EVENT_HANDLERS: Registry[
    str, Callable[[OverkizDataUpdateCoordinator, Event], Coroutine[Any, Any, None]]
] = Registry()


class OverkizDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Class to manage fetching data from Overkiz platform."""

    _default_update_interval: timedelta

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        name: str,
        client: OverkizClient,
        devices: list[Device],
        places: Place | None,
        update_interval: timedelta,
        config_entry_id: str,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=update_interval,
        )

        self.data = {}
        self.client = client
        self.devices: dict[str, Device] = {d.device_url: d for d in devices}
        self.executions: dict[str, dict[str, str]] = {}
        self.areas = self._places_to_area(places) if places else None
        self.config_entry_id = config_entry_id
        self._default_update_interval = update_interval

        self.is_stateless = all(
            device.protocol in (Protocol.RTS, Protocol.INTERNAL)
            for device in devices
            if device.widget not in IGNORED_OVERKIZ_DEVICES
            and device.ui_class not in IGNORED_OVERKIZ_DEVICES
        )

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch Overkiz data via event listener."""
        try:
            events = await self.client.fetch_events()
        except BadCredentialsException as exception:
            raise ConfigEntryAuthFailed("Invalid authentication.") from exception
        except TooManyConcurrentRequestsException as exception:
            raise UpdateFailed("Too many concurrent requests.") from exception
        except TooManyRequestsException as exception:
            raise UpdateFailed("Too many requests, try again later.") from exception
        except MaintenanceException as exception:
            raise UpdateFailed("Server is down for maintenance.") from exception
        except InvalidEventListenerIdException as exception:
            raise UpdateFailed(exception) from exception
        except (TimeoutError, ClientConnectorError) as exception:
            raise UpdateFailed("Failed to connect.") from exception
        except (ServerDisconnectedError, NotAuthenticatedException):
            self.executions = {}

            # During the relogin, similar exceptions can be thrown.
            try:
                await self.client.login()
                self.devices = await self._get_devices()
            except BadCredentialsException as exception:
                raise ConfigEntryAuthFailed("Invalid authentication.") from exception
            except TooManyRequestsException as exception:
                raise UpdateFailed("Too many requests, try again later.") from exception

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

    def set_update_interval(self, update_interval: timedelta) -> None:
        """Set the update interval and store this value."""
        self.update_interval = update_interval
        self._default_update_interval = update_interval


@EVENT_HANDLERS.register(EventName.DEVICE_AVAILABLE)
async def on_device_available(
    coordinator: OverkizDataUpdateCoordinator, event: Event
) -> None:
    """Handle device available event."""
    if event.device_url:
        coordinator.devices[event.device_url].available = True


@EVENT_HANDLERS.register(EventName.DEVICE_UNAVAILABLE)
@EVENT_HANDLERS.register(EventName.DEVICE_DISABLED)
async def on_device_unavailable_disabled(
    coordinator: OverkizDataUpdateCoordinator, event: Event
) -> None:
    """Handle device unavailable / disabled event."""
    if event.device_url:
        coordinator.devices[event.device_url].available = False


@EVENT_HANDLERS.register(EventName.DEVICE_CREATED)
@EVENT_HANDLERS.register(EventName.DEVICE_UPDATED)
async def on_device_created_updated(
    coordinator: OverkizDataUpdateCoordinator, event: Event
) -> None:
    """Handle device unavailable / disabled event."""
    coordinator.hass.async_create_task(
        coordinator.hass.config_entries.async_reload(coordinator.config_entry_id)
    )


@EVENT_HANDLERS.register(EventName.DEVICE_STATE_CHANGED)
async def on_device_state_changed(
    coordinator: OverkizDataUpdateCoordinator, event: Event
) -> None:
    """Handle device state changed event."""
    if not event.device_url:
        return

    for state in event.device_states:
        device = coordinator.devices[event.device_url]
        device.states[state.name] = state


@EVENT_HANDLERS.register(EventName.DEVICE_REMOVED)
async def on_device_removed(
    coordinator: OverkizDataUpdateCoordinator, event: Event
) -> None:
    """Handle device removed event."""
    if not event.device_url:
        return

    base_device_url = event.device_url.split("#")[0]
    registry = dr.async_get(coordinator.hass)

    if registered_device := registry.async_get_device(
        identifiers={(DOMAIN, base_device_url)}
    ):
        registry.async_remove_device(registered_device.id)

    if event.device_url:
        del coordinator.devices[event.device_url]


@EVENT_HANDLERS.register(EventName.EXECUTION_REGISTERED)
async def on_execution_registered(
    coordinator: OverkizDataUpdateCoordinator, event: Event
) -> None:
    """Handle execution registered event."""
    if event.exec_id and event.exec_id not in coordinator.executions:
        coordinator.executions[event.exec_id] = {}

    if not coordinator.is_stateless:
        coordinator.update_interval = timedelta(seconds=1)


@EVENT_HANDLERS.register(EventName.EXECUTION_STATE_CHANGED)
async def on_execution_state_changed(
    coordinator: OverkizDataUpdateCoordinator, event: Event
) -> None:
    """Handle execution changed event."""
    if event.exec_id in coordinator.executions and event.new_state in [
        ExecutionState.COMPLETED,
        ExecutionState.FAILED,
    ]:
        del coordinator.executions[event.exec_id]
