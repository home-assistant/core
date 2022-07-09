"""The bluetooth integration."""
from __future__ import annotations

from collections.abc import Mapping
import dataclasses
from typing import TYPE_CHECKING

from homeassistant.components import bluetooth
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity

if TYPE_CHECKING:
    from .update_coordinator import BluetoothDataUpdateCoordinator


@dataclasses.dataclass(frozen=True)
class BluetoothDeviceKey:
    """Key for a bluetooth device.

    Example:
    device_id: outdoor_sensor_1
    key: temperature
    """

    device_id: str | None
    key: str


BluetoothDeviceEntityDescriptionsType = Mapping[
    BluetoothDeviceKey, entity.EntityDescription
]


@dataclasses.dataclass
class BluetoothDescriptionRequiredKeysMixin:
    """Mixin for required keys."""

    device_key: BluetoothDeviceKey


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
        self._attr_unique_id = f"{coordinator.address}-{self.device_key.key}"
        self._attr_name = description.name
        identifiers: set[tuple[str, str]] = set()
        connections: set[tuple[str, str]] = set()
        if device_key.device_id:
            identifiers.add(
                (bluetooth.DOMAIN, f"{coordinator.address}-{self.device_key.device_id}")
            )
            self._attr_unique_id = f"{coordinator.address}-{self.device_key.device_id}-{self.device_key.key}"
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
