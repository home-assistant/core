"""Support for SwitchBot Air Conditioner remotes."""

import asyncio
from logging import getLogger
from typing import Any

from switchbot_api import (
    AirConditionerCommands,
    Device,
    Remote,
    SmartRadiatorThermostatCommands,
    SmartRadiatorThermostatMode,
    SwitchBotAPI,
)

from homeassistant.components import climate as FanState
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_TEMPERATURE,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_NONE,
    PRESET_SLEEP,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PRECISION_TENTHS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import SwitchbotCloudData, SwitchBotCoordinator
from .const import DOMAIN, SMART_RADIATOR_THERMOSTAT_AFTER_COMMAND_REFRESH
from .entity import SwitchBotCloudEntity

_LOGGER = getLogger(__name__)

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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        _async_make_entity(data.api, device, coordinator)
        for device, coordinator in data.devices.climates
    )


class SwitchBotCloudAirConditioner(SwitchBotCloudEntity, ClimateEntity, RestoreEntity):
    """Representation of a SwitchBot air conditioner.

    As it is an IR device, we don't know the actual state.
    """

    _attr_assumed_state = True
    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
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

        if not (
            last_state := await self.async_get_last_state()
        ) or last_state.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            return
        _LOGGER.debug("Last state attributes: %s", last_state.attributes)
        self._attr_hvac_mode = HVACMode(last_state.state)
        self._attr_fan_mode = last_state.attributes.get(
            ATTR_FAN_MODE, self._attr_fan_mode
        )
        self._attr_target_temperature = last_state.attributes.get(
            ATTR_TEMPERATURE, self._attr_target_temperature
        )

    def _get_mode(self, hvac_mode: HVACMode | None) -> int:
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

    async def async_turn_off(self) -> None:
        """Turn climate entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        """Turn climate entity on.

        Uses the last known hvac_mode (if not OFF), otherwise defaults to FAN_ONLY.
        """
        hvac_mode = self._attr_hvac_mode
        if hvac_mode == HVACMode.OFF:
            hvac_mode = HVACMode.FAN_ONLY
        await self.async_set_hvac_mode(hvac_mode)


RADIATOR_PRESET_MODE_MAP: dict[str, SmartRadiatorThermostatMode] = {
    PRESET_NONE: SmartRadiatorThermostatMode.OFF,
    PRESET_ECO: SmartRadiatorThermostatMode.ENERGY_SAVING,
    PRESET_BOOST: SmartRadiatorThermostatMode.FAST_HEATING,
    PRESET_COMFORT: SmartRadiatorThermostatMode.COMFORT,
    PRESET_HOME: SmartRadiatorThermostatMode.MANUAL,
}

RADIATOR_HA_PRESET_MODE_MAP = {
    value: key for key, value in RADIATOR_PRESET_MODE_MAP.items()
}


class SwitchBotCloudSmartRadiatorThermostat(SwitchBotCloudEntity, ClimateEntity):
    """Representation of a Smart Radiator Thermostat."""

    _attr_name = None

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )

    _attr_max_temp = 35
    _attr_min_temp = 4
    _attr_target_temperature_step = PRECISION_TENTHS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    _attr_preset_modes = [
        PRESET_NONE,
        PRESET_ECO,
        PRESET_AWAY,
        PRESET_BOOST,
        PRESET_COMFORT,
        PRESET_HOME,
        PRESET_SLEEP,
    ]
    _attr_preset_mode = PRESET_HOME

    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT,
    ]

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        self._attr_target_temperature = kwargs["temperature"]
        await self.send_api_command(
            command=SmartRadiatorThermostatCommands.SET_MANUAL_MODE_TEMPERATURE,
            parameters=str(self._attr_target_temperature),
        )

        await asyncio.sleep(SMART_RADIATOR_THERMOSTAT_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        await self.send_api_command(
            command=SmartRadiatorThermostatCommands.SET_MODE,
            parameters=RADIATOR_PRESET_MODE_MAP[preset_mode].value,
        )
        self._attr_preset_mode = preset_mode

        if self.preset_mode == PRESET_HOME:
            self._attr_target_temperature = self.current_temperature
        else:
            self._attr_target_temperature = None

        await asyncio.sleep(SMART_RADIATOR_THERMOSTAT_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set target hvac mode."""
        if hvac_mode is HVACMode.OFF:
            await self.send_api_command(
                command=SmartRadiatorThermostatCommands.SET_MODE,
                parameters=RADIATOR_PRESET_MODE_MAP[PRESET_NONE].value,
            )
            self._attr_preset_mode = PRESET_NONE
        else:
            await self.send_api_command(
                command=SmartRadiatorThermostatCommands.SET_MODE,
                parameters=RADIATOR_PRESET_MODE_MAP[PRESET_BOOST].value,
            )
            self._attr_preset_mode = PRESET_BOOST
        self._attr_target_temperature = None
        self._attr_hvac_mode = hvac_mode
        await asyncio.sleep(SMART_RADIATOR_THERMOSTAT_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if self.coordinator.data is None:
            return
        mode: int = self.coordinator.data["mode"]
        temperature: str = self.coordinator.data["temperature"]
        self._attr_current_temperature = float(temperature)
        self._attr_preset_mode = RADIATOR_HA_PRESET_MODE_MAP[
            SmartRadiatorThermostatMode(mode)
        ]

        if self.preset_mode in [PRESET_NONE, PRESET_AWAY]:
            self._attr_hvac_mode = HVACMode.OFF
        else:
            self._attr_hvac_mode = HVACMode.HEAT
            if self.preset_mode == PRESET_HOME:
                self._attr_target_temperature = self._attr_current_temperature
        self.async_write_ha_state()


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudAirConditioner | SwitchBotCloudSmartRadiatorThermostat:
    """Make a climate entity."""
    if device.device_type == "Smart Radiator Thermostat":
        return SwitchBotCloudSmartRadiatorThermostat(api, device, coordinator)
    return SwitchBotCloudAirConditioner(api, device, coordinator)
