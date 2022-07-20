"""The Bluetooth integration."""
from __future__ import annotations

from collections.abc import Callable
import dataclasses
from datetime import datetime, timedelta
import logging
import time
from typing import Any, Generic, TypeVar

from home_assistant_bluetooth import BluetoothServiceInfo

from homeassistant.const import ATTR_IDENTIFIERS, ATTR_NAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    async_address_present,
    async_register_callback,
)
from .const import DOMAIN

UNAVAILABLE_SECONDS = 60 * 5
NEVER_TIME = -UNAVAILABLE_SECONDS


@dataclasses.dataclass(frozen=True)
class PassiveBluetoothEntityKey:
    """Key for a passive bluetooth entity.

    Example:
    key: temperature
    device_id: outdoor_sensor_1
    """

    key: str
    device_id: str | None


_T = TypeVar("_T")


@dataclasses.dataclass(frozen=True)
class PassiveBluetoothDataUpdate(Generic[_T]):
    """Generic bluetooth data."""

    devices: dict[str | None, DeviceInfo] = dataclasses.field(default_factory=dict)
    entity_descriptions: dict[
        PassiveBluetoothEntityKey, EntityDescription
    ] = dataclasses.field(default_factory=dict)
    entity_data: dict[PassiveBluetoothEntityKey, _T] = dataclasses.field(
        default_factory=dict
    )


_PassiveBluetoothDataUpdateCoordinatorT = TypeVar(
    "_PassiveBluetoothDataUpdateCoordinatorT",
    bound="PassiveBluetoothDataUpdateCoordinator[Any]",
)


class PassiveBluetoothDataUpdateCoordinator(Generic[_T]):
    """Bluetooth data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        address: str,
        update_method: Callable[[BluetoothServiceInfo], PassiveBluetoothDataUpdate[_T]],
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.logger = logger
        self.name: str | None = None
        self.address = address
        self._listeners: list[
            Callable[[PassiveBluetoothDataUpdate[_T] | None], None]
        ] = []
        self._entity_key_listeners: dict[
            PassiveBluetoothEntityKey | None,
            list[Callable[[PassiveBluetoothDataUpdate[_T] | None], None]],
        ] = {}
        self.update_method = update_method

        self.entity_data: dict[PassiveBluetoothEntityKey, _T] = {}
        self.entity_descriptions: dict[
            PassiveBluetoothEntityKey, EntityDescription
        ] = {}
        self.devices: dict[str | None, DeviceInfo] = {}

        self.last_update_success = True
        self._last_callback_time: float = NEVER_TIME
        self._present = True

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._present and self.last_update_success

    def _async_check_device_present(self, _: datetime) -> None:
        """Check if the device is present."""
        if (
            not self._present
            or time.monotonic() - self._last_callback_time < UNAVAILABLE_SECONDS
            or async_address_present(self.hass, self.address)
        ):
            return
        self._present = False
        self.async_update_listeners(None)

    @callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Start the callback."""
        cancels = [
            async_track_time_interval(
                self.hass,
                self._async_check_device_present,
                timedelta(seconds=UNAVAILABLE_SECONDS),
            ),
            async_register_callback(
                self.hass,
                self._async_handle_bluetooth_event,
                BluetoothCallbackMatcher(address=self.address),
            ),
        ]

        @callback
        def _async_cancel_all() -> None:
            """Cancel all the callbacks."""
            for cancel in cancels:
                cancel()

        return _async_cancel_all

    @callback
    def async_add_entities_listener(
        self,
        entity_class: type[PassiveBluetoothCoordinatorEntity],
        async_add_entites: AddEntitiesCallback,
    ) -> Callable[[], None]:
        """Add a listener for new entities."""
        created: set[PassiveBluetoothEntityKey] = set()

        @callback
        def _async_add_or_update_entities(
            data: PassiveBluetoothDataUpdate[_T] | None,
        ) -> None:
            """Listen for new entities."""
            if data is None:
                return
            entities: list[PassiveBluetoothCoordinatorEntity] = []
            for entity_key, description in data.entity_descriptions.items():
                if entity_key not in created:
                    entities.append(entity_class(self, entity_key, description))
                    created.add(entity_key)
            if entities:
                async_add_entites(entities)

        return self.async_add_listener(_async_add_or_update_entities)

    @callback
    def async_add_listener(
        self,
        update_callback: Callable[[PassiveBluetoothDataUpdate[_T] | None], None],
    ) -> Callable[[], None]:
        """Listen for all updates."""

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self._listeners.remove(update_callback)

        self._listeners.append(update_callback)
        return remove_listener

    @callback
    def async_add_entity_key_listener(
        self,
        update_callback: Callable[[PassiveBluetoothDataUpdate[_T] | None], None],
        entity_key: PassiveBluetoothEntityKey | None = None,
    ) -> Callable[[], None]:
        """Listen for updates by device key."""

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self._entity_key_listeners[entity_key].remove(update_callback)
            if not self._entity_key_listeners[entity_key]:
                del self._entity_key_listeners[entity_key]

        self._entity_key_listeners.setdefault(entity_key, []).append(update_callback)
        return remove_listener

    @callback
    def async_update_listeners(
        self, data: PassiveBluetoothDataUpdate[_T] | None
    ) -> None:
        """Update all registered listeners."""
        # Dispatch to listeners without a filter key
        for update_callback in self._listeners:
            update_callback(data)

        # Dispatch to listeners with a filter key
        for key in self._entity_key_listeners:
            if listeners := self._entity_key_listeners.get(key):
                for update_callback in listeners:
                    update_callback(data)

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfo,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        self.name = service_info.name
        self._last_callback_time = time.monotonic()
        self._present = True

        try:
            new_data = self.update_method(service_info)
        except Exception as err:  # pylint: disable=broad-except
            self.last_update_success = False
            self.logger.exception(
                "Unexpected error updating %s data: %s", self.name, err
            )
            return

        if not self.last_update_success:
            self.last_update_success = True
            self.logger.info("Processing %s data recovered", self.name)

        if new_data:
            self.devices.update(new_data.devices)
            self.entity_descriptions.update(new_data.entity_descriptions)
            self.entity_data.update(new_data.entity_data)
            self.async_update_listeners(new_data)


