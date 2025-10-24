"""Probe Plus base entity type."""

from dataclasses import dataclass

from pyprobeplus import ProbePlusDevice

from homeassistant.const import CONF_MODEL
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ProbePlusDataUpdateCoordinator


@dataclass
class ProbePlusEntity(CoordinatorEntity[ProbePlusDataUpdateCoordinator]):
    """Base class for Probe Plus entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ProbePlusDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        # Set the unique ID for the entity
        self._attr_unique_id = (
            f"{format_mac(coordinator.device.mac)}_{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, format_mac(coordinator.device.mac))},
            name=coordinator.device.name,
            manufacturer="Probe Plus",
            suggested_area="Kitchen",
            model=coordinator.config_entry.data.get(CONF_MODEL),
            connections={(CONNECTION_BLUETOOTH, coordinator.device.mac)},
        )

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return super().available and self.coordinator.device.connected

    @property
    def device(self) -> ProbePlusDevice:
        """Return the device associated with this entity."""
        return self.coordinator.device
