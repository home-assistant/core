"""Passive update processors for the Bluetooth integration."""

from __future__ import annotations

import dataclasses
from datetime import timedelta
from functools import cache
import logging
from typing import TYPE_CHECKING, Any, Generic, TypedDict, TypeVar, cast

from habluetooth import BluetoothScanningMode

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_IDENTIFIERS,
    ATTR_NAME,
    CONF_ENTITY_CATEGORY,
    EVENT_HOMEASSISTANT_STOP,
    EntityCategory,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import async_get_current_platform
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.util.enum import try_parse_enum

from .const import DOMAIN
from .update_coordinator import BasePassiveBluetoothCoordinator

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .models import BluetoothChange, BluetoothServiceInfoBleak

STORAGE_KEY = "bluetooth.passive_update_processor"
STORAGE_VERSION = 1
STORAGE_SAVE_INTERVAL = timedelta(minutes=15)
PASSIVE_UPDATE_PROCESSOR = "passive_update_processor"
_T = TypeVar("_T")


@dataclasses.dataclass(slots=True, frozen=True)
class PassiveBluetoothEntityKey:
    """Key for a passive bluetooth entity.

    Example:
    key: temperature
    device_id: outdoor_sensor_1

    """

    key: str
    device_id: str | None

    def to_string(self) -> str:
        """Convert the key to a string which can be used as JSON key."""
        return f"{self.key}___{self.device_id or ''}"

    @classmethod
    def from_string(cls, key: str) -> PassiveBluetoothEntityKey:
        """Convert a string (from JSON) to a key."""
        key, device_id = key.split("___")
        return cls(key, device_id or None)


@dataclasses.dataclass(slots=True, frozen=False)
class PassiveBluetoothProcessorData:
    """Data for the passive bluetooth processor."""

    coordinators: set[PassiveBluetoothProcessorCoordinator]
    all_restore_data: dict[str, dict[str, RestoredPassiveBluetoothDataUpdate]]


class RestoredPassiveBluetoothDataUpdate(TypedDict):
    """Restored PassiveBluetoothDataUpdate."""

    devices: dict[str, DeviceInfo]
    entity_descriptions: dict[str, dict[str, Any]]
    entity_names: dict[str, str | None]
    entity_data: dict[str, Any]


# Fields do not change so we can cache the result
# of calling fields() on the dataclass
cached_fields = cache(dataclasses.fields)


def deserialize_entity_description(
    descriptions_class: type[EntityDescription], data: dict[str, Any]
) -> EntityDescription:
    """Deserialize an entity description."""
    # pylint: disable=protected-access
    result: dict[str, Any] = {}
    if hasattr(descriptions_class, "_dataclass"):
        descriptions_class = descriptions_class._dataclass
    for field in cached_fields(descriptions_class):
        field_name = field.name
        # It would be nice if field.type returned the actual
        # type instead of a str so we could avoid writing this
        # out, but it doesn't. If we end up using this in more
        # places we can add a `as_dict` and a `from_dict`
        # method to these classes
        if field_name == CONF_ENTITY_CATEGORY:
            value = try_parse_enum(EntityCategory, data.get(field_name))
        else:
            value = data.get(field_name)
        result[field_name] = value
    return descriptions_class(**result)


def serialize_entity_description(description: EntityDescription) -> dict[str, Any]:
    """Serialize an entity description."""
    return {
        field.name: value
        for field in cached_fields(type(description))
        if (value := getattr(description, field.name)) != field.default
    }


