"""Melnor integration models."""

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import TypeVar

from melnor_bluetooth.device import Device, Valve

from homeassistant.components.number import EntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MelnorDataUpdateCoordinator(DataUpdateCoordinator[Device]):  # pylint: disable=hass-enforce-coordinator-module
    """Melnor data update coordinator."""

    _device: Device

    def __init__(self, hass: HomeAssistant, device: Device) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Melnor Bluetooth",
            update_interval=timedelta(seconds=5),
        )
        self._device = device

    async def _async_update_data(self):
        """Update the device state."""

        await self._device.fetch_state()
        return self._device


class MelnorBluetoothEntity(CoordinatorEntity[MelnorDataUpdateCoordinator]):  # pylint: disable=hass-enforce-coordinator-module
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


T = TypeVar("T", bound=EntityDescription)


def get_entities_for_valves(
    coordinator: MelnorDataUpdateCoordinator,
    descriptions: list[T],
    function: Callable[
        [Valve, T],
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
