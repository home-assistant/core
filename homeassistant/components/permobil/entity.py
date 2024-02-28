"""PermobilEntyty class."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MyPermobilCoordinator
from .sensor import PermobilSensorEntityDescription


class PermobilEntity(CoordinatorEntity[MyPermobilCoordinator]):
    """Representation of a permobil Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MyPermobilCoordinator,
        description: PermobilSensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.p_api.email}_{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.p_api.email)},
            manufacturer="Permobil",
            name="Permobil Wheelchair",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success
