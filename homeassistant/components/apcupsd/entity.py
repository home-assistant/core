"""Base entity for APCUPSd integration."""

from __future__ import annotations

from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEPRECATED_SENSORS, DOMAIN
from .coordinator import APCUPSdCoordinator


class APCUPSdEntity(CoordinatorEntity[APCUPSdCoordinator]):
    """Base entity for APCUPSd integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: APCUPSdCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the APCUPSd entity."""
        super().__init__(coordinator, context=description.key.upper())

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_device_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    async def async_added_to_hass(self) -> None:
        """Handle when entity is added to Home Assistant.

        If this is a deprecated sensor entity, create a repair issue to guide
        the user to disable it.
        """
        await super().async_added_to_hass()
        if not self.enabled:
            return

        if issue_key := DEPRECATED_SENSORS.get(self.entity_description.key):
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"{issue_key}_{self.entity_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=issue_key,
                translation_placeholders={
                    "entity_name": str(self.name or self.entity_id),
                    "entity_id": self.entity_id,
                },
            )

    async def async_will_remove_from_hass(self) -> None:
        """Handle when entity will be removed from Home Assistant."""
        if issue_key := DEPRECATED_SENSORS.get(self.entity_description.key):
            ir.async_delete_issue(self.hass, DOMAIN, f"{issue_key}_{self.entity_id}")
        await super().async_will_remove_from_hass()