@dataclasses.dataclass(slots=True, frozen=False)
class PassiveBluetoothDataUpdate(Generic[_T]):
    """Generic bluetooth data."""

    devices: dict[str | None, DeviceInfo] = dataclasses.field(default_factory=dict)
    entity_descriptions: dict[PassiveBluetoothEntityKey, EntityDescription] = (
        dataclasses.field(default_factory=dict)
    )
    entity_names: dict[PassiveBluetoothEntityKey, str | None] = dataclasses.field(
        default_factory=dict
    )
    entity_data: dict[PassiveBluetoothEntityKey, _T] = dataclasses.field(
        default_factory=dict
    )

    def update(
        self, new_data: PassiveBluetoothDataUpdate[_T]
    ) -> set[PassiveBluetoothEntityKey] | None:
        """Update the data and returned changed PassiveBluetoothEntityKey or None on device change.

        The changed PassiveBluetoothEntityKey can be used to filter
        which listeners are called.
        """
        device_change = False
        changed_entity_keys: set[PassiveBluetoothEntityKey] = set()
        for key, device_info in new_data.devices.items():
            if device_change or self.devices.get(key, UNDEFINED) != device_info:
                device_change = True
                self.devices[key] = device_info
        for incoming, current in (
            (new_data.entity_descriptions, self.entity_descriptions),
            (new_data.entity_names, self.entity_names),
            (new_data.entity_data, self.entity_data),
        ):
            # mypy can't seem to work this out
            for key, data in incoming.items():  # type: ignore[attr-defined]
                if current.get(key, UNDEFINED) != data:  # type: ignore[attr-defined]
                    changed_entity_keys.add(key)  # type: ignore[arg-type]
                    current[key] = data  # type: ignore[index]
        # If the device changed we don't need to return the changed
        # entity keys as all entities will be updated
        return None if device_change else changed_entity_keys

    def async_get_restore_data(self) -> RestoredPassiveBluetoothDataUpdate:
        """Serialize restore data to storage."""
        return {
            "devices": {
                key or "": device_info for key, device_info in self.devices.items()
            },
            "entity_descriptions": {
                key.to_string(): serialize_entity_description(description)
                for key, description in self.entity_descriptions.items()
            },
            "entity_names": {
                key.to_string(): name for key, name in self.entity_names.items()
            },
            "entity_data": {
                key.to_string(): data for key, data in self.entity_data.items()
            },
        }

    @callback
    def async_set_restore_data(
        self,
        restore_data: RestoredPassiveBluetoothDataUpdate,
        entity_description_class: type[EntityDescription],
    ) -> None:
        """Set the restored data from storage."""
        self.devices.update(
            {
                key or None: device_info
                for key, device_info in restore_data["devices"].items()
            }
        )
        self.entity_descriptions.update(
            {
                PassiveBluetoothEntityKey.from_string(
                    key
                ): deserialize_entity_description(entity_description_class, description)
                for key, description in restore_data["entity_descriptions"].items()
                if description
            }
        )
        self.entity_names.update(
            {
                PassiveBluetoothEntityKey.from_string(key): name
                for key, name in restore_data["entity_names"].items()
            }
        )
        self.entity_data.update(
            {
                PassiveBluetoothEntityKey.from_string(key): cast(_T, data)
                for key, data in restore_data["entity_data"].items()
            }
        )


