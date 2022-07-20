"""The Bluetooth integration."""
from __future__ import annotations

from collections.abc import Callable
import dataclasses
from datetime import datetime
import logging
import time
from typing import Any, Generic, TypeVar

from home_assistant_bluetooth import BluetoothServiceInfo

from homeassistant.const import ATTR_IDENTIFIERS, ATTR_NAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

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
    """Passive bluetooth data update coordinator for bluetooth advertisements.

    The coordinator is responsible for keeping track of the bluetooth data,
    updating subscribers, and device availability.

    The update_method must return a PassiveBluetoothDataUpdate object. Callers
    are responsible for formatting the data returned from their parser into
    the appropriate format.

    The coordinator will call the update_method every time the bluetooth device
    receives a new advertisement with the following signature:

    update_method(service_info: BluetoothServiceInfo) -> PassiveBluetoothDataUpdate

    As the size of each advertisement is limited, the update_method should
    return a PassiveBluetoothDataUpdate object that contains only data that
    should be updated. The coordinator will then dispatch subscribers based
    on the data in the PassiveBluetoothDataUpdate object. The accumulated data
    is available in the devices, entity_data, and entity_descriptions attributes.
    """

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
            PassiveBluetoothEntityKey,
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
        self._cancel_track_available: CALLBACK_TYPE | None = None
        self._present = False

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._present and self.last_update_success

    @callback
    def _async_cancel_available_tracker(self) -> None:
        """Reset the available tracker."""
        if self._cancel_track_available:
            self._cancel_track_available()
            self._cancel_track_available = None

    @callback
    def _async_schedule_available_tracker(self, time_remaining: float) -> None:
        """Schedule the available tracker."""
        self._cancel_track_available = async_call_later(
            self.hass, time_remaining, self._async_check_device_present
        )

    @callback
    def _async_check_device_present(self, _: datetime) -> None:
        """Check if the device is present."""
        time_passed_since_seen = time.monotonic() - self._last_callback_time
        self._async_cancel_available_tracker()
        if (
            not self._present
            or time_passed_since_seen < UNAVAILABLE_SECONDS
            or async_address_present(self.hass, self.address)
        ):
            self._async_schedule_available_tracker(
                UNAVAILABLE_SECONDS - time_passed_since_seen
            )
            return
        self._present = False
        self.async_update_listeners(None)

    @callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Start the callback."""
        return async_register_callback(
            self.hass,
            self._async_handle_bluetooth_event,
            BluetoothCallbackMatcher(address=self.address),
        )

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
        entity_key: PassiveBluetoothEntityKey,
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
        for listeners in self._entity_key_listeners.values():
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
        if not self._cancel_track_available:
            self._async_schedule_available_tracker(UNAVAILABLE_SECONDS)
        if self.hass.is_stopping:
            return

        try:
            new_data = self.update_method(service_info)
        except Exception as err:  # pylint: disable=broad-except
            self.last_update_success = False
            self.logger.exception(
                "Unexpected error updating %s data: %s", self.name, err
            )
            return

        if not isinstance(new_data, PassiveBluetoothDataUpdate):
            self.last_update_success = False  # type: ignore[unreachable]
            raise ValueError(
                f"The update_method for {self.name} returned {new_data} instead of a PassiveBluetoothDataUpdate"
            )

        if not self.last_update_success:
            self.last_update_success = True
            self.logger.info("Processing %s data recovered", self.name)

        self.devices.update(new_data.devices)
        self.entity_descriptions.update(new_data.entity_descriptions)
        self.entity_data.update(new_data.entity_data)
        self.async_update_listeners(new_data)


class PassiveBluetoothCoordinatorEntity(
    Entity, Generic[_PassiveBluetoothDataUpdateCoordinatorT]
):
    """A class for entities using PassiveBluetoothDataUpdateCoordinator."""

    _attr_has_entity_name = True
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
        if device_id:
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
