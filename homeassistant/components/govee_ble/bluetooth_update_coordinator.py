"""The Govee Bluetooth integration."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, Generic, TypeVar

from homeassistant.components import bluetooth
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import entity
from homeassistant.helpers.update_coordinator import UpdateFailed

_T = TypeVar("_T")
_BluetoothDataUpdateCoordinatorT = TypeVar(
    "_BluetoothDataUpdateCoordinatorT", bound="BluetoothDataUpdateCoordinator[Any]"
)


class BluetoothDataUpdateCoordinator(Generic[_T]):
    """Bluetooth data update dispatcher."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        matcher: bluetooth.BluetoothCallbackMatcher,
        *,
        name: str,
        update_method: Callable[
            [bluetooth.BluetoothServiceInfo, bluetooth.BluetoothChange], _T
        ]
        | None = None,
    ) -> None:
        """Initialize the dispatcher."""
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_method = update_method
        self.matcher = matcher
        self._listeners: dict[CALLBACK_TYPE, tuple[CALLBACK_TYPE, object | None]] = {}
        # It's None before the first successful update.
        # Set type to just T to remove annoying checks that data is not None
        # when it was already checked during setup.
        self.data: _T = None  # type: ignore[assignment]
        self._cancel: CALLBACK_TYPE | None = None
        self.last_update_success = True
        self.last_exception: Exception | None = None

    @callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Start the callback."""
        return bluetooth.async_register_callback(
            self.hass,
            self._async_handle_bluetooth_event,
            self.matcher,
        )

    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        """Listen for data updates."""

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self._listeners.pop(remove_listener)

        self._listeners[remove_listener] = (update_callback, context)
        return remove_listener

    @callback
    def async_update_listeners(self) -> None:
        """Update all registered listeners."""
        for update_callback, _ in list(self._listeners.values()):
            update_callback()

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfo,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        if self.update_method is None:
            raise NotImplementedError("Update method not implemented")

        try:
            self.data = self.update_method(service_info, change)
        except UpdateFailed as err:
            self.last_update_success = False
            self.last_exception = err
            self.logger.error("Error updating %s data: %s", self.name, err)
        except Exception as err:  # pylint: disable=broad-except
            self.last_exception = err
            self.last_update_success = False
            self.logger.exception("Unexpected error update %s data: %s", self.name, err)
        else:
            if not self.last_update_success:
                self.last_update_success = True
                self.logger.info("Fetching %s data recovered", self.name)

        self.async_update_listeners()


class BluetoothCoordinatorEntity(
    entity.Entity, Generic[_BluetoothDataUpdateCoordinatorT]
):
    """A class for entities using DataUpdateCoordinator."""

    def __init__(
        self, coordinator: _BluetoothDataUpdateCoordinatorT, context: Any = None
    ) -> None:
        """Create the entity with a DataUpdateCoordinator."""
        self.coordinator = coordinator
        self.coordinator_context = context

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self._handle_coordinator_update, self.coordinator_context
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
