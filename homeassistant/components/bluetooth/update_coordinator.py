"""The Govee Bluetooth integration."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device import BluetoothDeviceData
from .entity import BluetoothDeviceEntityDescriptionsType, BluetoothDeviceKey

BluetoothListenerCallbackType = Callable[[BluetoothDeviceEntityDescriptionsType], None]


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
        parser_method: Callable[
            [bluetooth.BluetoothServiceInfo, bluetooth.BluetoothChange],
            dict[str, Any] | None,
        ]
        | None = None,
    ) -> None:
        """Initialize the dispatcher."""
        self.data = data
        self.entity_descriptions = data.entity_descriptions
        self.hass = hass
        self.logger = logger
        self.name = name
        self.parser_method = parser_method
        self.address = address
        self._listeners: dict[
            BluetoothDeviceKey | None, list[BluetoothListenerCallbackType]
        ] = {}
        self._cancel: CALLBACK_TYPE | None = None
        self.last_update_success = True
        self.last_exception: Exception | None = None

    @callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Start the callback."""
        if self.parser_method is None:
            raise NotImplementedError("Parser method not implemented")
        return bluetooth.async_register_callback(
            self.hass,
            self._async_handle_bluetooth_event,
            bluetooth.BluetoothCallbackMatcher(address=self.address),
        )

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
            data: BluetoothDeviceEntityDescriptionsType,
        ) -> None:
            """Listen for new entities."""
            entities: list[entity.Entity] = []
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
        self, data: BluetoothDeviceEntityDescriptionsType
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
        assert self.parser_method is not None
        try:
            data_update = self.data.generate_update(service_info, change)
        except Exception as err:  # pylint: disable=broad-except
            self.last_exception = err
            self.last_update_success = False
            self.logger.exception("Unexpected error update %s data: %s", self.name, err)
        else:
            if not self.last_update_success:
                self.last_update_success = True
                self.logger.info("Fetching %s data recovered", self.name)
            if data_update:
                self.async_update_listeners(data_update)


class BluetoothCoordinatorEntity(entity.Entity):
    """A class for entities using DataUpdateCoordinator."""

    def __init__(
        self,
        coordinator: BluetoothDataUpdateCoordinator,
        description: entity.EntityDescription,
        device_key: BluetoothDeviceKey,
    ) -> None:
        """Create the entity with a DataUpdateCoordinator."""
        self.device_key = device_key
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}-{description.key}"
        self._attr_name = f"{coordinator.name} {description.name}"
        identifiers: set[tuple[str, str]] = set()
        connections: set[tuple[str, str]] = set()
        if device_key.device_id:
            identifiers.add(
                (bluetooth.DOMAIN, f"{coordinator.address}-{self.device_key.device_id}")
            )
        elif ":" in coordinator.address:
            # Linux
            connections.add((dr.CONNECTION_NETWORK_MAC, coordinator.address))
        else:
            # Mac uses UUIDs
            identifiers.add((bluetooth.DOMAIN, coordinator.address))
        self._attr_device_info = entity.DeviceInfo(
            name=coordinator.data.get_device_name(self.device_key.device_id),
            connections=connections,
            identifiers=identifiers,
        )

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # TODO: be able to set some type of timeout for last update
        # Check every 5 minutes to see if we are still in devices?
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self._handle_coordinator_update, self.device_key
            )
        )

    @callback
    def _handle_coordinator_update(
        self, data: BluetoothDeviceEntityDescriptionsType
    ) -> None:
        """Handle updated data from the coordinator."""
        self.entity_description = data[self.device_key]
        self.async_write_ha_state()
