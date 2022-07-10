"""The Bluetooth integration."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
import logging
import time
from typing import TYPE_CHECKING, Optional

from homeassistant.components import bluetooth
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .device import BluetoothDeviceData
from .entity import BluetoothDeviceKey

UNAVAILABLE_SECONDS = 60 * 5
NEVER_TIME = -UNAVAILABLE_SECONDS

BluetoothListenerCallbackType = Callable[
    [Optional[Mapping[BluetoothDeviceKey, EntityDescription]]], None
]
if TYPE_CHECKING:
    from .entity import BluetoothCoordinatorEntity


class BluetoothDataUpdateCoordinator:
    """Bluetooth data update dispatcher."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        address: str,
        data: BluetoothDeviceData,
        *,
        name: str,
    ) -> None:
        """Initialize the dispatcher."""
        self.data = data
        self.entity_descriptions = data.entity_descriptions
        self.hass = hass
        self.logger = logger
        self.name = name
        self.address = address
        self._listeners: dict[
            BluetoothDeviceKey | None, list[BluetoothListenerCallbackType]
        ] = {}
        self._cancel: CALLBACK_TYPE | None = None
        self.last_update_success = True
        self._present = True
        self.last_exception: Exception | None = None
        self._last_callback_time: float = NEVER_TIME

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._present and self.last_update_success

    def _async_check_device_present(self, _: datetime) -> None:
        """Check if the device is present."""
        if (
            not self._present
            or time.monotonic() - self._last_callback_time < UNAVAILABLE_SECONDS
        ):
            return
        if bluetooth.async_address_present(self.hass, self.address):
            return
        self._present = False
        for key, callbacks in self._listeners.items():
            if key is not None:
                for update_callback in callbacks:
                    update_callback(None)

    @callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Start the callback."""
        cancel_track_time = async_track_time_interval(
            self.hass,
            self._async_check_device_present,
            timedelta(seconds=UNAVAILABLE_SECONDS),
        )
        cancel_callback = bluetooth.async_register_callback(
            self.hass,
            self._async_handle_bluetooth_event,
            bluetooth.BluetoothCallbackMatcher(address=self.address),
        )

        @callback
        def _async_cancel_all() -> None:
            cancel_track_time()
            cancel_callback()

        return _async_cancel_all

    @callback
    def async_add_entities_listener(
        self,
        entity_class: type[BluetoothCoordinatorEntity],
        async_add_entites: AddEntitiesCallback,
    ) -> Callable[[], None]:
        """Add a listener for new entities."""
        created: set[BluetoothDeviceKey] = set()

        @callback
        def _async_add_or_update_entities(
            data: Mapping[BluetoothDeviceKey, EntityDescription] | None,
        ) -> None:
            """Listen for new entities."""
            entities: list[BluetoothCoordinatorEntity] = []
            if data:
                for key, description in data.items():
                    if key not in created:
                        entities.append(entity_class(self, description, key))
                        created.add(key)
            if entities:
                async_add_entites(entities)

        return self.async_add_listener(_async_add_or_update_entities)

    @callback
    def async_add_listener(
        self,
        update_callback: BluetoothListenerCallbackType,
        device_key: BluetoothDeviceKey | None = None,
    ) -> Callable[[], None]:
        """Listen for data updates."""

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self._listeners[device_key].remove(update_callback)
            if not self._listeners[device_key]:
                del self._listeners[device_key]

        self._listeners.setdefault(device_key, []).append(update_callback)
        return remove_listener

    @callback
    def async_update_listeners(
        self, data: Mapping[BluetoothDeviceKey, EntityDescription]
    ) -> None:
        """Update all registered listeners."""
        # Dispatch to listeners without a filter key
        if listeners := self._listeners.get(None):
            for update_callback in listeners:
                update_callback(data)

        # Dispatch to listeners with a filter key
        for key in data:
            if listeners := self._listeners.get(key):
                for update_callback in listeners:
                    update_callback(data)

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfo,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        self._last_callback_time = time.monotonic()
        self._present = True
        try:
            data_update = self.data.generate_update(service_info)
        except Exception as err:  # pylint: disable=broad-except
            self.last_exception = err
            self.last_update_success = False
            self.logger.exception("Unexpected error update %s data: %s", self.name, err)
        else:
            if not self.last_update_success:
                self.last_update_success = True
                self.logger.info("Processing %s data recovered", self.name)
            if data_update:
                self.async_update_listeners(data_update)
