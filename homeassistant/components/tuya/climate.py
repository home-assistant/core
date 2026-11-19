"""Support for Tuya Climate."""

import asyncio
from dataclasses import dataclass
from typing import Any, cast, override

from tuya_device_handlers.definition.climate import (
    ClimateDefinition,
    get_default_definition,
    get_infrared_ac_definition,
)
from tuya_device_handlers.helpers.homeassistant import (
    TuyaClimateHVACMode,
    TuyaClimateSwingMode,
    TuyaUnitOfTemperature,
)
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_ON,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
    RestoreClimate,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import TUYA_DISCOVERY_NEW, DeviceCategory
from .coordinator import TuyaConfigEntry
from .entity import TuyaEntity, TuyaEntityDescription
from .util import get_temperature_unit

_TUYA_TO_HA_HVACMODE_MAPPINGS = {
    TuyaClimateHVACMode.OFF: HVACMode.OFF,
    TuyaClimateHVACMode.HEAT: HVACMode.HEAT,
    TuyaClimateHVACMode.COOL: HVACMode.COOL,
    TuyaClimateHVACMode.FAN_ONLY: HVACMode.FAN_ONLY,
    TuyaClimateHVACMode.DRY: HVACMode.DRY,
    TuyaClimateHVACMode.HEAT_COOL: HVACMode.HEAT_COOL,
    TuyaClimateHVACMode.AUTO: HVACMode.AUTO,
}
_HA_TO_TUYA_HVACMODE_MAPPINGS = {v: k for k, v in _TUYA_TO_HA_HVACMODE_MAPPINGS.items()}

_TUYA_TO_HA_SWING_MAPPINGS = {
    TuyaClimateSwingMode.BOTH: SWING_BOTH,
    TuyaClimateSwingMode.HORIZONTAL: SWING_HORIZONTAL,
    TuyaClimateSwingMode.OFF: SWING_OFF,
    TuyaClimateSwingMode.ON: SWING_ON,
    TuyaClimateSwingMode.VERTICAL: SWING_VERTICAL,
}
_HA_TO_TUYA_SWING_MAPPINGS = {v: k for k, v in _TUYA_TO_HA_SWING_MAPPINGS.items()}

_HA_TO_TUYA_TEMPERATURE = {
    UnitOfTemperature.CELSIUS: TuyaUnitOfTemperature.CELSIUS,
    UnitOfTemperature.FAHRENHEIT: TuyaUnitOfTemperature.FAHRENHEIT,
}


@dataclass(frozen=True, kw_only=True)
class TuyaClimateEntityDescription(TuyaEntityDescription, ClimateEntityDescription):
    """Describe an Tuya climate entity."""

    switch_only_hvac_mode: HVACMode


