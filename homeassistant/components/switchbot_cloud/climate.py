"""Support for SwitchBot Air Conditioner remotes."""

from logging import getLogger
from typing import Any

from switchbot_api import AirConditionerCommands

from homeassistant.components import climate as FanState
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import SwitchbotCloudData
from .const import DOMAIN
from .entity import SwitchBotCloudEntity

_LOGGER = getLogger(__name__)

_SWITCHBOT_HVAC_MODES: dict[HVACMode, int] = {
    HVACMode.AUTO: 1,
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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        SwitchBotCloudAirConditioner(data.api, device, coordinator)
        for device, coordinator in data.devices.climates
    )


class SwitchBotCloudAirConditioner(SwitchBotCloudEntity, ClimateEntity, RestoreEntity):
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
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.HEAT,
        HVACMode.OFF,
    ]
    _attr_hvac_mode = HVACMode.FAN_ONLY
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature = 21
    _attr_target_temperature_step = 1
    _attr_precision = 1
    _attr_name = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        if not (last_state := await self.async_get_last_state()):
            return
        _LOGGER.debug("Last state attributes: %s", last_state.attributes)
        self._attr_hvac_mode = HVACMode(last_state.state)
        self._attr_fan_mode = last_state.attributes.get("fan_mode", self._attr_fan_mode)
        self._attr_target_temperature = last_state.attributes.get(
            "temperature", self._attr_target_temperature
        )

    def _get_mode(self, hvac_mode: HVACMode | None = None) -> int:
        new_hvac_mode = hvac_mode or self._attr_hvac_mode
        _LOGGER.debug(
            "Received hvac_mode: %s (Currently set as %s)",
            hvac_mode,
            self._attr_hvac_mode,
        )
        if new_hvac_mode == HVACMode.OFF:
            return _SWITCHBOT_HVAC_MODES.get(
                self._attr_hvac_mode, _DEFAULT_SWITCHBOT_HVAC_MODE
            )
        return _SWITCHBOT_HVAC_MODES.get(new_hvac_mode, _DEFAULT_SWITCHBOT_HVAC_MODE)

    async def _do_send_command(
        self,
        hvac_mode: HVACMode | None = None,
        fan_mode: str | None = None,
        temperature: float | None = None,
    ) -> None:
        new_temperature = temperature or self._attr_target_temperature
        new_mode = self._get_mode(hvac_mode)
        new_fan_speed = _SWITCHBOT_FAN_MODES.get(
            fan_mode or self._attr_fan_mode, _DEFAULT_SWITCHBOT_FAN_MODE
        )
        new_power_state = "on" if hvac_mode != HVACMode.OFF else "off"
        command = f"{int(new_temperature)},{new_mode},{new_fan_speed},{new_power_state}"
        _LOGGER.debug("Sending command to %s: %s", self._attr_unique_id, command)
        await self.send_api_command(
            AirConditionerCommands.SET_ALL,
            parameters=command,
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
