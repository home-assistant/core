"""Base entity for the eGauge integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import EgaugeDataCoordinator


class EgaugeEntity(CoordinatorEntity[EgaugeDataCoordinator]):
    """Base entity for eGauge sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EgaugeDataCoordinator,
        register_name: str,
    ) -> None:
        """Initialize the eGauge entity."""
        super().__init__(coordinator)

        register_identifier = f"{coordinator.serial_number}_{register_name}"
        register_name = f"{coordinator.hostname} {register_name}"

        # Device info using coordinator's cached data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, register_identifier)},
            name=register_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
            via_device=(DOMAIN, coordinator.serial_number),
        )
