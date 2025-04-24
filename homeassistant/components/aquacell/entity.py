"""Aquacell entity."""

from __future__ import annotations

from aioaquacell import Softener

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, INTEGRATION_DEVICE_NAME
from .coordinator import AquacellCoordinator


class AquacellEntity(CoordinatorEntity[AquacellCoordinator]):
    """Representation of an aquacell entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AquacellCoordinator,
        entity_key: str,
        softener_key: str | None = None,
        device_name: str | None = None,
    ) -> None:
        """Initialize the aquacell entity."""
        super().__init__(coordinator)

        self.softener_key = softener_key
        self.entity_key = entity_key

        if softener_key:
            softener = coordinator.data[softener_key]
            self._attr_unique_id = f"{softener_key}-{entity_key}"
            self._attr_device_info = DeviceInfo(
                name=softener.name,
                hw_version=softener.fwVersion,
                identifiers={(DOMAIN, str(softener_key))},
                manufacturer=softener.brand,
                model=softener.ssn,
                serial_number=softener_key,
            )
        else:
            self._attr_unique_id = f"{DOMAIN}-{entity_key}"
            # Use a consistent identifier for the integration-level device
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, DOMAIN)},  # Consistent identifier
                name=device_name or INTEGRATION_DEVICE_NAME,
                manufacturer="Aquacell",
            )

    @property
    def softener(self) -> Softener:
        """Return the softener object."""
        if self.softener_key is None:
            raise ValueError("No softener key defined for this entity")
        return self.coordinator.data[self.softener_key]
