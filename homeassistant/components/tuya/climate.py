"""Support for Tuya Climate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.climate import (
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_ON,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode, DPType
from .entity import TuyaEntity
from .models import (
    DPCodeBooleanWrapper,
    DPCodeEnumWrapper,
    DPCodeIntegerWrapper,
    find_dpcode,
)

TUYA_HVAC_TO_HA = {
    "auto": HVACMode.HEAT_COOL,
    "cold": HVACMode.COOL,
    "freeze": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "hot": HVACMode.HEAT,
    "manual": HVACMode.HEAT_COOL,
    "wet": HVACMode.DRY,
    "wind": HVACMode.FAN_ONLY,
}


class _RoundedIntegerWrapper(DPCodeIntegerWrapper):
    """An integer that always rounds its value."""

    def read_device_status(self, device: CustomerDevice) -> int | None:
        """Read and round the device status."""
        if (value := super().read_device_status(device)) is None:
            return None
        return round(value)


@dataclass(frozen=True, kw_only=True)
class TuyaClimateEntityDescription(ClimateEntityDescription):
    """Describe an Tuya climate entity."""

    switch_only_hvac_mode: HVACMode


CLIMATE_DESCRIPTIONS: dict[DeviceCategory, TuyaClimateEntityDescription] = {
    DeviceCategory.DBL: TuyaClimateEntityDescription(
        key="dbl",
        switch_only_hvac_mode=HVACMode.HEAT,
    ),
    DeviceCategory.KT: TuyaClimateEntityDescription(
        key="kt",
        switch_only_hvac_mode=HVACMode.COOL,
    ),
    DeviceCategory.QN: TuyaClimateEntityDescription(
        key="qn",
        switch_only_hvac_mode=HVACMode.HEAT,
    ),
    DeviceCategory.RS: TuyaClimateEntityDescription(
        key="rs",
        switch_only_hvac_mode=HVACMode.HEAT,
    ),
    DeviceCategory.WK: TuyaClimateEntityDescription(
        key="wk",
        switch_only_hvac_mode=HVACMode.HEAT_COOL,
    ),
    DeviceCategory.WKF: TuyaClimateEntityDescription(
        key="wkf",
        switch_only_hvac_mode=HVACMode.HEAT,
    ),
}


def _get_temperature_wrappers(
    device: CustomerDevice, system_temperature_unit: UnitOfTemperature
) -> tuple[DPCodeIntegerWrapper | None, DPCodeIntegerWrapper | None, UnitOfTemperature]:
    """Get temperature wrappers for current and set temperatures."""
    current_temperature_wrapper: DPCodeIntegerWrapper | None = None
    set_temperature_wrapper: DPCodeIntegerWrapper | None = None

    # Default to System Temperature Unit
    temperature_unit = system_temperature_unit

    # If both temperature values for celsius and fahrenheit are present,
    # use whatever the device is set to, with a fallback to celsius.
    prefered_temperature_unit = None
    if all(
        dpcode in device.status
        for dpcode in (DPCode.TEMP_CURRENT, DPCode.TEMP_CURRENT_F)
    ) or all(
        dpcode in device.status for dpcode in (DPCode.TEMP_SET, DPCode.TEMP_SET_F)
    ):
        prefered_temperature_unit = UnitOfTemperature.CELSIUS
        if any(
            "f" in device.status[dpcode].lower()
            for dpcode in (DPCode.C_F, DPCode.TEMP_UNIT_CONVERT)
            if isinstance(device.status.get(dpcode), str)
        ):
            prefered_temperature_unit = UnitOfTemperature.FAHRENHEIT

    # Figure out current temperature, use preferred unit or what is available
    celsius_type = find_dpcode(
        device, (DPCode.TEMP_CURRENT, DPCode.UPPER_TEMP), dptype=DPType.INTEGER
    )
    fahrenheit_type = find_dpcode(
        device,
        (DPCode.TEMP_CURRENT_F, DPCode.UPPER_TEMP_F),
        dptype=DPType.INTEGER,
    )
    if fahrenheit_type and (
        prefered_temperature_unit == UnitOfTemperature.FAHRENHEIT
        or (prefered_temperature_unit == UnitOfTemperature.CELSIUS and not celsius_type)
    ):
        temperature_unit = UnitOfTemperature.FAHRENHEIT
        current_temperature_wrapper = DPCodeIntegerWrapper(
            fahrenheit_type.dpcode, fahrenheit_type
        )
    elif celsius_type:
        temperature_unit = UnitOfTemperature.CELSIUS
        current_temperature_wrapper = DPCodeIntegerWrapper(
            celsius_type.dpcode, celsius_type
        )

    # Figure out setting temperature, use preferred unit or what is available
    celsius_type = find_dpcode(
        device, DPCode.TEMP_SET, dptype=DPType.INTEGER, prefer_function=True
    )
    fahrenheit_type = find_dpcode(
        device, DPCode.TEMP_SET_F, dptype=DPType.INTEGER, prefer_function=True
    )
    if fahrenheit_type and (
        prefered_temperature_unit == UnitOfTemperature.FAHRENHEIT
        or (prefered_temperature_unit == UnitOfTemperature.CELSIUS and not celsius_type)
    ):
        set_temperature_wrapper = DPCodeIntegerWrapper(
            fahrenheit_type.dpcode, fahrenheit_type
        )
    elif celsius_type:
        set_temperature_wrapper = DPCodeIntegerWrapper(
            celsius_type.dpcode, celsius_type
        )

    return current_temperature_wrapper, set_temperature_wrapper, temperature_unit


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya climate dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya climate."""
        entities: list[TuyaClimateEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if device and device.category in CLIMATE_DESCRIPTIONS:
                temperature_wrappers = _get_temperature_wrappers(
                    device, hass.config.units.temperature_unit
                )
                entities.append(
                    TuyaClimateEntity(
                        device,
                        manager,
                        CLIMATE_DESCRIPTIONS[device.category],
                        current_humidity_wrapper=_RoundedIntegerWrapper.find_dpcode(
                            device, DPCode.HUMIDITY_CURRENT
                        ),
                        current_temperature_wrapper=temperature_wrappers[0],
                        fan_mode_wrapper=DPCodeEnumWrapper.find_dpcode(
                            device,
                            (DPCode.FAN_SPEED_ENUM, DPCode.LEVEL, DPCode.WINDSPEED),
                            prefer_function=True,
                        ),
                        hvac_mode_wrapper=DPCodeEnumWrapper.find_dpcode(
                            device, DPCode.MODE, prefer_function=True
                        ),
                        set_temperature_wrapper=temperature_wrappers[1],
                        swing_wrapper=DPCodeBooleanWrapper.find_dpcode(
                            device, (DPCode.SWING, DPCode.SHAKE), prefer_function=True
                        ),
                        swing_h_wrapper=DPCodeBooleanWrapper.find_dpcode(
                            device, DPCode.SWITCH_HORIZONTAL, prefer_function=True
                        ),
                        swing_v_wrapper=DPCodeBooleanWrapper.find_dpcode(
                            device, DPCode.SWITCH_VERTICAL, prefer_function=True
                        ),
                        switch_wrapper=DPCodeBooleanWrapper.find_dpcode(
                            device, DPCode.SWITCH, prefer_function=True
                        ),
                        target_humidity_wrapper=_RoundedIntegerWrapper.find_dpcode(
                            device, DPCode.HUMIDITY_SET, prefer_function=True
                        ),
                        temperature_unit=temperature_wrappers[2],
                    )
                )
        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaClimateEntity(TuyaEntity, ClimateEntity):
    """Tuya Climate Device."""

    _hvac_to_tuya: dict[str, str]
    entity_description: TuyaClimateEntityDescription
    _attr_name = None

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaClimateEntityDescription,
        *,
        current_humidity_wrapper: _RoundedIntegerWrapper | None,
        current_temperature_wrapper: DPCodeIntegerWrapper | None,
        fan_mode_wrapper: DPCodeEnumWrapper | None,
        hvac_mode_wrapper: DPCodeEnumWrapper | None,
        set_temperature_wrapper: DPCodeIntegerWrapper | None,
        swing_wrapper: DPCodeBooleanWrapper | None,
        swing_h_wrapper: DPCodeBooleanWrapper | None,
        swing_v_wrapper: DPCodeBooleanWrapper | None,
        switch_wrapper: DPCodeBooleanWrapper | None,
        target_humidity_wrapper: _RoundedIntegerWrapper | None,
        temperature_unit: UnitOfTemperature,
    ) -> None:
        """Determine which values to use."""
        self._attr_target_temperature_step = 1.0
        self.entity_description = description

        super().__init__(device, device_manager)
        self._current_humidity_wrapper = current_humidity_wrapper
        self._current_temperature = current_temperature_wrapper
        self._fan_mode_wrapper = fan_mode_wrapper
        self._hvac_mode_wrapper = hvac_mode_wrapper
        self._set_temperature = set_temperature_wrapper
        self._swing_wrapper = swing_wrapper
        self._swing_h_wrapper = swing_h_wrapper
        self._swing_v_wrapper = swing_v_wrapper
        self._switch_wrapper = switch_wrapper
        self._target_humidity_wrapper = target_humidity_wrapper
        self._attr_temperature_unit = temperature_unit

        # Get integer type data for the dpcode to set temperature, use
        # it to define min, max & step temperatures
        if self._set_temperature:
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
            self._attr_max_temp = self._set_temperature.type_information.max_scaled
            self._attr_min_temp = self._set_temperature.type_information.min_scaled
            self._attr_target_temperature_step = (
                self._set_temperature.type_information.step_scaled
            )

        # Determine HVAC modes
        self._attr_hvac_modes: list[HVACMode] = []
        self._hvac_to_tuya = {}
        if hvac_mode_wrapper:
            self._attr_hvac_modes = [HVACMode.OFF]
            unknown_hvac_modes: list[str] = []
            for tuya_mode in hvac_mode_wrapper.type_information.range:
                if tuya_mode in TUYA_HVAC_TO_HA:
                    ha_mode = TUYA_HVAC_TO_HA[tuya_mode]
                    self._hvac_to_tuya[ha_mode] = tuya_mode
                    self._attr_hvac_modes.append(ha_mode)
                else:
                    unknown_hvac_modes.append(tuya_mode)

            if unknown_hvac_modes:  # Tuya modes are presets instead of hvac_modes
                self._attr_hvac_modes.append(description.switch_only_hvac_mode)
                self._attr_preset_modes = unknown_hvac_modes
                self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
        elif switch_wrapper:
            self._attr_hvac_modes = [
                HVACMode.OFF,
                description.switch_only_hvac_mode,
            ]

        # Determine dpcode to use for setting the humidity
        if target_humidity_wrapper:
            self._attr_supported_features |= ClimateEntityFeature.TARGET_HUMIDITY
            self._attr_min_humidity = round(
                target_humidity_wrapper.type_information.min_scaled
            )
            self._attr_max_humidity = round(
                target_humidity_wrapper.type_information.max_scaled
            )

        # Determine fan modes
        if fan_mode_wrapper:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = fan_mode_wrapper.type_information.range

        # Determine swing modes
        if swing_wrapper or swing_h_wrapper or swing_v_wrapper:
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE
            self._attr_swing_modes = [SWING_OFF]
            if swing_wrapper:
                self._attr_swing_modes.append(SWING_ON)

            if swing_h_wrapper:
                self._attr_swing_modes.append(SWING_HORIZONTAL)

            if swing_v_wrapper:
                self._attr_swing_modes.append(SWING_VERTICAL)

        if switch_wrapper:
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        commands = []
        if self._switch_wrapper:
            commands.append(
                self._switch_wrapper.get_update_command(
                    self.device, hvac_mode != HVACMode.OFF
                )
            )
        if self._hvac_mode_wrapper and hvac_mode in self._hvac_to_tuya:
            commands.append(
                self._hvac_mode_wrapper.get_update_command(
                    self.device, self._hvac_to_tuya[hvac_mode]
                )
            )
        await self._async_send_commands(commands)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        await self._async_send_dpcode_update(self._hvac_mode_wrapper, preset_mode)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self._async_send_dpcode_update(self._fan_mode_wrapper, fan_mode)

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self._async_send_dpcode_update(self._target_humidity_wrapper, humidity)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        commands = []
        if self._swing_wrapper:
            commands.append(
                self._swing_wrapper.get_update_command(
                    self.device, swing_mode == SWING_ON
                )
            )
        if self._swing_v_wrapper:
            commands.append(
                self._swing_v_wrapper.get_update_command(
                    self.device, swing_mode in (SWING_BOTH, SWING_VERTICAL)
                )
            )
        if self._swing_h_wrapper:
            commands.append(
                self._swing_h_wrapper.get_update_command(
                    self.device, swing_mode in (SWING_BOTH, SWING_HORIZONTAL)
                )
            )
        if commands:
            await self._async_send_commands(commands)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self._async_send_dpcode_update(
            self._set_temperature, kwargs[ATTR_TEMPERATURE]
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._read_wrapper(self._current_temperature)

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._read_wrapper(self._current_humidity_wrapper)

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature currently set to be reached."""
        return self._read_wrapper(self._set_temperature)

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity currently set to be reached."""
        return self._read_wrapper(self._target_humidity_wrapper)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac mode."""
        # If the switch is off, hvac mode is off as well.
        # Unless the switch doesn't exists of course...
        if (switch_status := self._read_wrapper(self._switch_wrapper)) is False:
            return HVACMode.OFF

        # If the mode is known and maps to an HVAC mode, return it.
        if (mode := self._read_wrapper(self._hvac_mode_wrapper)) and (
            hvac_mode := TUYA_HVAC_TO_HA.get(mode)
        ):
            return hvac_mode

        # If hvac_mode is unknown, return the switch only mode.
        if switch_status:
            return self.entity_description.switch_only_hvac_mode
        return HVACMode.OFF

    @property
    def preset_mode(self) -> str | None:
        """Return preset mode."""
        if self._hvac_mode_wrapper is None:
            return None

        mode = self._read_wrapper(self._hvac_mode_wrapper)
        if mode in TUYA_HVAC_TO_HA:
            return None

        return mode

    @property
    def fan_mode(self) -> str | None:
        """Return fan mode."""
        return self._read_wrapper(self._fan_mode_wrapper)

    @property
    def swing_mode(self) -> str:
        """Return swing mode."""
        if self._read_wrapper(self._swing_wrapper):
            return SWING_ON

        horizontal = self._read_wrapper(self._swing_h_wrapper)
        vertical = self._read_wrapper(self._swing_v_wrapper)
        if horizontal and vertical:
            return SWING_BOTH
        if horizontal:
            return SWING_HORIZONTAL
        if vertical:
            return SWING_VERTICAL

        return SWING_OFF

    async def async_turn_on(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        await self._async_send_dpcode_update(self._switch_wrapper, True)

    async def async_turn_off(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        await self._async_send_dpcode_update(self._switch_wrapper, False)
