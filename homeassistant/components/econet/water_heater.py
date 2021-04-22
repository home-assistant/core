"""Support for Rheem EcoNet water heaters."""
import logging

from pyeconet.equipment import EquipmentType
from pyeconet.equipment.water_heater import WaterHeaterOperationMode

from homeassistant.components.water_heater import (
    ATTR_TEMPERATURE,
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_OFF,
    STATE_PERFORMANCE,
    SUPPORT_AWAY_MODE,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterEntity,
)
from homeassistant.core import callback

from . import EcoNetEntity
from .const import DOMAIN, EQUIPMENT

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

SUPPORT_FLAGS_HEATER = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up EcoNet water heater based on a config entry."""
    equipment = hass.data[DOMAIN][EQUIPMENT][entry.entry_id]
    async_add_entities(
        [
            EcoNetWaterHeater(water_heater)
            for water_heater in equipment[EquipmentType.WATER_HEATER]
        ],
    )


class EcoNetWaterHeater(EcoNetEntity, WaterHeaterEntity):
    """Define a Econet water heater."""

    def __init__(self, water_heater):
        """Initialize."""
        super().__init__(water_heater)
        self._running = water_heater.running
        self._poll = True
        self.water_heater = water_heater
        self.econet_state_to_ha = {}
        self.ha_state_to_econet = {}

    @callback
    def on_update_received(self):
        """Update was pushed from the ecoent API."""
        if self._running != self.water_heater.running:
            # Water heater running state has changed so check usage on next update
            self._poll = True
            self._running = self.water_heater.running
        self.async_write_ha_state()

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
    def supported_features(self):
        """Return the list of supported features."""
        if self.water_heater.modes:
            if self.water_heater.supports_away:
                return SUPPORT_FLAGS_HEATER | SUPPORT_AWAY_MODE
            return SUPPORT_FLAGS_HEATER
        if self.water_heater.supports_away:
            return SUPPORT_TARGET_TEMPERATURE | SUPPORT_AWAY_MODE
        return SUPPORT_TARGET_TEMPERATURE

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is not None:
            self.water_heater.set_set_point(target_temp)
        else:
            _LOGGER.error("A target temperature must be provided")

    def set_operation_mode(self, operation_mode):
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

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return self._poll

    async def async_update(self):
        """Get the latest energy usage."""
        await self.water_heater.get_energy_usage()
        await self.water_heater.get_water_usage()
        self.async_write_ha_state()
        self._poll = False

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self.water_heater.set_away_mode(True)

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self.water_heater.set_away_mode(False)