CLIMATE_DESCRIPTIONS: dict[DeviceCategory, TuyaClimateEntityDescription] = {
    DeviceCategory.DBL: TuyaClimateEntityDescription(
        key="",
        switch_only_hvac_mode=HVACMode.HEAT,
    ),
    DeviceCategory.KT: TuyaClimateEntityDescription(
        key="",
        switch_only_hvac_mode=HVACMode.COOL,
    ),
    DeviceCategory.MJJ: TuyaClimateEntityDescription(
        key="",
        switch_only_hvac_mode=HVACMode.HEAT,
    ),
    DeviceCategory.QN: TuyaClimateEntityDescription(
        key="",
        switch_only_hvac_mode=HVACMode.HEAT,
    ),
    DeviceCategory.RS: TuyaClimateEntityDescription(
        key="",
        switch_only_hvac_mode=HVACMode.HEAT,
    ),
    DeviceCategory.WK: TuyaClimateEntityDescription(
        key="",
        switch_only_hvac_mode=HVACMode.HEAT_COOL,
    ),
    DeviceCategory.WKF: TuyaClimateEntityDescription(
        key="",
        switch_only_hvac_mode=HVACMode.HEAT,
    ),
    # IR air conditioners have dedicated power datapoints instead of a switch,
    # so `switch_only_hvac_mode` is not used for them.
    DeviceCategory.INFRARED_AC: TuyaClimateEntityDescription(
        key="",
        switch_only_hvac_mode=HVACMode.HEAT_COOL,
    ),
}


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
        entities: list[TuyaClimateEntity | TuyaInfraredAcEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if (description := CLIMATE_DESCRIPTIONS.get(device.category)) is None:
                continue

            if device.category == DeviceCategory.INFRARED_AC:
                if definition := get_infrared_ac_definition(device):
                    entities.append(
                        TuyaInfraredAcEntity(device, manager, description, definition)
                    )
                continue

            if definition := get_default_definition(
                device,
                _HA_TO_TUYA_TEMPERATURE.get(
                    hass.config.units.temperature_unit,
                    TuyaUnitOfTemperature.CELSIUS,
                ),
            ):
                entities.append(
                    TuyaClimateEntity(device, manager, description, definition)
                )
        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaClimateEntity(TuyaEntity, ClimateEntity):
    """Tuya Climate Device."""

    entity_description: TuyaClimateEntityDescription
    _attr_name = None
    _attr_target_temperature_step = 1.0

    _current_temp_unit: UnitOfTemperature | None = None
    _set_temp_unit: UnitOfTemperature | None = None

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaClimateEntityDescription,
        definition: ClimateDefinition,
    ) -> None:
        """Determine which values to use."""
        super().__init__(device, device_manager, description)
        self._current_humidity_wrapper = definition.current_humidity_wrapper
        self._current_temperature = definition.current_temperature_wrapper
        self._fan_mode_wrapper = definition.fan_mode_wrapper
        self._hvac_mode_wrapper = definition.hvac_mode_wrapper
        self._preset_wrapper = definition.preset_wrapper
        self._set_temperature = definition.set_temperature_wrapper
        self._swing_wrapper = definition.swing_wrapper
        self._switch_wrapper = definition.switch_wrapper
        self._target_humidity_wrapper = definition.target_humidity_wrapper
        self._attr_native_temperature_unit = definition.temperature_unit

        if self._current_temperature:
            self._current_temp_unit = get_temperature_unit(
                device, self._current_temperature.native_unit
            )
        if self._set_temperature:
            self._set_temp_unit = get_temperature_unit(
                device, self._set_temperature.native_unit
            )

        # Get integer type data for the dpcode to set temperature, use
        # it to define min, max & step temperatures
        if definition.set_temperature_wrapper:
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
            self._attr_max_temp = definition.set_temperature_wrapper.max_value
            self._attr_min_temp = definition.set_temperature_wrapper.min_value
            self._attr_target_temperature_step = (
                definition.set_temperature_wrapper.value_step
            )

        # Determine HVAC modes
        self._attr_hvac_modes = []
        if definition.hvac_mode_wrapper:
            self._attr_hvac_modes = [HVACMode.OFF]
            for tuya_mode in cast(
                list[TuyaClimateHVACMode], definition.hvac_mode_wrapper.options
            ):
                if (
                    ha_mode := _TUYA_TO_HA_HVACMODE_MAPPINGS.get(tuya_mode)
                ) and ha_mode != HVACMode.OFF:
                    # OFF is always added first
                    self._attr_hvac_modes.append(ha_mode)

        elif definition.switch_wrapper:
            self._attr_hvac_modes = [
                HVACMode.OFF,
                description.switch_only_hvac_mode,
            ]

        # Determine preset modes (ignore if empty options)
        if definition.preset_wrapper and definition.preset_wrapper.options:
            self._attr_preset_modes = definition.preset_wrapper.options
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
            if description.switch_only_hvac_mode not in self._attr_hvac_modes:
                self._attr_hvac_modes.append(description.switch_only_hvac_mode)

        # Determine dpcode to use for setting the humidity
        if definition.target_humidity_wrapper:
            self._attr_supported_features |= ClimateEntityFeature.TARGET_HUMIDITY
            self._attr_min_humidity = round(
                definition.target_humidity_wrapper.min_value
            )
            self._attr_max_humidity = round(
                definition.target_humidity_wrapper.max_value
            )

        # Determine fan modes
        if definition.fan_mode_wrapper:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = definition.fan_mode_wrapper.options

        # Determine swing modes
        if definition.swing_wrapper:
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE
            self._attr_swing_modes = [
                ha_swing_mode
                for tuya_swing_mode in cast(
                    list[TuyaClimateSwingMode], definition.swing_wrapper.options
                )
                if (ha_swing_mode := _TUYA_TO_HA_SWING_MAPPINGS.get(tuya_swing_mode))
            ]

        if definition.switch_wrapper:
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        commands = []
        if self._switch_wrapper:
            commands.extend(
                self._switch_wrapper.get_update_commands(
                    self.device, hvac_mode != HVACMode.OFF
                )
            )
        if (
            self._hvac_mode_wrapper
            and (tuya_mode := _HA_TO_TUYA_HVACMODE_MAPPINGS.get(hvac_mode))
            and tuya_mode in self._hvac_mode_wrapper.options
        ):
            commands.extend(
                self._hvac_mode_wrapper.get_update_commands(self.device, tuya_mode)
            )
        elif (
            hvac_mode == self.entity_description.switch_only_hvac_mode
            and self._preset_wrapper
            and self._preset_wrapper.options
            and self._read_wrapper(self._preset_wrapper) is None
        ):
            # The mode DP holds an HVAC value such as "off": select a preset.
            commands.extend(
                self._preset_wrapper.get_update_commands(
                    self.device, self._preset_wrapper.options[0]
                )
            )
        await self._async_send_commands(commands)

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        await self._async_send_wrapper_updates(self._preset_wrapper, preset_mode)

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self._async_send_wrapper_updates(self._fan_mode_wrapper, fan_mode)

    @override
    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self._async_send_wrapper_updates(self._target_humidity_wrapper, humidity)

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        if tuya_mode := _HA_TO_TUYA_SWING_MAPPINGS.get(swing_mode):
            await self._async_send_wrapper_updates(self._swing_wrapper, tuya_mode)

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        value = kwargs[ATTR_TEMPERATURE]
        if self._set_temp_unit and self._set_temp_unit != self.native_temperature_unit:
            value = TemperatureConverter.convert(
                value, self.native_temperature_unit, self._set_temp_unit
            )
        await self._async_send_wrapper_updates(self._set_temperature, value)

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        value = self._read_wrapper(self._current_temperature)
        if (
            value is not None
            and self._current_temp_unit
            and self._current_temp_unit != self.native_temperature_unit
        ):
            return TemperatureConverter.convert(
                value, self._current_temp_unit, self.native_temperature_unit
            )
        return value

    @property
    @override
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._read_wrapper(self._current_humidity_wrapper)

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the temperature currently set to be reached."""
        value = self._read_wrapper(self._set_temperature)
        if (
            value is not None
            and self._set_temp_unit
            and self._set_temp_unit != self.native_temperature_unit
        ):
            return TemperatureConverter.convert(
                value, self._set_temp_unit, self.native_temperature_unit
            )
        return value

    @property
    @override
    def target_humidity(self) -> int | None:
        """Return the humidity currently set to be reached."""
        return self._read_wrapper(self._target_humidity_wrapper)

    @property
    @override
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
        if tuya_mode := self._read_wrapper(self._hvac_mode_wrapper):
            return _TUYA_TO_HA_HVACMODE_MAPPINGS.get(tuya_mode)

        # The mode DP holds a preset rather than an HVAC mode.
        if self._read_wrapper(self._preset_wrapper) is not None:
            return self.entity_description.switch_only_hvac_mode
        return None

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return preset mode."""
        return self._read_wrapper(self._preset_wrapper)

    @property
    @override
    def fan_mode(self) -> str | None:
        """Return fan mode."""
        return self._read_wrapper(self._fan_mode_wrapper)

    @property
    @override
    def swing_mode(self) -> str | None:
        """Return swing mode."""
        tuya_value = self._read_wrapper(self._swing_wrapper)
        return _TUYA_TO_HA_SWING_MAPPINGS.get(tuya_value) if tuya_value else None

    @override
    async def async_turn_on(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        await self._async_send_wrapper_updates(self._switch_wrapper, True)

    @override
    async def async_turn_off(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        await self._async_send_wrapper_updates(self._switch_wrapper, False)


class TuyaInfraredAcEntity(TuyaEntity, RestoreClimate, ClimateEntity):
    """Tuya infrared air conditioner.

    IR air conditioners are virtual devices driven through an IR hub. They are
    controlled with write-only commands (`PowerOn`, `PowerOff`, `M`, `T` and
    `F`), but the hub reports the resulting state as `power`, `mode`, `temp`
    and `wind` status datapoints, which are used to keep the state in sync.
    The locally tracked state is restored after a restart until a push arrives.
    """

    entity_description: TuyaClimateEntityDescription
    _attr_name = None
    _attr_target_temperature_step = 1.0

    _last_on_hvac_mode: HVACMode

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaClimateEntityDescription,
        definition: ClimateDefinition,
    ) -> None:
        """Initialize the entity."""
        super().__init__(device, device_manager, description)
        self._fan_mode_wrapper = definition.fan_mode_wrapper
        self._hvac_mode_wrapper = definition.hvac_mode_wrapper
        self._set_temperature = definition.set_temperature_wrapper
        self._switch_wrapper = definition.switch_wrapper
        self._attr_native_temperature_unit = definition.temperature_unit

        self._attr_hvac_modes = [HVACMode.OFF]
        if self._hvac_mode_wrapper:
            for tuya_mode in cast(
                list[TuyaClimateHVACMode], self._hvac_mode_wrapper.options
            ):
                if (ha_mode := _TUYA_TO_HA_HVACMODE_MAPPINGS.get(tuya_mode)) and (
                    ha_mode != HVACMode.OFF
                ):
                    self._attr_hvac_modes.append(ha_mode)

        if self._set_temperature:
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
            self._attr_max_temp = self._set_temperature.max_value
            self._attr_min_temp = self._set_temperature.min_value
            self._attr_target_temperature_step = self._set_temperature.value_step
            # Start in the middle of the supported range, as the device does
            # not report its own setpoint
            step = self._attr_target_temperature_step or 1.0
            self._attr_native_target_temperature = self._attr_min_temp + (
                (self._attr_max_temp - self._attr_min_temp) // 2 // step * step
            )

        if self._fan_mode_wrapper and self._fan_mode_wrapper.options:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = self._fan_mode_wrapper.options
            self._attr_fan_mode = self._attr_fan_modes[0]

        if self._switch_wrapper:
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )

        # Fall back to a mode even if the device does not restore its state
        self._attr_hvac_mode = HVACMode.OFF
        self._last_on_hvac_mode = (
            self._attr_hvac_modes[1]
            if len(self._attr_hvac_modes) > 1
            else description.switch_only_hvac_mode
        )
        # Per-entity lock to prevent concurrent command/state races
        self._action_lock = asyncio.Lock()

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the locally tracked state."""
        await super().async_added_to_hass()

        # Use RestoreClimate with validate_range=True to handle Fahrenheit conversion correctly
        if (last_climate_data := await self.async_get_last_climate_data()) is None:
            # No saved state, but we should still process any cached device status
            await self._apply_cached_device_status()
            return

        # HVAC mode, fan mode and last_on_hvac_mode come from the regular state
        last_state = await self.async_get_last_state()
        if last_state is not None:
            if (hvac_mode := last_state.state) in self._attr_hvac_modes:
                self._attr_hvac_mode = HVACMode(hvac_mode)
                if self._attr_hvac_mode != HVACMode.OFF:
                    self._last_on_hvac_mode = self._attr_hvac_mode

            if (
                fan_mode := last_state.attributes.get(ATTR_FAN_MODE)
            ) is not None and fan_mode in (self._attr_fan_modes or []):
                self._attr_fan_mode = fan_mode

            if (
                last_on_mode := last_state.attributes.get("last_on_hvac_mode")
            ) is not None:
                try:
                    restored_mode = HVACMode(last_on_mode)
                    if (
                        restored_mode in self._attr_hvac_modes
                        and restored_mode != HVACMode.OFF
                    ):
                        self._last_on_hvac_mode = restored_mode
                except ValueError:
                    pass

        # Validate target temperature (handles Fahrenheit conversion)
        if (temperature := last_climate_data.native_target_temperature) is not None:
            self._attr_native_target_temperature = temperature

        # Apply any cached device status after restoring fallback values
        await self._apply_cached_device_status()

    async def _apply_cached_device_status(self) -> None:
        """Apply cached device status on setup if available.

        The hub may already report an active AC state (power/mode/temp/wind).
        If so, we should initialize our local state from it instead of defaults.
        """
        async with self._action_lock:
            power = self._switch_wrapper.read_device_status(self.device)
            if power is False:
                self._attr_hvac_mode = HVACMode.OFF
            elif power is True:
                if self._hvac_mode_wrapper is not None:
                    tuya_mode = self._hvac_mode_wrapper.read_device_status(self.device)
                    if tuya_mode is not None and (
                        ha_mode := _TUYA_TO_HA_HVACMODE_MAPPINGS.get(tuya_mode)
                    ):
                        self._attr_hvac_mode = ha_mode
                        self._last_on_hvac_mode = ha_mode
                if self._set_temperature is not None:
                    temperature = self._set_temperature.read_device_status(self.device)
                    if temperature is not None:
                        self._attr_native_target_temperature = temperature
                if self._fan_mode_wrapper is not None:
                    fan_mode = self._fan_mode_wrapper.read_device_status(self.device)
                    if fan_mode is not None and fan_mode in (
                        self._attr_fan_modes or []
                    ):
                        self._attr_fan_mode = fan_mode
            self.async_write_ha_state()

    @override
    async def _process_device_update(
        self,
        updated_status_properties: list[str] | None,
        dp_timestamps: dict[str, int] | None = None,
    ) -> bool:
        """Update the locally tracked state from a hub status push."""
        async with self._action_lock:
            power = self._switch_wrapper.read_device_status(self.device)
            if power is False:
                self._attr_hvac_mode = HVACMode.OFF
            elif power is True:
                if self._hvac_mode_wrapper is not None:
                    tuya_mode = self._hvac_mode_wrapper.read_device_status(self.device)
                    if tuya_mode is not None and (
                        ha_mode := _TUYA_TO_HA_HVACMODE_MAPPINGS.get(tuya_mode)
                    ):
                        self._attr_hvac_mode = ha_mode
                        self._last_on_hvac_mode = ha_mode
                if self._set_temperature is not None:
                    temperature = self._set_temperature.read_device_status(self.device)
                    if temperature is not None:
                        self._attr_native_target_temperature = temperature
                if self._fan_mode_wrapper is not None:
                    fan_mode = self._fan_mode_wrapper.read_device_status(self.device)
                    if fan_mode is not None and fan_mode in (
                        self._attr_fan_modes or []
                    ):
                        self._attr_fan_mode = fan_mode
            self.async_write_ha_state()
        return True

    @override
    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set a new HVAC mode, replaying the full state when turning on."""
        async with self._action_lock:
            await self._async_set_hvac_mode_unlocked(hvac_mode)

    async def _async_set_hvac_mode_unlocked(self, hvac_mode: HVACMode) -> None:
        """Set a new HVAC mode, replaying the full state when turning on.

        The device API rejects multiple commands in one request for IR air
        conditioners, so the commands are sent one by one.
        """
        commands: list[dict[str, Any]] = []
        if self._switch_wrapper:
            commands.extend(
                self._switch_wrapper.get_update_commands(
                    self.device, hvac_mode != HVACMode.OFF
                )
            )

        if hvac_mode != HVACMode.OFF:
            if (
                self._hvac_mode_wrapper
                and (tuya_mode := _HA_TO_TUYA_HVACMODE_MAPPINGS.get(hvac_mode))
                and tuya_mode in self._hvac_mode_wrapper.options
            ):
                commands.extend(
                    self._hvac_mode_wrapper.get_update_commands(self.device, tuya_mode)
                )
            if (
                self._set_temperature
                and self._attr_native_target_temperature is not None
            ):
                commands.extend(
                    self._set_temperature.get_update_commands(
                        self.device, self._attr_native_target_temperature
                    )
                )
            if self._fan_mode_wrapper and self._attr_fan_mode is not None:
                commands.extend(
                    self._fan_mode_wrapper.get_update_commands(
                        self.device, self._attr_fan_mode
                    )
                )

        await self._async_send_sequentially(commands)

        self._attr_hvac_mode = hvac_mode
        if hvac_mode != HVACMode.OFF:
            self._last_on_hvac_mode = hvac_mode
        self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature.

        While the device is off, the value is only remembered locally.
        """
        async with self._action_lock:
            if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
                return

            # Round to the same step the command wrapper uses
            if self._set_temperature:
                step = self._set_temperature.value_step or 1.0
                min_val = self._set_temperature.min_value
                # Round to nearest valid step
                temperature = round((temperature - min_val) / step) * step + min_val

            self._attr_native_target_temperature = temperature

            # Honor optional hvac_mode passed in kwargs
            if (hvac_mode := kwargs.get("hvac_mode")) is not None:
                # Cache target before applying mode (full-state replay will include it)
                self._attr_native_target_temperature = temperature
                # Call without lock to avoid deadlock; async_set_hvac_mode acquires it
                await self._async_set_hvac_mode_unlocked(HVACMode(hvac_mode))
                return

            if self._set_temperature and self._attr_hvac_mode not in (
                None,
                HVACMode.OFF,
            ):
                await self._async_send_sequentially(
                    self._set_temperature.get_update_commands(self.device, temperature)
                )
            self.async_write_ha_state()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set a new fan mode.

        While the device is off, the value is only remembered locally.
        """
        async with self._action_lock:
            self._attr_fan_mode = fan_mode
            if self._fan_mode_wrapper and self._attr_hvac_mode not in (
                None,
                HVACMode.OFF,
            ):
                await self._async_send_sequentially(
                    self._fan_mode_wrapper.get_update_commands(self.device, fan_mode)
                )
            self.async_write_ha_state()

    @override
    async def async_turn_on(self) -> None:
        """Turn the device on, retaining the last HVAC mode."""
        await self.async_set_hvac_mode(self._last_on_hvac_mode)

    @override
    async def async_turn_off(self) -> None:
        """Turn the device off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def _async_send_sequentially(self, commands: list[dict[str, Any]]) -> None:
        """Send commands one by one."""
        for command in commands:
            await self._async_send_commands([command])
