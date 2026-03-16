"""Support for WaterFurnace climate entity."""

from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WaterFurnaceConfigEntry
from .const import DOMAIN
from .coordinator import WaterFurnaceCoordinator
from .entity import WaterFurnaceEntity

PARALLEL_UPDATES = 0

# Maps ActiveSettings.mode string to HVACMode
ACTIVE_MODE_TO_HVAC: dict[str, HVACMode] = {
    "Off": HVACMode.OFF,
    "Auto": HVACMode.AUTO,
    "Cool": HVACMode.COOL,
    "Heat": HVACMode.HEAT,
    "E-Heat": HVACMode.HEAT,
}

# Maps WFReading.mode string to HVACAction
FURNACE_MODE_TO_ACTION: dict[str, HVACAction] = {
    "Standby": HVACAction.IDLE,
    "Fan Only": HVACAction.FAN,
    "Cooling 1": HVACAction.COOLING,
    "Cooling 2": HVACAction.COOLING,
    "Reheat": HVACAction.HEATING,
    "Heating 1": HVACAction.HEATING,
    "Heating 2": HVACAction.HEATING,
    "E-Heat": HVACAction.HEATING,
    "Aux Heat": HVACAction.HEATING,
    "Lockout": HVACAction.OFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WaterFurnaceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WaterFurnace climate from a config entry."""
    async_add_entities(
        WaterFurnaceClimate(device_data.realtime)
        for device_data in config_entry.runtime_data.values()
    )


class WaterFurnaceClimate(WaterFurnaceEntity, ClimateEntity):
    """Read-only climate entity for WaterFurnace geothermal systems."""

    _attr_name = None
    _attr_supported_features = ClimateEntityFeature(0)
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT

    def __init__(self, coordinator: WaterFurnaceCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unit}_climate"

    @property
    def current_temperature(self) -> float | None:
        """Return the current room temperature."""
        return self.coordinator.data.tstatroomtemp

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self.coordinator.data.tstatrelativehumidity

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        return ACTIVE_MODE_TO_HVAC.get(self.coordinator.data.activesettings.mode)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        return FURNACE_MODE_TO_ACTION.get(self.coordinator.data.mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode — not supported (read-only)."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="set_hvac_mode_not_supported",
        )
