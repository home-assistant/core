"""The HWAM Smart Control Thermostat."""

import re

from pystove import DATA_BURN_LEVEL, DATA_PHASE, DATA_ROOM_TEMPERATURE

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

from .const import DOMAIN, LOGGER
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

    _PATTERN_BURN_LEVEL: re.Pattern = re.compile(r"Level (\d)")

    _attr_has_entity_name = True
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
        self._attr_unique_id = f"{coordinator.device_id}-airbox"
        self._attr_device_info = self.coordinator.device_info()
        self._attr_hvac_mode = None
        self._attr_preset_mode = None

    @property
    def name(self) -> str:
        """Name of the entity."""
        return "Airbox"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        LOGGER.debug(data)
        if data[DATA_PHASE] == "Standby":
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.IDLE
        else:
            self._attr_hvac_mode = HVACMode.HEAT
            self._attr_hvac_action = HVACAction.HEATING

        self._attr_preset_mode = f"Level {data[DATA_BURN_LEVEL]}"
        self._attr_current_temperature = data[DATA_ROOM_TEMPERATURE]
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        if self.coordinator.data[DATA_PHASE] == "Standby":
            LOGGER.info(f"Turning on stove {self.coordinator.api.name}")
            await self.coordinator.api.start()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn the entity on."""
        if hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode, aka the burn level.

        Parameter
        ----------
        preset_mode:
            Supported values are: "Level [0-5]"
        """
        assert preset_mode in self._attr_preset_modes
        match = self._PATTERN_BURN_LEVEL.match(preset_mode)
        if match:
            level = match.group(1)
            if self.coordinator.data[DATA_BURN_LEVEL] != level:
                LOGGER.info(
                    f"Setting burn level of {self.coordinator.api.name} to {level}"
                )
                if await self.coordinator.api.set_burn_level(level):
                    self.coordinator.data[DATA_BURN_LEVEL] = level
        else:
            LOGGER.error(f"Invalid preset_mode = '{preset_mode}'")
