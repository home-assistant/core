"""APsystems base entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ApSystemsData, ApSystemsDataCoordinator


class ApSystemsEntity(Entity):
    """Defines a base APsystems entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        data: ApSystemsData,
    ) -> None:
        """Initialize the APsystems entity."""
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data.device_id)},
            manufacturer="APsystems",
            model="EZ1-M",
            serial_number=data.device_id,
            sw_version=data.coordinator.sw_version,
        )


class ApSystemsCoordinatorEntity(
    CoordinatorEntity[ApSystemsDataCoordinator], ApSystemsEntity
):
    """Defines a base APsystems entity backed by the data coordinator."""

    def __init__(self, data: ApSystemsData) -> None:
        """Initialize the APsystems coordinator entity."""
        super().__init__(data.coordinator)
        ApSystemsEntity.__init__(self, data)
