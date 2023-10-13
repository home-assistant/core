"""Base classes for SmartTub entities."""
import smarttub

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .helpers import get_spa_name


class SmartTubEntity(CoordinatorEntity):
    """Base class for SmartTub entities."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, spa: smarttub.Spa, entity_name
    ) -> None:
        """Initialize the entity.

        Given a spa id and a short name for the entity, we provide basic device
        info, name, unique id, etc. for all derived entities.
        """

        super().__init__(coordinator)
        self.spa = spa
        self._attr_unique_id = f"{spa.id}-{entity_name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, spa.id)},
            manufacturer=spa.brand,
            model=spa.model,
        )
        spa_name = get_spa_name(self.spa)
        self._attr_name = f"{spa_name} {entity_name}"

    @property
    def spa_status(self) -> smarttub.SpaState:
        """Retrieve the result of Spa.get_status()."""

        return self.coordinator.data[self.spa.id].get("status")


class SmartTubSensorBase(SmartTubEntity):
    """Base class for SmartTub sensors."""

    def __init__(self, coordinator, spa, sensor_name, state_key):
        """Initialize the entity."""
        super().__init__(coordinator, spa, sensor_name)
        self._state_key = state_key

    @property
    def _state(self):
        """Retrieve the underlying state from the spa."""
        return getattr(self.spa_status, self._state_key)