class PassiveBluetoothCoordinatorEntity(
    Entity, Generic[_PassiveBluetoothDataUpdateCoordinatorT]
):
    """A class for entities using PassiveBluetoothDataUpdateCoordinator."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: _PassiveBluetoothDataUpdateCoordinatorT,
        entity_key: PassiveBluetoothEntityKey,
        description: EntityDescription,
        context: Any = None,
    ) -> None:
        """Create the entity with a PassiveBluetoothDataUpdateCoordinator."""
        self.entity_description = description
        self.entity_key = entity_key
        self.coordinator = coordinator
        self.coordinator_context = context
        address = coordinator.address
        device_id = entity_key.device_id
        devices = coordinator.devices
        key = entity_key.key
        if device_id in devices:
            base_device_info = devices[device_id]
        else:
            base_device_info = DeviceInfo({})
        if entity_key.device_id:
            self._attr_device_info = base_device_info | DeviceInfo(
                {ATTR_IDENTIFIERS: {(DOMAIN, f"{address}-{device_id}")}}
            )
            self._attr_unique_id = f"{address}-{key}-{device_id}"
        else:
            self._attr_device_info = base_device_info | DeviceInfo(
                {ATTR_IDENTIFIERS: {(DOMAIN, address)}}
            )
            self._attr_unique_id = f"{address}-{key}"
        if ATTR_NAME not in self._attr_device_info:
            self._attr_device_info[ATTR_NAME] = self.coordinator.name

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.available

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_entity_key_listener(
                self._handle_coordinator_update, self.entity_key
            )
        )

    @callback
    def _handle_coordinator_update(
        self, new_data: PassiveBluetoothDataUpdate | None
    ) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
