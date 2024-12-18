"""Support for SwitchBot Air Conditioner remotes."""

from typing import Any

from switchbot_api import AirConditionerCommands

import homeassistant.components.climate as FanState
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SwitchbotCloudData
from .const import DOMAIN
from .entity import SwitchBotCloudEntity

_SWITCHBOT_HVAC_MODES: dict[HVACMode, int] = {
    HVACMode.HEAT_COOL: 1,
    HVACMode.COOL: 2,
    HVACMode.DRY: 3,
    HVACMode.FAN_ONLY: 4,
    HVACMode.HEAT: 5,
}

_DEFAULT_SWITCHBOT_HVAC_MODE = _SWITCHBOT_HVAC_MODES[HVACMode.FAN_ONLY]

_SWITCHBOT_FAN_MODES: dict[str, int] = {
    FanState.FAN_AUTO: 1,
    FanState.FAN_LOW: 2,
    FanState.FAN_MEDIUM: 3,
    FanState.FAN_HIGH: 4,
}

_DEFAULT_SWITCHBOT_FAN_MODE = _SWITCHBOT_FAN_MODES[FanState.FAN_AUTO]


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        SwitchBotCloudAirConditioner(data.api, device, coordinator)
        for device, coordinator in data.devices.climates
    )


class SwitchBotCloudAirConditioner(SwitchBotCloudEntity, ClimateEntity):
    """Representation of a SwitchBot air conditioner.

    As it is an IR device, we don't know the actual state.
    """

    _attr_assumed_state = True
    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )
    _attr_fan_modes = [
        FanState.FAN_AUTO,
        FanState.FAN_LOW,
        FanState.FAN_MEDIUM,
        FanState.FAN_HIGH,
    ]
    _attr_fan_mode = FanState.FAN_AUTO
    _attr_hvac_modes = [
        HVACMode.HEAT_COOL,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.HEAT,
    ]
    _attr_hvac_mode = HVACMode.FAN_ONLY
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature = 21
    _attr_target_temperature_step = 1
    _attr_precision = 1
    _attr_name = None

    async def _do_send_command(
        self,
        hvac_mode: HVACMode | None = None,
        fan_mode: str | None = None,
        temperature: float | None = None,
    ) -> None:
        new_temperature = temperature or self._attr_target_temperature
        new_mode = _SWITCHBOT_HVAC_MODES.get(
            hvac_mode or self._attr_hvac_mode, _DEFAULT_SWITCHBOT_HVAC_MODE
        )
        new_fan_speed = _SWITCHBOT_FAN_MODES.get(
            fan_mode or self._attr_fan_mode, _DEFAULT_SWITCHBOT_FAN_MODE
        )
        await self.send_api_command(
            AirConditionerCommands.SET_ALL,
            parameters=f"{int(new_temperature)},{new_mode},{new_fan_speed},on",
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set target hvac mode."""
        await self._do_send_command(hvac_mode=hvac_mode)
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set target fan mode."""
        await self._do_send_command(fan_mode=fan_mode)
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self._do_send_command(temperature=temperature)
        self._attr_target_temperature = temperature
        self.async_write_ha_state()
