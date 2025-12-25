"""Support for Tuya Climate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

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
from .const import (
    CELSIUS_ALIASES,
    FAHRENHEIT_ALIASES,
    TUYA_DISCOVERY_NEW,
    DeviceCategory,
    DPCode,
)
from .entity import TuyaEntity
from .models import (
    DeviceWrapper,
    DPCodeBooleanWrapper,
    DPCodeEnumWrapper,
    DPCodeIntegerWrapper,
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


@dataclass(kw_only=True)
class _SwingModeWrapper(DeviceWrapper):
    """Wrapper for managing climate swing mode operations across multiple DPCodes."""

    on_off: DPCodeBooleanWrapper | None = None
    horizontal: DPCodeBooleanWrapper | None = None
    vertical: DPCodeBooleanWrapper | None = None
    options: list[str]

    @classmethod
    def find_dpcode(cls, device: CustomerDevice) -> Self | None:
        """Find and return a _SwingModeWrapper for the given DP codes."""
        on_off = DPCodeBooleanWrapper.find_dpcode(
            device, (DPCode.SWING, DPCode.SHAKE), prefer_function=True
        )
        horizontal = DPCodeBooleanWrapper.find_dpcode(
            device, DPCode.SWITCH_HORIZONTAL, prefer_function=True
        )
        vertical = DPCodeBooleanWrapper.find_dpcode(
            device, DPCode.SWITCH_VERTICAL, prefer_function=True
        )
        if on_off or horizontal or vertical:
            options = [SWING_OFF]
            if on_off:
                options.append(SWING_ON)
            if horizontal:
                options.append(SWING_HORIZONTAL)
            if vertical:
                options.append(SWING_VERTICAL)
            return cls(
                on_off=on_off,
                horizontal=horizontal,
                vertical=vertical,
                options=options,
            )
        return None

    def read_device_status(self, device: CustomerDevice) -> str | None:
        """Read the device swing mode."""
        if self.on_off and self.on_off.read_device_status(device):
            return SWING_ON

        horizontal = (
            self.horizontal.read_device_status(device) if self.horizontal else None
        )
        vertical = self.vertical.read_device_status(device) if self.vertical else None
        if horizontal and vertical:
            return SWING_BOTH
        if horizontal:
            return SWING_HORIZONTAL
        if vertical:
            return SWING_VERTICAL

        return SWING_OFF

    def get_update_commands(
        self, device: CustomerDevice, value: str
    ) -> list[dict[str, Any]]:
        """Set new target swing operation."""
        commands = []
        if self.on_off:
            commands.extend(self.on_off.get_update_commands(device, value == SWING_ON))

        if self.vertical:
            commands.extend(
                self.vertical.get_update_commands(
                    device, value in (SWING_BOTH, SWING_VERTICAL)
                )
            )
        if self.horizontal:
            commands.extend(
                self.horizontal.get_update_commands(
                    device, value in (SWING_BOTH, SWING_HORIZONTAL)
                )
            )
        return commands


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


def _get_temperature_wrapper(
    wrappers: list[DPCodeIntegerWrapper | None], aliases: set[str]
) -> DPCodeIntegerWrapper | None:
    """Return first wrapper with matching unit."""
    return next(
        (
            wrapper
            for wrapper in wrappers
            if wrapper is not None
            and (unit := wrapper.type_information.unit)
            and unit.lower() in aliases
        ),
        None,
    )


def _get_temperature_wrappers(
    device: CustomerDevice, system_temperature_unit: UnitOfTemperature
) -> tuple[DPCodeIntegerWrapper | None, DPCodeIntegerWrapper | None, UnitOfTemperature]:
    """Get temperature wrappers for current and set temperatures."""
    # Get all possible temperature dpcodes
    temp_current = DPCodeIntegerWrapper.find_dpcode(
        device, (DPCode.TEMP_CURRENT, DPCode.UPPER_TEMP)
    )
    temp_current_f = DPCodeIntegerWrapper.find_dpcode(
        device, (DPCode.TEMP_CURRENT_F, DPCode.UPPER_TEMP_F)
    )
    temp_set = DPCodeIntegerWrapper.find_dpcode(
        device, DPCode.TEMP_SET, prefer_function=True
    )
    temp_set_f = DPCodeIntegerWrapper.find_dpcode(
        device, DPCode.TEMP_SET_F, prefer_function=True
    )

    # If there is a temp unit convert dpcode, override empty units
    if (
        temp_unit_convert := DPCodeEnumWrapper.find_dpcode(
            device, DPCode.TEMP_UNIT_CONVERT
        )
    ) is not None:
        for wrapper in (temp_current, temp_current_f, temp_set, temp_set_f):
            if wrapper is not None and not wrapper.type_information.unit:
                wrapper.type_information.unit = temp_unit_convert.read_device_status(
                    device
                )

    # Get wrappers for celsius and fahrenheit
    # We need to check the unit of measurement
    current_celsius = _get_temperature_wrapper(
        [temp_current, temp_current_f], CELSIUS_ALIASES
    )
    current_fahrenheit = _get_temperature_wrapper(
        [temp_current_f, temp_current], FAHRENHEIT_ALIASES
    )
    set_celsius = _get_temperature_wrapper([temp_set, temp_set_f], CELSIUS_ALIASES)
    set_fahrenheit = _get_temperature_wrapper(
        [temp_set_f, temp_set], FAHRENHEIT_ALIASES
    )

    # Return early if we have the right wrappers for the system unit
    if system_temperature_unit == UnitOfTemperature.FAHRENHEIT:
        if (
            (current_fahrenheit and set_fahrenheit)
            or (current_fahrenheit and not set_celsius)
            or (set_fahrenheit and not current_celsius)
        ):
            return current_fahrenheit, set_fahrenheit, UnitOfTemperature.FAHRENHEIT
    if (
        (current_celsius and set_celsius)
        or (current_celsius and not set_fahrenheit)
        or (set_celsius and not current_fahrenheit)
    ):
        return current_celsius, set_celsius, UnitOfTemperature.CELSIUS

    # If we don't have the right wrappers, return whatever is available
    # and assume system unit
    if system_temperature_unit == UnitOfTemperature.FAHRENHEIT:
        return (
            temp_current_f or temp_current,
            temp_set_f or temp_set,
            UnitOfTemperature.FAHRENHEIT,
        )

    return (
        temp_current or temp_current_f,
        temp_set or temp_set_f,
        UnitOfTemperature.CELSIUS,
    )


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
                        swing_wrapper=_SwingModeWrapper.find_dpcode(device),
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
        swing_wrapper: _SwingModeWrapper | None,
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
        self._switch_wrapper = switch_wrapper
        self._target_humidity_wrapper = target_humidity_wrapper
        self._attr_temperature_unit = temperature_unit

        # Get integer type data for the dpcode to set temperature, use
        # it to define min, max & step temperatures
        if self._set_temperature:
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
            self._attr_max_temp = self._set_temperature.max_value
            self._attr_min_temp = self._set_temperature.min_value
            self._attr_target_temperature_step = self._set_temperature.value_step

        # Determine HVAC modes
        self._attr_hvac_modes: list[HVACMode] = []
        self._hvac_to_tuya = {}
        if hvac_mode_wrapper:
            self._attr_hvac_modes = [HVACMode.OFF]
            unknown_hvac_modes: list[str] = []
            for tuya_mode in hvac_mode_wrapper.options:
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
            self._attr_min_humidity = round(target_humidity_wrapper.min_value)
            self._attr_max_humidity = round(target_humidity_wrapper.max_value)

        # Determine fan modes
        if fan_mode_wrapper:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = fan_mode_wrapper.options

        # Determine swing modes
        if swing_wrapper:
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE
            self._attr_swing_modes = swing_wrapper.options

        if switch_wrapper:
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        commands = []
        if self._switch_wrapper:
            commands.extend(
                self._switch_wrapper.get_update_commands(
                    self.device, hvac_mode != HVACMode.OFF
                )
            )
        if self._hvac_mode_wrapper and hvac_mode in self._hvac_to_tuya:
            commands.extend(
                self._hvac_mode_wrapper.get_update_commands(
                    self.device, self._hvac_to_tuya[hvac_mode]
                )
            )
        await self._async_send_commands(commands)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        await self._async_send_wrapper_updates(self._hvac_mode_wrapper, preset_mode)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self._async_send_wrapper_updates(self._fan_mode_wrapper, fan_mode)

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self._async_send_wrapper_updates(self._target_humidity_wrapper, humidity)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        await self._async_send_wrapper_updates(self._swing_wrapper, swing_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self._async_send_wrapper_updates(
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
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac mode."""
        # If the switch is off, hvac mode is off.
        switch_status: bool | None
        if (switch_status := self._read_wrapper(self._switch_wrapper)) is False:
            return HVACMode.OFF

        # If we don't have a mode wrapper, return switch only mode.
        if self._hvac_mode_wrapper is None:
            if switch_status is True:
                return self.entity_description.switch_only_hvac_mode
            return None

        # If we do have a mode wrapper, check if the mode maps to an HVAC mode.
        if (hvac_status := self._read_wrapper(self._hvac_mode_wrapper)) is None:
            return None
        return TUYA_HVAC_TO_HA.get(hvac_status)

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
    def swing_mode(self) -> str | None:
        """Return swing mode."""
        return self._read_wrapper(self._swing_wrapper)

    async def async_turn_on(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        await self._async_send_wrapper_updates(self._switch_wrapper, True)

    async def async_turn_off(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        await self._async_send_wrapper_updates(self._switch_wrapper, False)
