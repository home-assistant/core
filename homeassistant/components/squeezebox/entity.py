"""Base class for Squeezebox Sensor entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATUS_QUERY_UUID
from .coordinator import LMSStatusDataUpdateCoordinator


class LMSStatusEntity(CoordinatorEntity[LMSStatusDataUpdateCoordinator]):
    """Defines a base status sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LMSStatusDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize status sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.key.replace(" ", "_")
        self._attr_unique_id = (
            f"{coordinator.data[STATUS_QUERY_UUID]}_{description.key}"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data[STATUS_QUERY_UUID])},
        )
