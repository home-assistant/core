"""Platform for climate integration."""

from __future__ import annotations

from typing import Any

from whirlpool.aircon import Aircon, FanSpeed as AirconFanSpeed, Mode as AirconMode

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    SWING_HORIZONTAL,
    SWING_OFF,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WhirlpoolConfigEntry
from .entity import WhirlpoolEntity

PARALLEL_UPDATES = 1

AIRCON_MODE_MAP = {
    AirconMode.Cool: HVACMode.COOL,
    AirconMode.Heat: HVACMode.HEAT,
    AirconMode.Fan: HVACMode.FAN_ONLY,
}

HVAC_MODE_TO_AIRCON_MODE = {v: k for k, v in AIRCON_MODE_MAP.items()}

AIRCON_FANSPEED_MAP = {
    AirconFanSpeed.Off: FAN_OFF,
    AirconFanSpeed.Auto: FAN_AUTO,
    AirconFanSpeed.Low: FAN_LOW,
    AirconFanSpeed.Medium: FAN_MEDIUM,
    AirconFanSpeed.High: FAN_HIGH,
}

FAN_MODE_TO_AIRCON_FANSPEED = {v: k for k, v in AIRCON_FANSPEED_MAP.items()}

SUPPORTED_MAX_TEMP = 30
SUPPORTED_MIN_TEMP = 16
SUPPORTED_SWING_MODES = [SWING_HORIZONTAL, SWING_OFF]
SUPPORTED_TARGET_TEMPERATURE_STEP = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WhirlpoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    appliances_manager = config_entry.runtime_data
    async_add_entities(AirConEntity(aircon) for aircon in appliances_manager.aircons)


class AirConEntity(WhirlpoolEntity, ClimateEntity):
    """Representation of an air conditioner."""

    _appliance: Aircon

    _attr_name = None
    _attr_fan_modes = [*FAN_MODE_TO_AIRCON_FANSPEED.keys()]
    _attr_hvac_modes = [HVACMode.OFF, *HVAC_MODE_TO_AIRCON_MODE.keys()]
    _attr_max_temp = SUPPORTED_MAX_TEMP
    _attr_min_temp = SUPPORTED_MIN_TEMP
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_swing_modes = SUPPORTED_SWING_MODES
    _attr_target_temperature_step = SUPPORTED_TARGET_TEMPERATURE_STEP
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._appliance.get_current_temp()

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self._appliance.get_temp()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        AirConEntity._check_service_request(
            await self._appliance.set_temp(kwargs.get(ATTR_TEMPERATURE))
        )

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return self._appliance.get_current_humidity()

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current operation ie. heat, cool, fan."""
        if not self._appliance.get_power_on():
            return HVACMode.OFF

        mode: AirconMode = self._appliance.get_mode()
        return AIRCON_MODE_MAP.get(mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            AirConEntity._check_service_request(
                await self._appliance.set_power_on(False)
            )
            return

        mode = HVAC_MODE_TO_AIRCON_MODE[hvac_mode]
        AirConEntity._check_service_request(await self._appliance.set_mode(mode))
        if not self._appliance.get_power_on():
            AirConEntity._check_service_request(
                await self._appliance.set_power_on(True)
            )

    @property
    def fan_mode(self) -> str:
        """Return the fan setting."""
        fanspeed = self._appliance.get_fanspeed()
        return AIRCON_FANSPEED_MAP.get(fanspeed, FAN_OFF)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        fanspeed = FAN_MODE_TO_AIRCON_FANSPEED[fan_mode]
        AirConEntity._check_service_request(
            await self._appliance.set_fanspeed(fanspeed)
        )

    @property
    def swing_mode(self) -> str:
        """Return the swing setting."""
        return SWING_HORIZONTAL if self._appliance.get_h_louver_swing() else SWING_OFF

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        AirConEntity._check_service_request(
            await self._appliance.set_h_louver_swing(swing_mode == SWING_HORIZONTAL)
        )

    async def async_turn_on(self) -> None:
        """Turn device on."""
        AirConEntity._check_service_request(await self._appliance.set_power_on(True))

    async def async_turn_off(self) -> None:
        """Turn device off."""
        AirConEntity._check_service_request(await self._appliance.set_power_on(False))
