"""Support for SwitchBot Air Conditioner remotes."""
from logging import getLogger
from typing import Any

from switchbot_api import (
    AirConditionerCommands,
    Device,
    FanCommands,
    Remote,
    SwitchBotAPI,
)

import homeassistant.components.climate as FanState
from homeassistant.components.climate import (
    SWING_HORIZONTAL,
    SWING_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from . import SwitchbotCloudData
from .const import DOMAIN
from .coordinator import SwitchBotCoordinator
from .entity import SwitchBotCloudEntity

_LOGGER = getLogger(__name__)

_SWITCHBOT_HVAC_MODES: dict[HVACMode, int] = {
    HVACMode.HEAT_COOL: 1,
    HVACMode.COOL: 2,
    HVACMode.DRY: 3,
    HVACMode.FAN_ONLY: 4,
    HVACMode.HEAT: 5,
}

_SWITCHBOT_FAN_MODES: dict[str, int] = {
    FanState.FAN_AUTO: 1,
    FanState.FAN_LOW: 2,
    FanState.FAN_MEDIUM: 3,
    FanState.FAN_HIGH: 4,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        _async_make_entity(data.api, device, coordinator)
        for device, coordinator in data.devices.climates
    )


class SwitchBotCloudAirConditionner(SwitchBotCloudEntity, ClimateEntity):
    """Representation of a SwitchBot air conditionner."""

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
    _attr_name = None

    async def _do_send_command(
        self,
        hvac_mode: HVACMode | None = None,
        fan_mode: str | None = None,
        temperature: float | None = None,
    ) -> None:
        new_temperature = temperature or self._attr_target_temperature
        new_mode = _SWITCHBOT_HVAC_MODES.get(hvac_mode or self._attr_hvac_mode, 4)
        new_fan_speed = _SWITCHBOT_FAN_MODES.get(fan_mode or self._attr_fan_mode, 1)
        await self.send_command(
            AirConditionerCommands.SET_ALL,
            parameters=f"{new_temperature},{new_mode},{new_fan_speed},on",
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


class SwitchBotCloudFan(SwitchBotCloudEntity, ClimateEntity):
    """Representation of a SwitchBot fan."""

    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.SWING_MODE
    )
    _attr_fan_modes = [FanState.FAN_LOW, FanState.FAN_MEDIUM, FanState.FAN_HIGH]
    _attr_fan_mode = FanState.FAN_LOW
    _attr_swing_modes = [
        SWING_ON,
        SWING_HORIZONTAL,
    ]  # Not sure what to do here, selecting multiple times should allow to cycle through all SWING_HORIZONTAL modes
    _attr_swing_mode = SWING_HORIZONTAL
    _attr_name = None

    # Not sure why I need to set these, but it makes errors without
    _attr_hvac_modes = []
    _attr_hvac_mode = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set target fan mode."""
        match fan_mode:
            case FanState.FAN_LOW:
                await self.send_command(FanCommands.LOW_SPEED)
            case FanState.FAN_MEDIUM:
                await self.send_command(FanCommands.MIDDLE_SPEED)
            case FanState.FAN_HIGH:
                await self.send_command(FanCommands.HIGH_SPEED)
            case _:
                _LOGGER.error("Unsupported fan mode: %s", fan_mode)
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        await self.send_command(FanCommands.SWING)
        self._attr_swing_mode = swing_mode


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> ClimateEntity:
    """Make a SwitchBotCloudAirConditionner or SwitchBotCloudFan."""
    if isinstance(device, Remote) and "Air Conditioner" in device.device_type:
        return SwitchBotCloudAirConditionner(api, device, coordinator)
    if isinstance(device, Remote) and "Fan" in device.device_type:
        return SwitchBotCloudFan(api, device, coordinator)
    raise NotImplementedError(f"Unsupported device type: {device.device_type}")
