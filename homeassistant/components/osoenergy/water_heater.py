"""Support for OSO Energy water heaters."""

from typing import Any

from apyosoenergyapi import OSOEnergy
from apyosoenergyapi.helper.const import OSOEnergyWaterHeaterData

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_HIGH_DEMAND,
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import OSOEnergyEntity

CURRENT_OPERATION_MAP: dict[str, Any] = {
    "default": {
        "off": STATE_OFF,
        "powersave": STATE_OFF,
        "extraenergy": STATE_HIGH_DEMAND,
    },
    "oso": {
        "auto": STATE_ECO,
        "off": STATE_OFF,
        "powersave": STATE_OFF,
        "extraenergy": STATE_HIGH_DEMAND,
    },
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OSO Energy heater based on a config entry."""
    osoenergy = hass.data[DOMAIN][entry.entry_id]
    devices = osoenergy.session.device_list.get("water_heater")
    if not devices:
        return
    async_add_entities((OSOEnergyWaterHeater(osoenergy, dev) for dev in devices), True)


class OSOEnergyWaterHeater(
    OSOEnergyEntity[OSOEnergyWaterHeaterData], WaterHeaterEntity
):
    """OSO Energy Water Heater Device."""

    _attr_name = None
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        instance: OSOEnergy,
        entity_data: OSOEnergyWaterHeaterData,
    ) -> None:
        """Initialize the OSO Energy water heater."""
        super().__init__(instance, entity_data)
        self._attr_unique_id = entity_data.device_id

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.entity_data.available

    @property
    def current_operation(self) -> str:
        """Return current operation."""
        status = self.entity_data.current_operation
        if status == "off":
            return STATE_OFF

        optimization_mode = self.entity_data.optimization_mode.lower()
        heater_mode = self.entity_data.heater_mode.lower()
        if optimization_mode in CURRENT_OPERATION_MAP:
            return CURRENT_OPERATION_MAP[optimization_mode].get(
                heater_mode, STATE_ELECTRIC
            )

        return CURRENT_OPERATION_MAP["default"].get(heater_mode, STATE_ELECTRIC)

    @property
    def current_temperature(self) -> float:
        """Return the current temperature of the heater."""
        return self.entity_data.current_temperature

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self.entity_data.target_temperature

    @property
    def target_temperature_high(self) -> float:
        """Return the temperature we try to reach."""
        return self.entity_data.target_temperature_high

    @property
    def target_temperature_low(self) -> float:
        """Return the temperature we try to reach."""
        return self.entity_data.target_temperature_low

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.entity_data.min_temperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.entity_data.max_temperature

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on hotwater."""
        await self.osoenergy.hotwater.turn_on(self.entity_data, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off hotwater."""
        await self.osoenergy.hotwater.turn_off(self.entity_data, True)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temperature = int(kwargs.get("temperature", self.target_temperature))
        profile = [target_temperature] * 24

        await self.osoenergy.hotwater.set_profile(self.entity_data, profile)

    async def async_update(self) -> None:
        """Update all Node data from Hive."""
        await self.osoenergy.session.update_data()
        self.entity_data = await self.osoenergy.hotwater.get_water_heater(
            self.entity_data
        )
