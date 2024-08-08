"""Base entity for the flipr entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTRIBUTION, CONF_FLIPR_ID, DOMAIN, MANUFACTURER


class FliprEntity(CoordinatorEntity):
    """Implements a common class elements representing the Flipr component."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: DataUpdateCoordinator, description: EntityDescription
    ) -> None:
        """Initialize Flipr sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        if coordinator.config_entry:
            flipr_id = coordinator.config_entry.data[CONF_FLIPR_ID]
            self._attr_unique_id = f"{flipr_id}-{description.key}"

            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, flipr_id)},
                manufacturer=MANUFACTURER,
                name=f"Flipr {flipr_id}",
            )
