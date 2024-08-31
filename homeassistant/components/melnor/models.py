"""Melnor integration models."""

from collections.abc import Callable

from melnor_bluetooth.device import Device, Valve

from homeassistant.components.number import EntityDescription
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MelnorDataUpdateCoordinator


class MelnorBluetoothEntity(CoordinatorEntity[MelnorDataUpdateCoordinator]):
    """Base class for melnor entities."""

    _device: Device
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MelnorDataUpdateCoordinator,
    ) -> None:
        """Initialize a melnor base entity."""
        super().__init__(coordinator)

        self._device = coordinator.data

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.mac)},
            manufacturer="Melnor",
            model=self._device.model,
            name=self._device.name,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._device = self.coordinator.data
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.is_connected


class MelnorZoneEntity(MelnorBluetoothEntity):
    """Base class for valves that define themselves as child devices."""

    _valve: Valve

    def __init__(
        self,
        coordinator: MelnorDataUpdateCoordinator,
        entity_description: EntityDescription,
        valve: Valve,
    ) -> None:
        """Initialize a valve entity."""
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{self._device.mac}-zone{valve.id}-{entity_description.key}"
        )
        self.entity_description = entity_description

        self._valve = valve

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._device.mac}-zone{self._valve.id}")},
            manufacturer="Melnor",
            name=f"Zone {valve.id + 1}",
            via_device=(DOMAIN, self._device.mac),
        )


def get_entities_for_valves[_T: EntityDescription](
    coordinator: MelnorDataUpdateCoordinator,
    descriptions: list[_T],
    function: Callable[
        [Valve, _T],
        CoordinatorEntity[MelnorDataUpdateCoordinator],
    ],
) -> list[CoordinatorEntity[MelnorDataUpdateCoordinator]]:
    """Get descriptions for valves."""
    entities: list[CoordinatorEntity[MelnorDataUpdateCoordinator]] = []

    # This device may not have 4 valves total, but the library will only expose the right number of valves
    for i in range(1, 5):
        valve = coordinator.data[f"zone{i}"]

        if valve is not None:
            entities.extend(
                function(valve, description) for description in descriptions
            )

    return entities
