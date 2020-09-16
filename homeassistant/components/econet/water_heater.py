"""Support for Rheem EcoNet water heaters."""
import logging
from typing import Callable, Dict, List, Optional

from pyeconet import EquipmentType
from pyeconet.equipments.water_heater import WaterHeater, WaterHeaterOperationMode
import voluptuous as vol

from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    PLATFORM_SCHEMA,
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_OFF,
    STATE_PERFORMANCE,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .common import get_data_api

_LOGGER = logging.getLogger(__name__)

ATTR_VACATION_START = "next_vacation_start_date"
ATTR_VACATION_END = "next_vacation_end_date"
ATTR_ON_VACATION = "on_vacation"
ATTR_TODAYS_ENERGY_USAGE = "todays_energy_usage"
ATTR_IN_USE = "in_use"

ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"

ATTR_LOWER_TEMP = "lower_temp"
ATTR_UPPER_TEMP = "upper_temp"
ATTR_IS_ENABLED = "is_enabled"

SUPPORT_FLAGS_HEATER = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

ECONET_DATA = "econet"

ECONET_STATE_TO_HA: Dict[WaterHeaterOperationMode, str] = {
    WaterHeaterOperationMode.ENERGY_SAVER: STATE_ECO,
    WaterHeaterOperationMode.GAS: STATE_GAS,
    WaterHeaterOperationMode.HIGH_DEMAND: STATE_HIGH_DEMAND,
    WaterHeaterOperationMode.OFF: STATE_OFF,
    WaterHeaterOperationMode.PERFORMANCE: STATE_PERFORMANCE,
    WaterHeaterOperationMode.ELECTRIC_MODE: STATE_ELECTRIC,
    WaterHeaterOperationMode.HEAT_PUMP_ONLY: STATE_HEAT_PUMP,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], Optional[bool]], None],
) -> None:
    """Set up the config entry."""
    api = get_data_api(hass, config_entry)

    equipment_dict = await api.get_equipment_by_type([EquipmentType.WATER_HEATER])

    async_add_entities(
        [
            EcoNetWaterHeater(water_heater)
            for water_heater in equipment_dict.get(EquipmentType.WATER_HEATER, ())
        ]
    )


class EcoNetWaterHeater(WaterHeaterEntity):
    """Representation of an EcoNet water heater."""

    def __init__(self, water_heater: WaterHeater):
        """Initialize the water heater."""
        self.water_heater = water_heater
        self.supported_modes = self.water_heater.modes
        self.econet_state_to_ha = {}
        self.ha_state_to_econet = {}
        for mode in ECONET_STATE_TO_HA:
            if mode in self.supported_modes:
                self.econet_state_to_ha[mode] = ECONET_STATE_TO_HA.get(mode)
        for key, value in self.econet_state_to_ha.items():
            self.ha_state_to_econet[value] = key
        for mode in self.supported_modes:
            if mode not in ECONET_STATE_TO_HA:
                error = f"Invalid operation mode mapping. {mode} doesn't map. Please report this."
                _LOGGER.error(error)

    async def async_added_to_hass(self) -> None:
        """Subscribe to changes when added to hass."""
        self.water_heater.set_update_callback(self._update_callback)
        self.async_on_remove(lambda: self.water_heater.set_update_callback(None))

    def _update_callback(self):
        """Update the state."""
        self.schedule_update_ha_state(True)

    @property
    def name(self):
        """Return the device name."""
        return self.water_heater.device_name

    @property
    def available(self):
        """Return if the the device is online or not."""
        return self.water_heater.connected

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def device_state_attributes(self):
        """Return the optional device state attributes."""
        data = {}
        data[ATTR_ON_VACATION] = self.water_heater.vacation
        todays_usage = self.water_heater.todays_energy_usage
        if todays_usage:
            data[ATTR_TODAYS_ENERGY_USAGE] = todays_usage
        data[ATTR_IN_USE] = self.water_heater.running

        if self.min_temp is not None:
            data[ATTR_LOWER_TEMP] = round(self.min_temp, 2)
        if self.max_temp is not None:
            data[ATTR_UPPER_TEMP] = round(self.max_temp, 2)
        if self.water_heater.enabled is not None:
            data[ATTR_IS_ENABLED] = self.water_heater.enabled

        return data

    @property
    def current_operation(self):
        """
        Return current operation as one of the following.

        ["eco", "heat_pump", "high_demand", "electric_only"]
        """
        current_op = self.econet_state_to_ha.get(self.water_heater.mode)
        return current_op

    @property
    def operation_list(self):
        """List of available operation modes."""
        op_list = []
        for mode in self.supported_modes:
            ha_mode = self.econet_state_to_ha.get(mode)
            if ha_mode is not None:
                op_list.append(ha_mode)
        return op_list

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS_HEATER

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs[ATTR_TEMPERATURE]
        self.water_heater.set_set_point(target_temp)

        if kwargs.get(ATTR_OPERATION_MODE):
            self.set_operation_mode(kwargs.get(ATTR_OPERATION_MODE))

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        op_mode_to_set = self.ha_state_to_econet.get(operation_mode)
        self.water_heater.set_mode(op_mode_to_set)

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
        """Return False as the data is updated through mqtt."""
        return False
