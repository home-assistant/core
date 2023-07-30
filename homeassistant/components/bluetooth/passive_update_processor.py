"""Passive update processors for the Bluetooth integration."""
from __future__ import annotations

from collections.abc import Callable
import dataclasses
from datetime import timedelta
import logging
from typing import Any, Generic, TypedDict, TypeVar, cast

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_NAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .models import BluetoothChange, BluetoothScanningMode, BluetoothServiceInfoBleak
from .update_coordinator import BasePassiveBluetoothCoordinator


@dataclasses.dataclass(slots=True, frozen=True)
class PassiveBluetoothEntityKey:
    """Key for a passive bluetooth entity.

    Example:
    key: temperature
    device_id: outdoor_sensor_1
    """

    key: str
    device_id: str | None


_T = TypeVar("_T")

STORAGE_KEY = "bluetooth.passive_update_processor"
STORAGE_SAVE_INTERVAL = timedelta(minutes=15)
PASSIVE_UPDATE_PROCESSOR = "passive_update_processor"


@dataclasses.dataclass(slots=True, frozen=False)
class PassiveBluetoothProcessorData:
    """Data for the passive bluetooth processor."""

    coordinators: set[PassiveBluetoothProcessorCoordinator] = dataclasses.field(
        default_factory=set
    )
    restore_data: dict[str, dict[str, dict[str, Any]]] = dataclasses.field(
        default_factory=dict
    )


class PassiveBluetoothEntityKeyDict(TypedDict):
    """Passive bluetooth entity key dict."""

    key: str
    device_id: str | None


class RestoredPassiveBluetoothDataUpdate(TypedDict):
    """Restored PassiveBluetoothDataUpdate."""

    devices: dict[str | None, DeviceInfo]
    entity_descriptions: dict[PassiveBluetoothEntityKeyDict, dict[str, Any]]
    entity_names: dict[PassiveBluetoothEntityKeyDict, str | None]
    entity_data: dict[PassiveBluetoothEntityKeyDict, Any]


@dataclasses.dataclass(slots=True, frozen=True)
class PassiveBluetoothDataUpdate(Generic[_T]):
    """Generic bluetooth data."""

    devices: dict[str | None, DeviceInfo] = dataclasses.field(default_factory=dict)
    entity_descriptions: dict[
        PassiveBluetoothEntityKey, EntityDescription
    ] = dataclasses.field(default_factory=dict)
    entity_names: dict[PassiveBluetoothEntityKey, str | None] = dataclasses.field(
        default_factory=dict
    )
    entity_data: dict[PassiveBluetoothEntityKey, _T] = dataclasses.field(
        default_factory=dict
    )

    def update(self, new_data: PassiveBluetoothDataUpdate[_T]) -> None:
        """Update the data."""
        self.devices.update(new_data.devices)
        self.entity_descriptions.update(new_data.entity_descriptions)
        self.entity_data.update(new_data.entity_data)
        self.entity_names.update(new_data.entity_names)

    def async_get_restore_data(self) -> dict[str, Any]:
        """Serialize restore data to storage."""
        return {
            "devices": self.devices,
            "entity_descriptions": self.entity_descriptions,
            "entity_names": self.entity_names,
            "entity_data": self.entity_data,
        }

    @callback
    def async_set_restore_data(
        self,
        restored_data: RestoredPassiveBluetoothDataUpdate,
        entity_description_class: type[EntityDescription],
    ) -> None:
        """Set the restored data from storage."""
        self.devices.update(restored_data["devices"])
        restored_entity_descriptions = {
            PassiveBluetoothEntityKey(
                **passive_bluetooth_entity_key
            ): entity_description_class(**description)
            for passive_bluetooth_entity_key, description in restored_data[
                "entity_descriptions"
            ].items()
        }
        self.entity_descriptions.update(restored_entity_descriptions)
        restored_entity_names = {
            PassiveBluetoothEntityKey(**passive_bluetooth_entity_key): name
            for passive_bluetooth_entity_key, name in restored_data[
                "entity_names"
            ].items()
        }
        self.entity_names.update(restored_entity_names)
        restored_entity_data = {
            PassiveBluetoothEntityKey(**passive_bluetooth_entity_key): cast(_T, data)
            for passive_bluetooth_entity_key, data in restored_data[
                "entity_data"
            ].items()
        }
        self.entity_data.update(restored_entity_data)


