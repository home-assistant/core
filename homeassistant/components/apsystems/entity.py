"""APsystems base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ApSystemsData
from .const import DOMAIN
from .coordinator import ApSystemsDataCoordinator


class ApSystemsEntity(Entity):
    """Defines a base APsystems entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        data: ApSystemsData,
    ) -> None:
        """Initialize the APsystems entity."""
        self._attr_unique_id = data.device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data.device_id)},
            serial_number=data.device_id,
            manufacturer="APsystems",
            model="EZ1-M",
        )


class ApSystemsCoordinatorEntity(
    CoordinatorEntity[ApSystemsDataCoordinator], ApSystemsEntity
):
    """Defines a Coordinator APsystems entity."""

    def __init__(
        self,
        data: ApSystemsData,
    ) -> None:
        """Initialize the APsystems entity and the coordinator entity."""
        super().__init__(data.coordinator)
        ApSystemsEntity.__init__(self, data)
