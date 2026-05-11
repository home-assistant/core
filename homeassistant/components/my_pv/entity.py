"""Base entity for the my-PV integration."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MyPVCoordinator


class MyPVBaseEntity(CoordinatorEntity[MyPVCoordinator]):
    """The my-PV base entity."""

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.connected:
            return False
        if self.coordinator.device.is_on is None:
            return False
        if self.coordinator.get_data_value(self.entity_description.key) is None:
            return False

        return self.coordinator.last_update_success