def register_coordinator(
    hass: HomeAssistant, coordinator: PassiveBluetoothProcessorCoordinator
) -> CALLBACK_TYPE:
    """Register a coordinator to have its processors data restored."""
    data: PassiveBluetoothProcessorData = hass.data[PASSIVE_UPDATE_PROCESSOR]
    data.coordinators.add(coordinator)
    if (restore_key := coordinator.restore_key) and (
        coordinator_restored_data := data.restore_data.get(restore_key)
    ):
        coordinator.restored_data = coordinator_restored_data

    def _unregister_coordinator() -> None:
        """Unregister a coordinator."""
        data.coordinators.remove(coordinator)

    return _unregister_coordinator


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the passive update processor coordinators."""
    data = PassiveBluetoothProcessorData()
    hass.data[PASSIVE_UPDATE_PROCESSOR] = data
    storage: Store[dict[str, dict[str, dict[str, Any]]]] = Store(hass, 1, STORAGE_KEY)
    if restore_data := await storage.async_load():
        data.restore_data = restore_data
    coordinators = data.coordinators

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
        EVENT_HOMEASSISTANT_STOP, _async_save_processor_data_at_stop
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
        self.restored_data: dict[str, dict[str, Any]] | None = None
        self.restore_key = None
        if config_entry := config_entries.current_entry.get():
            self.restore_key = config_entry.entry_id

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self.last_update_success

    @callback
    def async_get_restore_data(
        self,
    ) -> dict[str, dict[str, Any]]:
        """Generate the restore data."""
        return {
            processor.restore_key: processor.data.async_get_restore_data()
            for processor in self._processors
            if processor.restore_key
        }

    @callback
    def _async_start(self) -> None:
        """Start the callbacks."""
        super()._async_start()
        self._on_stop.append(register_coordinator(self.hass, self))

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
        super()._async_handle_bluetooth_event(service_info, change)
        if self.hass.is_stopping:
            return

        try:
            update = self._update_method(service_info)
        except Exception as err:  # pylint: disable=broad-except
            self.last_update_success = False
            self.logger.exception(
                "Unexpected error updating %s data: %s", self.name, err
            )
            return

        if not self.last_update_success:
            self.last_update_success = True
            self.logger.info("Coordinator %s recovered", self.name)

        for processor in self._processors:
            processor.async_handle_update(update)


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
    data: PassiveBluetoothDataUpdate[_T] = PassiveBluetoothDataUpdate()
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
        data: PassiveBluetoothDataUpdate[_T] = PassiveBluetoothDataUpdate()
        if (
            entity_description_class
            and (restore_key := self.restore_key)
            and (restored_data := coordinator.restored_data)
            and (restored_processor_data := restored_data.get(restore_key))
        ):
            data.async_set_restore_data(
                cast(RestoredPassiveBluetoothDataUpdate, restored_processor_data),
                entity_description_class,
            )
        self.data = data
        # These attributes to access the data in
        # self.data are for backwards compatibility.
        self.entity_names = data.entity_names
        self.entity_data = data.entity_data
        self.entity_descriptions = data.entity_descriptions
        self.devices = data.devices

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
            entities: list[PassiveBluetoothProcessorEntity] = []
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
    def async_handle_update(self, update: _T) -> None:
        """Handle a Bluetooth event."""
        try:
            new_data = self.update_method(update)
        except Exception as err:  # pylint: disable=broad-except
            self.last_update_success = False
            self.coordinator.logger.exception(
                "Unexpected error updating %s data: %s", self.coordinator.name, err
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

        self.data.update(new_data)
        self.async_update_listeners(new_data)


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
        self._attr_name = processor.entity_names.get(entity_key)

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
