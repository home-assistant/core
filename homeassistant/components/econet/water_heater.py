"""Support for Rheem EcoNet water heaters."""

from datetime import timedelta
import logging
from typing import Any

from pyeconet.equipment import EquipmentType
from pyeconet.equipment.water_heater import WaterHeaterOperationMode

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EQUIPMENT
from .entity import EcoNetEntity

SCAN_INTERVAL = timedelta(hours=1)

_LOGGER = logging.getLogger(__name__)

ECONET_STATE_TO_HA = {
    WaterHeaterOperationMode.ENERGY_SAVING: STATE_ECO,
    WaterHeaterOperationMode.HIGH_DEMAND: STATE_HIGH_DEMAND,
    WaterHeaterOperationMode.OFF: STATE_OFF,
    WaterHeaterOperationMode.HEAT_PUMP_ONLY: STATE_HEAT_PUMP,
    WaterHeaterOperationMode.ELECTRIC_MODE: STATE_ELECTRIC,
    WaterHeaterOperationMode.GAS: STATE_GAS,
    WaterHeaterOperationMode.PERFORMANCE: STATE_PERFORMANCE,
}
HA_STATE_TO_ECONET = {value: key for key, value in ECONET_STATE_TO_HA.items()}

SUPPORT_FLAGS_HEATER = (
    WaterHeaterEntityFeature.TARGET_TEMPERATURE
    | WaterHeaterEntityFeature.OPERATION_MODE
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EcoNet water heater based on a config entry."""
    equipment = hass.data[DOMAIN][EQUIPMENT][entry.entry_id]
    async_add_entities(
        [
            EcoNetWaterHeater(water_heater)
            for water_heater in equipment[EquipmentType.WATER_HEATER]
        ],
        update_before_add=True,
    )


class EcoNetWaterHeater(EcoNetEntity, WaterHeaterEntity):
    """Define an Econet water heater."""

    _attr_should_poll = True  # Override False default from EcoNetEntity
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT

    def __init__(self, water_heater):
        """Initialize."""
        super().__init__(water_heater)
        self.water_heater = water_heater

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._econet.away

    @property
    def current_operation(self):
        """Return current operation."""
        econet_mode = self.water_heater.mode
        _current_op = STATE_OFF
        if econet_mode is not None:
            _current_op = ECONET_STATE_TO_HA[econet_mode]

        return _current_op

    @property
    def operation_list(self):
        """List of available operation modes."""
        econet_modes = self.water_heater.modes
        op_list = []
        for mode in econet_modes:
            if (
                mode is not WaterHeaterOperationMode.UNKNOWN
                and mode is not WaterHeaterOperationMode.VACATION
            ):
                ha_mode = ECONET_STATE_TO_HA[mode]
                op_list.append(ha_mode)
        return op_list

    @property
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Return the list of supported features."""
        if self.water_heater.modes:
            if self.water_heater.supports_away:
                return SUPPORT_FLAGS_HEATER | WaterHeaterEntityFeature.AWAY_MODE
            return SUPPORT_FLAGS_HEATER
        if self.water_heater.supports_away:
            return (
                WaterHeaterEntityFeature.TARGET_TEMPERATURE
                | WaterHeaterEntityFeature.AWAY_MODE
            )
        return WaterHeaterEntityFeature.TARGET_TEMPERATURE

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (target_temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self.water_heater.set_set_point(target_temp)
        else:
            _LOGGER.error("A target temperature must be provided")

    def set_operation_mode(self, operation_mode: str) -> None:
        """Set operation mode."""
        op_mode_to_set = HA_STATE_TO_ECONET.get(operation_mode)
        if op_mode_to_set is not None:
            self.water_heater.set_mode(op_mode_to_set)
        else:
            _LOGGER.error("Invalid operation mode: %s", operation_mode)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.water_heater.set_point

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self.water_heater.set_point_limits[0]

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.water_heater.set_point_limits[1]

    async def async_update(self) -> None:
        """Get the latest energy usage."""
        await self.water_heater.get_energy_usage()
        await self.water_heater.get_water_usage()

    def turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        self.water_heater.set_away_mode(True)

    def turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        self.water_heater.set_away_mode(False)
