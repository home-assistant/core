"""Support for OSO Energy water heaters."""
from typing import Any

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OSOEnergyEntity
from .const import DOMAIN

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
HEATER_MIN_TEMP = 10
HEATER_MAX_TEMP = 80
MANUFACTURER = "OSO Energy"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OSO Energy heater based on a config entry."""
    osoenergy = hass.data[DOMAIN][entry.entry_id]
    devices = osoenergy.session.device_list.get("water_heater")
    entities = []
    if devices:
        for dev in devices:
            entities.append(OSOEnergyWaterHeater(osoenergy, dev))
    async_add_entities(entities, True)


class OSOEnergyWaterHeater(
    OSOEnergyEntity[OSOEnergyWaterHeaterData], WaterHeaterEntity
):
    """OSO Energy Water Heater Device."""

    _attr_name = None
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id)},
            manufacturer=MANUFACTURER,
            model=self.device.device_type,
            name=self.device.device_name,
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.device.available

    @property
    def current_operation(self) -> str:
        """Return current operation."""
        status = self.device.current_operation
        if status == "off":
            return STATE_OFF

        optimization_mode = self.device.optimization_mode.lower()
        heater_mode = self.device.heater_mode.lower()
        if optimization_mode in CURRENT_OPERATION_MAP:
            return CURRENT_OPERATION_MAP[optimization_mode].get(
                heater_mode, STATE_ELECTRIC
            )

        return CURRENT_OPERATION_MAP["default"].get(heater_mode, STATE_ELECTRIC)

    @property
    def current_temperature(self) -> float:
        """Return the current temperature of the heater."""
        return self.device.current_temperature

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self.device.target_temperature

    @property
    def target_temperature_high(self) -> float:
        """Return the temperature we try to reach."""
        return self.device.target_temperature_high

    @property
    def target_temperature_low(self) -> float:
        """Return the temperature we try to reach."""
        return self.device.target_temperature_low

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.device.min_temperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.device.max_temperature

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on hotwater."""
        await self.osoenergy.hotwater.turn_on(self.device, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off hotwater."""
        await self.osoenergy.hotwater.turn_off(self.device, True)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temperature = int(kwargs.get("temperature", self.target_temperature))
        profile = [target_temperature] * 24

        await self.osoenergy.hotwater.set_profile(self.device, profile)

    async def async_update(self) -> None:
        """Update all Node data from Hive."""
        await self.osoenergy.session.update_data()
        self.device = await self.osoenergy.hotwater.get_water_heater(self.device)