def async_register_coordinator_for_restore(
    hass: HomeAssistant, coordinator: PassiveBluetoothProcessorCoordinator
) -> CALLBACK_TYPE:
    """Register a coordinator to have its processors data restored."""
    data: PassiveBluetoothProcessorData = hass.data[PASSIVE_UPDATE_PROCESSOR]
    coordinators = data.coordinators
    coordinators.add(coordinator)
    if restore_key := coordinator.restore_key:
        coordinator.restore_data = data.all_restore_data.setdefault(restore_key, {})

    @callback
    def _unregister_coordinator_for_restore() -> None:
        """Unregister a coordinator."""
        coordinators.remove(coordinator)

    return _unregister_coordinator_for_restore


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the passive update processor coordinators."""
    storage: Store[dict[str, dict[str, RestoredPassiveBluetoothDataUpdate]]] = Store(
        hass, STORAGE_VERSION, STORAGE_KEY
    )
    coordinators: set[PassiveBluetoothProcessorCoordinator] = set()
    all_restore_data: dict[str, dict[str, RestoredPassiveBluetoothDataUpdate]] = (
        await storage.async_load() or {}
    )
    hass.data[PASSIVE_UPDATE_PROCESSOR] = PassiveBluetoothProcessorData(
        coordinators, all_restore_data
    )

    async def _async_save_processor_data(_: Any) -> None:
        """Save the processor data."""
        await storage.async_save(
            {
                coordinator.restore_key: coordinator.async_get_restore_data()
                for coordinator in coordinators
                if coordinator.restore_key
            }
        )

    cancel_interval = async_track_time_interval(
        hass, _async_save_processor_data, STORAGE_SAVE_INTERVAL
    )

    async def _async_save_processor_data_at_stop(_event: Event) -> None:
        """Save the processor data at shutdown."""
        cancel_interval()
        await _async_save_processor_data(None)

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP,
        _async_save_processor_data_at_stop,
    )


class PassiveBluetoothProcessorCoordinator(
    Generic[_T], BasePassiveBluetoothCoordinator
):
    """Passive bluetooth processor coordinator for bluetooth advertisements.

    The coordinator is responsible for dispatching the bluetooth data,
    to each processor, and tracking devices.

    The update_method should return the data that is dispatched to each processor.
    This is normally a parsed form of the data, but you can just forward the
    BluetoothServiceInfoBleak if needed.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        address: str,
        mode: BluetoothScanningMode,
        update_method: Callable[[BluetoothServiceInfoBleak], _T],
        connectable: bool = False,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, logger, address, mode, connectable)
        self._processors: list[PassiveBluetoothDataProcessor] = []
        self._update_method = update_method
        self.last_update_success = True
        self.restore_data: dict[str, RestoredPassiveBluetoothDataUpdate] = {}
        self.restore_key = None
        if config_entry := config_entries.current_entry.get():
            self.restore_key = config_entry.entry_id
        self._on_stop.append(async_register_coordinator_for_restore(self.hass, self))

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self.last_update_success

    @callback
    def async_get_restore_data(
        self,
    ) -> dict[str, RestoredPassiveBluetoothDataUpdate]:
        """Generate the restore data."""
        return {
            processor.restore_key: processor.data.async_get_restore_data()
            for processor in self._processors
            if processor.restore_key
        }

    @callback
    def async_register_processor(
        self,
        processor: PassiveBluetoothDataProcessor,
        entity_description_class: type[EntityDescription] | None = None,
    ) -> Callable[[], None]:
        """Register a processor that subscribes to updates."""

        # entity_description_class will become mandatory
        # in the future, but is optional for now to allow
        # for a transition period.
        processor.async_register_coordinator(self, entity_description_class)

        @callback
        def remove_processor() -> None:
            """Remove a processor."""
            # Save the data before removing the processor
            # so if they reload its still there
            if restore_key := processor.restore_key:
                self.restore_data[restore_key] = processor.data.async_get_restore_data()

            self._processors.remove(processor)

        self._processors.append(processor)
        return remove_processor

    @callback
    def _async_handle_unavailable(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Handle the device going unavailable."""
        super()._async_handle_unavailable(service_info)
        for processor in self._processors:
            processor.async_handle_unavailable()

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        was_available = self._available
        self._available = True
        if self.hass.is_stopping:
            return

        try:
            update = self._update_method(service_info)
        except Exception:  # pylint: disable=broad-except
            self.last_update_success = False
            self.logger.exception("Unexpected error updating %s data", self.name)
            return

        if not self.last_update_success:
            self.last_update_success = True
            self.logger.info("Coordinator %s recovered", self.name)

        for processor in self._processors:
            processor.async_handle_update(update, was_available)


_PassiveBluetoothDataProcessorT = TypeVar(
    "_PassiveBluetoothDataProcessorT",
    bound="PassiveBluetoothDataProcessor[Any]",
)


class PassiveBluetoothDataProcessor(Generic[_T]):
    """Passive bluetooth data processor for bluetooth advertisements.

    The processor is responsible for keeping track of the bluetooth data
    and updating subscribers.

    The update_method must return a PassiveBluetoothDataUpdate object. Callers
    are responsible for formatting the data returned from their parser into
    the appropriate format.

    The processor will call the update_method every time the bluetooth device
    receives a new advertisement data from the coordinator with the data
    returned by the update_method of the coordinator.

    As the size of each advertisement is limited, the update_method should
    return a PassiveBluetoothDataUpdate object that contains only data that
    should be updated. The coordinator will then dispatch subscribers based
    on the data in the PassiveBluetoothDataUpdate object. The accumulated data
    is available in the devices, entity_data, and entity_descriptions attributes.
    """

    coordinator: PassiveBluetoothProcessorCoordinator
    data: PassiveBluetoothDataUpdate[_T]
    entity_names: dict[PassiveBluetoothEntityKey, str | None]
    entity_data: dict[PassiveBluetoothEntityKey, _T]
    entity_descriptions: dict[PassiveBluetoothEntityKey, EntityDescription]
    devices: dict[str | None, DeviceInfo]
    restore_key: str | None

    def __init__(
        self,
        update_method: Callable[[_T], PassiveBluetoothDataUpdate[_T]],
        restore_key: str | None = None,
    ) -> None:
        """Initialize the coordinator."""
        try:
            self.restore_key = restore_key or async_get_current_platform().domain
        except RuntimeError:
            self.restore_key = None
        self._listeners: list[
            Callable[[PassiveBluetoothDataUpdate[_T] | None], None]
        ] = []
        self._entity_key_listeners: dict[
            PassiveBluetoothEntityKey,
            list[Callable[[PassiveBluetoothDataUpdate[_T] | None], None]],
        ] = {}
        self.update_method = update_method
        self.last_update_success = True

    @callback
    def async_register_coordinator(
        self,
        coordinator: PassiveBluetoothProcessorCoordinator,
        entity_description_class: type[EntityDescription] | None,
    ) -> None:
        """Register a coordinator."""
        self.coordinator = coordinator
        self.data = PassiveBluetoothDataUpdate()
        data = self.data
        # These attributes to access the data in
        # self.data are for backwards compatibility.
        self.entity_names = data.entity_names
        self.entity_data = data.entity_data
        self.entity_descriptions = data.entity_descriptions
        self.devices = data.devices
        if (
            entity_description_class
            and (restore_key := self.restore_key)
            and (restore_data := coordinator.restore_data)
            and (restored_processor_data := restore_data.get(restore_key))
        ):
            data.async_set_restore_data(
                restored_processor_data,
                entity_description_class,
            )
            self.async_update_listeners(data)

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.coordinator.available and self.last_update_success

    @callback
    def async_handle_unavailable(self) -> None:
        """Handle the device going unavailable."""
        self.async_update_listeners(None)

    @callback
    def async_add_entities_listener(
        self,
        entity_class: type[PassiveBluetoothProcessorEntity],
        async_add_entities: AddEntitiesCallback,
    ) -> Callable[[], None]:
        """Add a listener for new entities."""
        created: set[PassiveBluetoothEntityKey] = set()

        @callback
        def _async_add_or_update_entities(
            data: PassiveBluetoothDataUpdate[_T] | None,
        ) -> None:
            """Listen for new entities."""
            if data is None or created.issuperset(data.entity_descriptions):
                return
            entities: list[PassiveBluetoothProcessorEntity] = []
            for entity_key, description in data.entity_descriptions.items():
                if entity_key not in created:
                    entities.append(entity_class(self, entity_key, description))
                    created.add(entity_key)
            if entities:
                async_add_entities(entities)

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
        self,
        data: PassiveBluetoothDataUpdate[_T] | None,
        was_available: bool | None = None,
        changed_entity_keys: set[PassiveBluetoothEntityKey] | None = None,
    ) -> None:
        """Update all registered listeners."""
        if was_available is None:
            was_available = self.coordinator.available

        # Dispatch to listeners without a filter key
        for update_callback in self._listeners:
            update_callback(data)

        if not was_available or data is None:
            # When data is None, or was_available is False,
            # dispatch to all listeners as it means the device
            # is flipping between available and unavailable
            for listeners in self._entity_key_listeners.values():
                for update_callback in listeners:
                    update_callback(data)
            return

        # Dispatch to listeners with a filter key
        # if the key is in the data
        entity_key_listeners = self._entity_key_listeners
        for entity_key in data.entity_data:
            if (
                was_available
                and changed_entity_keys is not None
                and entity_key not in changed_entity_keys
            ):
                continue
            if maybe_listener := entity_key_listeners.get(entity_key):
                for update_callback in maybe_listener:
                    update_callback(data)

    @callback
    def async_handle_update(
        self, update: _T, was_available: bool | None = None
    ) -> None:
        """Handle a Bluetooth event."""
        try:
            new_data = self.update_method(update)
        except Exception:  # pylint: disable=broad-except
            self.last_update_success = False
            self.coordinator.logger.exception(
                "Unexpected error updating %s data", self.coordinator.name
            )
            return

        if not isinstance(new_data, PassiveBluetoothDataUpdate):
            self.last_update_success = False  # type: ignore[unreachable]
            raise TypeError(
                f"The update_method for {self.coordinator.name} returned"
                f" {new_data} instead of a PassiveBluetoothDataUpdate"
            )

        if not self.last_update_success:
            self.last_update_success = True
            self.coordinator.logger.info(
                "Processing %s data recovered", self.coordinator.name
            )

        changed_entity_keys = self.data.update(new_data)
        self.async_update_listeners(new_data, was_available, changed_entity_keys)


class PassiveBluetoothProcessorEntity(Entity, Generic[_PassiveBluetoothDataProcessorT]):
    """A class for entities using PassiveBluetoothDataProcessor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        processor: _PassiveBluetoothDataProcessorT,
        entity_key: PassiveBluetoothEntityKey,
        description: EntityDescription,
        context: Any = None,
    ) -> None:
        """Create the entity with a PassiveBluetoothDataProcessor."""
        self.entity_description = description
        self.entity_key = entity_key
        self.processor = processor
        self.processor_context = context
        address = processor.coordinator.address
        device_id = entity_key.device_id
        devices = processor.devices
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
            self._attr_device_info[ATTR_NAME] = self.processor.coordinator.name
        if device_id is None:
            self._attr_device_info[ATTR_CONNECTIONS] = {(CONNECTION_BLUETOOTH, address)}
        if (name := processor.entity_names.get(entity_key)) is not None:
            self._attr_name = name

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.processor.available

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.processor.async_add_entity_key_listener(
                self._handle_processor_update, self.entity_key
            )
        )

    @callback
    def _handle_processor_update(
        self, new_data: PassiveBluetoothDataUpdate | None
    ) -> None:
        """Handle updated data from the processor."""
        self.async_write_ha_state()
