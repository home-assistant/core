"""Platform for climate integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from toshiba_ac.device import (
    ToshibaAcDevice,
    ToshibaAcFanMode,
    ToshibaAcMeritA,
    ToshibaAcMode,
    ToshibaAcPowerSelection,
    ToshibaAcSelfCleaning,
    ToshibaAcStatus,
    ToshibaAcSwingMode,
)
from toshiba_ac.utils import pretty_enum_name

from homeassistant.components.climate import (
    FAN_OFF,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .const import DOMAIN
from .entity import ToshibaAcStateEntity
from .feature_list import get_feature_by_name, get_feature_list

_LOGGER = logging.getLogger(__name__)

TOSHIBA_TO_HVAC_MODE = {
    ToshibaAcMode.AUTO: HVACMode.AUTO,
    ToshibaAcMode.COOL: HVACMode.COOL,
    ToshibaAcMode.HEAT: HVACMode.HEAT,
    ToshibaAcMode.DRY: HVACMode.DRY,
    ToshibaAcMode.FAN: HVACMode.FAN_ONLY,
}

HVAC_MODE_TO_TOSHIBA = {v: k for k, v in TOSHIBA_TO_HVAC_MODE.items()}


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add climate for passed config_entry in HA."""
    device_manager = hass.data[DOMAIN][config_entry.entry_id]
    new_entities = []

    devices = await device_manager.get_devices()
    for device in devices:
        climate_entity = ToshibaClimate(device)
        new_entities.append(climate_entity)

    if new_entities:
        _LOGGER.info("Adding %d %s", len(new_entities), "climates")
        async_add_devices(new_entities)


class ToshibaClimate(ToshibaAcStateEntity, ClimateEntity):
    """Provides a Toshiba climates."""

    # This is the main entity for the device
    _attr_has_entity_name = True
    _attr_name = None

    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_target_temperature_step = 1
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, toshiba_device: ToshibaAcDevice) -> None:
        """Initialize the climate."""
        super().__init__(toshiba_device)

        self._attr_unique_id = f"{self._device.ac_unique_id}_climate"
        self._attr_fan_modes = get_feature_list(self._device.supported.ac_fan_mode)
        self._attr_swing_modes = get_feature_list(self._device.supported.ac_swing_mode)

    @property
    def is_on(self):
        """Return True if the device is on or completely off."""
        return self._device.ac_status == ToshibaAcStatus.ON

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        set_temperature = kwargs[ATTR_TEMPERATURE]

        # if hasattr(self._device, "ac_merit_a") and ToshibaAcMeritA.HEATING_8C in self._device.supported.ac_merit_a:
        if (
            hasattr(self._device, "ac_merit_a")
            and self._device.ac_merit_a == ToshibaAcMeritA.HEATING_8C
        ):
            # upper limit for target temp
            if set_temperature > 13:
                set_temperature = 13
            # lower limit for target temp
            elif set_temperature < 5:
                set_temperature = 5
        elif set_temperature > 30:
            # upper limit for target temp
            set_temperature = 30
        elif set_temperature < 17:
            # lower limit for target temp
            set_temperature = 17

        await self._device.set_ac_temperature(set_temperature)

    # PRESET MODE / POWER SETTING

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        if self._device.ac_self_cleaning == ToshibaAcSelfCleaning.ON:
            return "cleaning"

        if not self.is_on:
            return None

        return pretty_enum_name(self._device.ac_power_selection)

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires SUPPORT_PRESET_MODE.
        """
        return get_feature_list(self._device.supported.ac_power_selection)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.info("Toshiba Climate setting preset_mode: %s", preset_mode)

        feature_list_id = get_feature_by_name(
            list(ToshibaAcPowerSelection), preset_mode
        )
        if feature_list_id is not None:
            await self._device.set_ac_power_selection(feature_list_id)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        if not self.is_on:
            return HVACMode.OFF

        return TOSHIBA_TO_HVAC_MODE[self._device.ac_mode]

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        available_modes = [HVACMode.OFF]
        for toshiba_mode, hvac_mode in TOSHIBA_TO_HVAC_MODE.items():
            if toshiba_mode in self._device.supported.ac_mode:
                available_modes.append(hvac_mode)
        return available_modes

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        _LOGGER.info("Toshiba Climate setting hvac_mode: %s", hvac_mode)

        if hvac_mode == HVACMode.OFF:
            await self._device.set_ac_status(ToshibaAcStatus.OFF)
        else:
            if not self.is_on:
                await self._device.set_ac_status(ToshibaAcStatus.ON)
            await self._device.set_ac_mode(HVAC_MODE_TO_TOSHIBA[hvac_mode])

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        _LOGGER.info("Toshiba Climate setting fan_mode: %s", fan_mode)
        if fan_mode == FAN_OFF:
            await self._device.set_ac_fan_mode(ToshibaAcStatus.OFF)
        else:
            if not self.is_on:
                await self._device.set_ac_status(ToshibaAcStatus.ON)
            fan_mode = fan_mode.title().replace("_", " ")
            feature_list_id = get_feature_by_name(list(ToshibaAcFanMode), fan_mode)
            if feature_list_id is not None:
                await self._device.set_ac_fan_mode(feature_list_id)

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return pretty_enum_name(self._device.ac_fan_mode)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        swing_mode = swing_mode.title().replace("_", " ")
        feature_list_id = get_feature_by_name(list(ToshibaAcSwingMode), swing_mode)
        if feature_list_id is not None:
            await self._device.set_ac_swing_mode(feature_list_id)

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        return pretty_enum_name(self._device.ac_swing_mode)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.ac_indoor_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._device.ac_temperature

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if (
            hasattr(self._device, "ac_merit_a")
            and self._device.ac_merit_a == ToshibaAcMeritA.HEATING_8C
        ):
            return 5
        return 17

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if (
            hasattr(self._device, "ac_merit_a")
            and self._device.ac_merit_a == ToshibaAcMeritA.HEATING_8C
        ):
            return 13
        return 30

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes.

        Implemented by platform classes. Convention for attribute names
        is lowercase snake_case.
        """
        return {
            "merit_a_feature": self._device.ac_merit_a.name,
            "merit_b_feature": self._device.ac_merit_b.name,
            "air_pure_ion": self._device.ac_air_pure_ion.name,
            "self_cleaning": self._device.ac_self_cleaning.name,
            "outdoor_temperature": self._device.ac_outdoor_temperature,
        }
