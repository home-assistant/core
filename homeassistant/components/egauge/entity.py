"""Base entity for the eGauge integration."""

from __future__ import annotations

from egauge_async.json import RegisterInfo

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EgaugeDataCoordinator


class EgaugeEntity(CoordinatorEntity[EgaugeDataCoordinator]):
    """Base entity for eGauge sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EgaugeDataCoordinator,
        register_name: str,
        register_info: RegisterInfo,
    ) -> None:
        """Initialize the eGauge entity."""
        super().__init__(coordinator)
        self._register_name = register_name

        # Device info using coordinator's cached data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial_number)},
            name=coordinator.hostname,
            manufacturer="eGauge Systems",
            model="eGauge Energy Monitor",
            serial_number=coordinator.serial_number,
        )
