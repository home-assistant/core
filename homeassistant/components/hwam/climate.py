"""The HWAM Smart Control Thermostat."""

from hwamsmartctrl.stovedata import StoveData

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StoveDataUpdateCoordinator

CLIMATES: tuple[ClimateEntityDescription, ...] = (
    ClimateEntityDescription(key="climate", name="Thermostat"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure the thermostat."""
    coordinator: StoveDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(StoveClimateEntity(coordinator) for description in CLIMATES)


class StoveClimateEntity(CoordinatorEntity[StoveDataUpdateCoordinator], ClimateEntity):
    """The thermostat entity."""

    _attr_supported_features = (
        ClimateEntityFeature.TURN_ON | ClimateEntityFeature.PRESET_MODE
    )

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = [
        "Level 0",
        "Level 1",
        "Level 2",
        "Level 3",
        "Level 4",
        "Level 5",
    ]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: StoveDataUpdateCoordinator) -> None:
        """Set up the instance."""
        super().__init__(coordinator)
        self._attr_hvac_mode = None
        self._attr_preset_mode = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data: StoveData = self.coordinator.data
        if data.phase == 5:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.IDLE
        else:
            self._attr_hvac_mode = HVACMode.HEAT
            self._attr_hvac_action = HVACAction.HEATING

        self._attr_preset_mode = f"Level {data.burn_level}"
        self._attr_current_temperature = data.room_temperature
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.coordinator.api.start_combustion()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn the entity on."""
        if hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()
