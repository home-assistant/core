"""Support for Rheem EcoNet water heaters."""
import logging

from pyeconet.equipments import EquipmentType
from pyeconet.equipments.water_heater import WaterHeaterOperationMode

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

from . import EcoNetEntity
from .const import DOMAIN, EQUIPMENT

_LOGGER = logging.getLogger(__name__)

ATTR_IS_ENABLED = "is_enabled"
ATTR_SUPPORTS_LEAK = "supports_leak_detection"
ATTR_SHUT_OFF_VALVE_CLOSED = "shutoff_valve_closed"
ATTR_TANK_HEALTH = "tank_health"
ATTR_TANK_HOT_WATER_AVAILABILITY = "hot_water_availability"
ATTR_OVERRIDE_STATUS = "override_status"
ATTR_ENERGY_USAGE = "todays_energy_usage"

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

    def on_update_received(self):
        """Update the entities when an MQTT message is received in pyeconet."""
        if self._running != self.water_heater.running:
            # Water heater running state has changed so check usage on next update
            self._poll = True
            self._running = self.water_heater.running
        super().on_update_received()

    @property
    def device_state_attributes(self):
        """Return the optional device state attributes."""
        _attr = super().device_state_attributes
        _attr[ATTR_SUPPORTS_LEAK] = self.water_heater.leak_installed
        if self.water_heater.tank_hot_water_availability:
            _attr[
                ATTR_TANK_HOT_WATER_AVAILABILITY
            ] = self.water_heater.tank_hot_water_availability
        if self.water_heater.has_shutoff_valve:
            _attr[ATTR_SHUT_OFF_VALVE_CLOSED] = not self.water_heater.shutoff_valve_open
        if self.water_heater.tank_health:
            _attr[ATTR_TANK_HEALTH] = self.water_heater.tank_health
        if self.water_heater.override_status:
            _attr[ATTR_OVERRIDE_STATUS] = self.water_heater.override_status
        if self.water_heater.todays_energy_usage is not None:
            _attr[ATTR_ENERGY_USAGE] = round(self.water_heater.todays_energy_usage, 2)

        return _attr

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
            if mode is not WaterHeaterOperationMode.UNKNOWN:
                ha_mode = ECONET_STATE_TO_HA[mode]
                op_list.append(ha_mode)
        return op_list

    @property
    def supported_features(self):
        """Return the list of supported features."""
        if len(self.water_heater.modes) > 0:
            if self.water_heater.supports_away:
                return SUPPORT_FLAGS_HEATER | SUPPORT_AWAY_MODE
            return SUPPORT_FLAGS_HEATER
        else:
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
            _LOGGER.error("An operation mode must be provided")

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
        self._poll = False

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self.water_heater.set_away_mode(True)

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self.water_heater.set_away_mode(False)
