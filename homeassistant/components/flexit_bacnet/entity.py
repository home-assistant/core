"""Base entity for the Flexit Nordic (BACnet) integration."""
from __future__ import annotations

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import PRECISION_HALVES, UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FlexitCoordinator


class FlexitEntity(CoordinatorEntity[FlexitCoordinator]):
    """Defines a Flexit entity."""

    _attr_has_entity_name = True

    _attr_name = None

    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.FAN_ONLY,
    ]

    _attr_preset_modes = [
        PRESET_AWAY,
        PRESET_HOME,
        PRESET_BOOST,
    ]

    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )

    _attr_target_temperature_step: float = PRECISION_HALVES
    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: FlexitCoordinator) -> None:
        """Initialize a Flexit Nordic (BACnet) entity."""
        super().__init__(coordinator=coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.device.serial_number),
            },
            name=coordinator.device.device_name,
            manufacturer="Flexit",
            model="Nordic",
            serial_number=coordinator.device.serial_number,
        )
