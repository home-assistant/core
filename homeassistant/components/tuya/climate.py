"""Support for Tuya Climate."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast, override

from tuya_device_handlers.definition.climate import (
    ClimateDefinition,
    get_default_definition,
)
from tuya_device_handlers.helpers.homeassistant import (
    TuyaClimateHVACMode,
    TuyaClimateSwingMode,
    TuyaUnitOfTemperature,
)
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util.json import json_loads_object
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import DOMAIN, TUYA_DISCOVERY_NEW, DeviceCategory
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

# Each command of an infrared air conditioner (virtual remote of an IR hub)
# sends the full state of the remote and powers the unit on.
_IR_AC_POWER_ON = "PowerOn"
_IR_AC_POWER_OFF = "PowerOff"
_IR_AC_MODE = "M"
_IR_AC_TEMPERATURE = "T"
_IR_AC_FAN = "F"
_IR_AC_TUYA_TO_HA_HVACMODE = {
    0: HVACMode.COOL,
    1: HVACMode.HEAT,
    2: HVACMode.AUTO,
    3: HVACMode.FAN_ONLY,
    4: HVACMode.DRY,
}
_IR_AC_HA_TO_TUYA_HVACMODE = {v: k for k, v in _IR_AC_TUYA_TO_HA_HVACMODE.items()}
_IR_AC_TUYA_TO_HA_FAN = {0: FAN_AUTO, 1: FAN_LOW, 2: FAN_MEDIUM, 3: FAN_HIGH}
_IR_AC_HA_TO_TUYA_FAN = {v: k for k, v in _IR_AC_TUYA_TO_HA_FAN.items()}
_IR_AC_DEFAULT_TEMPERATURE = 24.0
# The infrared code libraries lock the temperature in these modes (25 °C on
# the remotes seen so far); the value is learned from the reported state.
_IR_AC_FIXED_TEMPERATURE_MODES = (HVACMode.AUTO, HVACMode.FAN_ONLY, HVACMode.DRY)
_IR_AC_FIXED_TEMPERATURE = 25
# Fan speeds the infrared code libraries have in these modes, like the Tuya
# app shows; other modes have every fan speed. Combinations the remote is
# seen in are added.
_IR_AC_MODE_FAN_MODES: dict[HVACMode, tuple[str, ...]] = {
    HVACMode.AUTO: (FAN_AUTO,),
    HVACMode.FAN_ONLY: (FAN_AUTO,),
    HVACMode.DRY: (FAN_LOW,),
}
_IR_AC_STORED_VERSION = 3
# Reports of the remote state lag the commands by a few seconds: during this
# time after a command, reports of intermediate states are not shown.
_IR_AC_SETTLE_SECONDS = 10
_IR_AC_STATUS_POWER = "power"
_IR_AC_STATUS_MODE = "mode"
_IR_AC_STATUS_TEMPERATURE = "temp"
_IR_AC_STATUS_FAN = "wind"
_IR_AC_STATUS_CODES = {
    _IR_AC_STATUS_POWER,
    _IR_AC_STATUS_MODE,
    _IR_AC_STATUS_TEMPERATURE,
    _IR_AC_STATUS_FAN,
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
        entities: list[ClimateEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if device.category == DeviceCategory.INFRARED_AC:
                if TuyaInfraredClimateEntity.is_supported(device):
                    entities.append(TuyaInfraredClimateEntity(device, manager))
                continue
            if (description := CLIMATE_DESCRIPTIONS.get(device.category)) and (
                definition := get_default_definition(
                    device,
                    _HA_TO_TUYA_TEMPERATURE.get(
                        hass.config.units.temperature_unit,
                        TuyaUnitOfTemperature.CELSIUS,
                    ),
                )
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


def _ir_ac_range(device: CustomerDevice, code: str) -> tuple[int, int, int] | None:
    """Return (min, max, step) of an integer IR AC function, or None."""
    if (function := device.function.get(code)) is None:
        return None
    try:
        values: dict[str, Any] = json_loads_object(function.values)
        return int(values["min"]), int(values["max"]), int(values.get("step", 1))
    except ValueError, KeyError, TypeError:
        return None


def _ir_ac_int(value: Any) -> int | None:
    """Return a status value of an IR AC as an int, or None."""
    try:
        return int(value)
    except TypeError, ValueError:
        return None


@dataclass
class TuyaInfraredClimateExtraStoredData(ExtraStoredData):
    """Extra data restored for an infrared air conditioner."""

    last_on_mode: HVACMode
    remote_state: dict[str, int | None]
    seen_fan_modes: dict[str, list[str]]
    fixed_temperatures: dict[str, int]
    target_temperature: float | None

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the extra data."""
        return {
            "last_on_mode": self.last_on_mode,
            "remote_state": self.remote_state,
            "seen_fan_modes": self.seen_fan_modes,
            "fixed_temperatures": self.fixed_temperatures,
            "target_temperature": self.target_temperature,
            "version": _IR_AC_STORED_VERSION,
        }


class _IRCommandRejected(Exception):
    """The cloud has no infrared code for the state a command leads to."""


class TuyaInfraredClimateEntity(TuyaEntity, ClimateEntity, RestoreEntity):
    """Air conditioner behind a Tuya infrared hub.

    The Tuya cloud exposes these virtual remotes as devices of category
    ``infrared_ac`` with the commands PowerOn, PowerOff, M (mode),
    T (temperature) and F (fan speed). The hub remembers the state of the
    virtual remote and every command makes it transmit one infrared frame
    holding the whole state (power on, mode, temperature and fan). So:

    * a single command is sent per request (the cloud rejects several), and
    * only the settings that differ from the remote's state are sent; turning
      the unit on with unchanged settings sends a single PowerOn, so the unit
      beeps once.

    The infrared code libraries only have codes for some combinations, like
    the Tuya app shows: auto and fan only with an automatic fan, dry with a
    low fan, and a temperature locked at 25 °C in these three modes. A
    command leading to a combination without a code is rejected by the
    cloud, so the entity offers only the fan speeds of the current mode,
    sends the locked temperature and the fan speed before switching to such
    a mode, and goes through cool when the fan cannot change in the current
    mode. Combinations the remote is seen in (for example after using the
    Tuya app) are offered too.

    The remote's state is read from the ``power``/``mode``/``temp``/``wind``
    status the cloud reports, when it does. Otherwise the entity keeps an
    assumed state that is restored after a restart.
    """

    _attr_assumed_state = True
    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, device: CustomerDevice, device_manager: Manager) -> None:
        """Initialize the infrared air conditioner."""
        super().__init__(device, device_manager, TuyaEntityDescription(key=""))
        min_temp, max_temp, step = _ir_ac_range(device, _IR_AC_TEMPERATURE) or (
            16,
            30,
            1,
        )
        self._attr_min_temp = min_temp
        self._attr_max_temp = max_temp
        self._attr_target_temperature_step = step
        self._attr_native_target_temperature = min(
            max(_IR_AC_DEFAULT_TEMPERATURE, min_temp), max_temp
        )

        mode_min, mode_max, _ = _ir_ac_range(device, _IR_AC_MODE) or (0, -1, 1)
        on_modes = [
            _IR_AC_TUYA_TO_HA_HVACMODE[value]
            for value in range(mode_min, mode_max + 1)
            if value in _IR_AC_TUYA_TO_HA_HVACMODE
        ]
        self._attr_hvac_modes = [HVACMode.OFF, *on_modes]
        self._attr_hvac_mode = HVACMode.OFF
        self._last_on_mode = HVACMode.COOL if HVACMode.COOL in on_modes else on_modes[0]

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        self._all_fan_modes: list[str] = []
        self._attr_fan_mode = None
        if fan_range := _ir_ac_range(device, _IR_AC_FAN):
            self._all_fan_modes = [
                _IR_AC_TUYA_TO_HA_FAN[value]
                for value in range(fan_range[0], fan_range[1] + 1)
                if value in _IR_AC_TUYA_TO_HA_FAN
            ]
            if self._all_fan_modes:
                self._attr_fan_mode = (
                    FAN_AUTO
                    if FAN_AUTO in self._all_fan_modes
                    else self._all_fan_modes[0]
                )
                self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        # Last known state of the virtual remote (None: unknown).
        self._remote_state: dict[str, int | None] = {
            _IR_AC_MODE: None,
            _IR_AC_TEMPERATURE: None,
            _IR_AC_FAN: None,
        }
        # Fan speeds and locked temperatures the remote was seen with.
        self._seen_fan_modes: dict[HVACMode, set[str]] = {}
        self._fixed_temperatures: dict[HVACMode, int] = {}
        # One action at a time: commands of two actions must not interleave.
        self._action_lock = asyncio.Lock()
        # Commands being sent, and until when reports may lag behind them.
        self._sending = False
        self._settle_until = 0.0
        self._cancel_settle: CALLBACK_TYPE | None = None
        self._reported_since_command = False
        self._remote_reports_state = self._async_sync_from_status()

    @staticmethod
    def is_supported(device: CustomerDevice) -> bool:
        """Return if the device has the commands this entity needs."""
        mode_range = _ir_ac_range(device, _IR_AC_MODE)
        return (
            _IR_AC_POWER_ON in device.function
            and _IR_AC_POWER_OFF in device.function
            and mode_range is not None
            and any(
                value in _IR_AC_TUYA_TO_HA_HVACMODE
                for value in range(mode_range[0], mode_range[1] + 1)
            )
        )

    @property
    @override
    def fan_modes(self) -> list[str] | None:
        """Return the fan speeds of the current mode."""
        if not self._all_fan_modes:
            return None
        return self._fan_modes_for(self._display_mode)

    @property
    @override
    def supported_features(self) -> ClimateEntityFeature:
        """Return the features, without temperature in locked modes."""
        if self._display_mode in _IR_AC_FIXED_TEMPERATURE_MODES:
            return (
                self._attr_supported_features & ~ClimateEntityFeature.TARGET_TEMPERATURE
            )
        return self._attr_supported_features

    @property
    def _display_mode(self) -> HVACMode:
        """Return the mode the unit is in, or will turn on in."""
        if (hvac_mode := self._attr_hvac_mode) is None or hvac_mode == HVACMode.OFF:
            return self._last_on_mode
        return hvac_mode

    def _fixed_temperature(self, hvac_mode: HVACMode) -> int | None:
        """Return the locked temperature of a mode, or None."""
        if hvac_mode not in _IR_AC_FIXED_TEMPERATURE_MODES:
            return None
        return self._fixed_temperatures.get(hvac_mode, _IR_AC_FIXED_TEMPERATURE)

    def _fan_modes_for(self, hvac_mode: HVACMode | None) -> list[str]:
        """Return the fan speeds of a mode."""
        if hvac_mode not in _IR_AC_MODE_FAN_MODES:
            return list(self._all_fan_modes)
        allowed = {
            *_IR_AC_MODE_FAN_MODES[hvac_mode],
            *self._seen_fan_modes.get(hvac_mode, ()),
        }
        return [fan for fan in self._all_fan_modes if fan in allowed] or list(
            self._all_fan_modes
        )

    def _fan_for_mode(self, hvac_mode: HVACMode, fan_mode: str | None) -> str | None:
        """Return the fan speed to use in a mode, given the wanted one."""
        if not self._all_fan_modes:
            return None
        allowed = self._fan_modes_for(hvac_mode)
        return fan_mode if fan_mode in allowed else allowed[0]

    @callback
    def _async_sync_from_status(self) -> bool:
        """Update the state from the remote state reported by the cloud.

        Return True if the cloud reports the remote state.
        """
        status = self.device.status
        if _IR_AC_STATUS_POWER not in status:
            return False
        mode = _ir_ac_int(status.get(_IR_AC_STATUS_MODE))
        temperature = _ir_ac_int(status.get(_IR_AC_STATUS_TEMPERATURE))
        fan = _ir_ac_int(status.get(_IR_AC_STATUS_FAN))
        self._remote_state = {
            _IR_AC_MODE: mode,
            _IR_AC_TEMPERATURE: temperature,
            _IR_AC_FAN: fan,
        }
        hvac_mode = _IR_AC_TUYA_TO_HA_HVACMODE.get(mode) if mode is not None else None
        if hvac_mode not in self._attr_hvac_modes:
            hvac_mode = None
        fan_mode = _IR_AC_TUYA_TO_HA_FAN.get(fan) if fan is not None else None
        if fan_mode not in self._all_fan_modes:
            fan_mode = None
        if hvac_mode is not None:
            self._last_on_mode = hvac_mode
            # The remote is in this combination: the code exists.
            if fan_mode is not None and hvac_mode in _IR_AC_MODE_FAN_MODES:
                self._seen_fan_modes.setdefault(hvac_mode, set()).add(fan_mode)
            if hvac_mode in _IR_AC_FIXED_TEMPERATURE_MODES and temperature is not None:
                self._fixed_temperatures[hvac_mode] = temperature
        if not status[_IR_AC_STATUS_POWER]:
            self._attr_hvac_mode = HVACMode.OFF
        elif hvac_mode is not None:
            self._attr_hvac_mode = hvac_mode
        if temperature is not None:
            self._attr_native_target_temperature = float(temperature)
        if fan_mode is not None:
            self._attr_fan_mode = fan_mode
        return True

    @override
    async def _process_device_update(
        self,
        updated_status_properties: list[str],
        dp_timestamps: dict[str, int] | None,
    ) -> bool:
        """Follow changes of the remote state (for example from the Tuya app)."""
        if not set(updated_status_properties) & _IR_AC_STATUS_CODES:
            return False
        self._reported_since_command = True
        if self._sending or (
            self.hass.loop.time() < self._settle_until
            and not self._status_matches_sent()
        ):
            # An intermediate state of commands just sent (for example
            # through cool to change the fan): not shown.
            return False
        self._settle_until = 0.0
        self._remote_reports_state = self._async_sync_from_status()
        return True

    @asynccontextmanager
    async def _async_action(self) -> AsyncIterator[None]:
        """Run one action, hiding reports of intermediate states."""
        async with self._action_lock:
            self._sending = True
            try:
                yield
            finally:
                self._sending = False
                self._settle_until = self.hass.loop.time() + _IR_AC_SETTLE_SECONDS
                if self._cancel_settle:
                    self._cancel_settle()
                self._cancel_settle = async_call_later(
                    self.hass, _IR_AC_SETTLE_SECONDS, self._async_settled
                )

    @callback
    def _async_settled(self, _now: datetime) -> None:
        """Show the reported remote state once reports caught up."""
        self._cancel_settle = None
        self._settle_until = 0.0
        # Without a report since the last command, the status is older than
        # the commands and the assumed state is kept.
        if (
            self._remote_reports_state
            and self._reported_since_command
            and not self._status_matches_sent()
        ):
            self._remote_reports_state = self._async_sync_from_status()
            self.async_write_ha_state()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel the pending settle check."""
        if self._cancel_settle:
            self._cancel_settle()
            self._cancel_settle = None
        await super().async_will_remove_from_hass()

    def _status_matches_sent(self) -> bool:
        """Return if the reported remote state is the one last sent."""
        status = self.device.status
        reported = {
            _IR_AC_MODE: _ir_ac_int(status.get(_IR_AC_STATUS_MODE)),
            _IR_AC_TEMPERATURE: _ir_ac_int(status.get(_IR_AC_STATUS_TEMPERATURE)),
            _IR_AC_FAN: _ir_ac_int(status.get(_IR_AC_STATUS_FAN)),
        }
        return bool(status.get(_IR_AC_STATUS_POWER)) == (
            self._attr_hvac_mode != HVACMode.OFF
        ) and all(
            sent is None or reported[code] == sent
            for code, sent in self._remote_state.items()
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the assumed state."""
        await super().async_added_to_hass()
        restored_temperature = False
        if (extra := await self.async_get_last_extra_data()) is not None:
            restored_temperature = self._async_restore_extra_data(extra.as_dict())
        if self._remote_reports_state:
            # The reported state wins.
            self._remote_reports_state = self._async_sync_from_status()
            return
        if (last_state := await self.async_get_last_state()) is None:
            return
        if last_state.state in self._attr_hvac_modes:
            self._attr_hvac_mode = HVACMode(last_state.state)
            if self._attr_hvac_mode != HVACMode.OFF and extra is None:
                self._last_on_mode = self._attr_hvac_mode
        if not restored_temperature and isinstance(
            temperature := last_state.attributes.get(ATTR_TEMPERATURE), (int, float)
        ):
            # State attributes are in the unit of the Home Assistant instance.
            self._attr_native_target_temperature = float(
                self._quantize_temperature(
                    TemperatureConverter.convert(
                        temperature,
                        self.hass.config.units.temperature_unit,
                        UnitOfTemperature.CELSIUS,
                    )
                )
            )
        if (fan_mode := last_state.attributes.get(ATTR_FAN_MODE)) in (
            self._all_fan_modes
        ):
            self._attr_fan_mode = fan_mode

    @callback
    def _async_restore_extra_data(self, extra_data: dict[str, Any]) -> bool:
        """Restore the last used mode, remote state and seen combinations.

        Return True if the target temperature was restored.
        """
        if (last_on_mode := extra_data.get("last_on_mode")) in self._attr_hvac_modes:
            if last_on_mode != HVACMode.OFF:
                self._last_on_mode = HVACMode(last_on_mode)
        if not self._remote_reports_state and isinstance(
            remote_state := extra_data.get("remote_state"), dict
        ):
            for code in self._remote_state:
                self._remote_state[code] = _ir_ac_int(remote_state.get(code))
        if extra_data.get("version") != _IR_AC_STORED_VERSION:
            return False
        restored_temperature = False
        if isinstance(
            temperature := extra_data.get("target_temperature"), (int, float)
        ):
            self._attr_native_target_temperature = float(
                self._quantize_temperature(temperature)
            )
            restored_temperature = True
        if isinstance(seen := extra_data.get("seen_fan_modes"), dict):
            for mode, fans in seen.items():
                if mode in _IR_AC_MODE_FAN_MODES and isinstance(fans, list):
                    self._seen_fan_modes[HVACMode(mode)] = {
                        fan for fan in fans if fan in self._all_fan_modes
                    }
        if isinstance(temperatures := extra_data.get("fixed_temperatures"), dict):
            for mode, temperature in temperatures.items():
                if (
                    mode in _IR_AC_FIXED_TEMPERATURE_MODES
                    and (value := _ir_ac_int(temperature)) is not None
                ):
                    self._fixed_temperatures[HVACMode(mode)] = value
        return restored_temperature

    @property
    @override
    def extra_restore_state_data(self) -> TuyaInfraredClimateExtraStoredData:
        """Return the data kept across restarts."""
        return TuyaInfraredClimateExtraStoredData(
            self._last_on_mode,
            dict(self._remote_state),
            {mode: sorted(fans) for mode, fans in self._seen_fan_modes.items()},
            {mode.value: temp for mode, temp in self._fixed_temperatures.items()},
            self._attr_native_target_temperature,
        )

    def _quantize_temperature(self, temperature: float) -> int:
        """Return a temperature rounded to the step and range of the remote."""
        step = self._attr_target_temperature_step or 1
        value = round(temperature / step) * step
        return int(min(max(value, self._attr_min_temp), self._attr_max_temp))

    async def _async_send_ir_command(self, code: str, value: Any) -> None:
        """Send one command (the cloud rejects several IR commands at once)."""
        # A report arriving from now on reflects this command.
        self._reported_since_command = False
        await self._async_send_commands([{"code": code, "value": value}])
        if code in self._remote_state:
            self._remote_state[code] = value

    async def _async_try_ir_command(self, code: str, value: Any) -> None:
        """Send one command, raising _IRCommandRejected if it has no code."""
        try:
            await self._async_send_ir_command(code, value)
        except HomeAssistantError as err:
            if err.translation_key != "command_rejected":
                raise
            raise _IRCommandRejected from err

    async def _async_reach(self, hvac_mode: HVACMode, fan_mode: str | None) -> bool:
        """Bring the remote to a mode and fan speed.

        Return False when the cloud rejects a command on the way.
        """
        state_known = None not in self._remote_state.values()
        try:
            await self._async_reach_from_remote_state(hvac_mode, fan_mode)
        except _IRCommandRejected:
            if state_known:
                return False
            # The unknown remote state may have no code for this route.
            try:
                await self._async_reach_from_remote_state(
                    hvac_mode, fan_mode, via_bridge=True
                )
            except _IRCommandRejected:
                return False
        return True

    async def _async_reach_from_remote_state(
        self, hvac_mode: HVACMode, fan_mode: str | None, via_bridge: bool = False
    ) -> None:
        """Send the commands leading from the remote state to a mode and fan.

        Raise _IRCommandRejected when the cloud rejects a command.
        """
        remote = self._remote_state
        mode_value = _IR_AC_HA_TO_TUYA_HVACMODE[hvac_mode]
        fan_value = _IR_AC_HA_TO_TUYA_FAN[fan_mode] if fan_mode else None
        if remote[_IR_AC_MODE] == mode_value and fan_value in (
            None,
            remote[_IR_AC_FAN],
        ):
            return
        remote_mode = (
            None
            if (value := remote[_IR_AC_MODE]) is None
            else _IR_AC_TUYA_TO_HA_HVACMODE.get(value)
        )
        remote_fan = (
            None
            if (value := remote[_IR_AC_FAN]) is None
            else _IR_AC_TUYA_TO_HA_FAN.get(value)
        )
        fixed = self._fixed_temperature(hvac_mode)
        needs_fixed = (
            remote[_IR_AC_MODE] != mode_value
            and fixed is not None
            and remote[_IR_AC_TEMPERATURE] != fixed
        )
        if needs_fixed and remote_mode in _IR_AC_FIXED_TEMPERATURE_MODES:
            # The current mode only has codes at its own locked temperature.
            via_bridge = True
        if via_bridge:
            # Cool (or heat) has codes for every temperature and fan speed.
            bridge = next(
                (
                    mode
                    for mode in (HVACMode.COOL, HVACMode.HEAT)
                    if mode in self._attr_hvac_modes
                ),
                None,
            )
            if bridge is None:
                raise _IRCommandRejected
            bridge_value = _IR_AC_HA_TO_TUYA_HVACMODE[bridge]
            if remote[_IR_AC_MODE] != bridge_value:
                await self._async_try_ir_command(_IR_AC_MODE, bridge_value)
            if needs_fixed:
                await self._async_try_ir_command(_IR_AC_TEMPERATURE, fixed)
            if fan_value is not None and remote[_IR_AC_FAN] != fan_value:
                await self._async_try_ir_command(_IR_AC_FAN, fan_value)
            if remote[_IR_AC_MODE] != mode_value:
                await self._async_try_ir_command(_IR_AC_MODE, mode_value)
            return
        if needs_fixed:
            # The mode only has codes at its locked temperature.
            await self._async_try_ir_command(_IR_AC_TEMPERATURE, fixed)
        if remote[_IR_AC_MODE] == mode_value:
            await self._async_try_ir_command(_IR_AC_FAN, fan_value)
        elif remote_fan is None or remote_fan in self._fan_modes_for(hvac_mode):
            # The new mode has the current fan speed: mode first.
            await self._async_try_ir_command(_IR_AC_MODE, mode_value)
            if fan_value is not None and remote[_IR_AC_FAN] != fan_value:
                await self._async_try_ir_command(_IR_AC_FAN, fan_value)
        elif fan_mode in self._fan_modes_for(remote_mode):
            # The current mode has the new fan speed: fan first.
            await self._async_try_ir_command(_IR_AC_FAN, fan_value)
            await self._async_try_ir_command(_IR_AC_MODE, mode_value)
        else:
            await self._async_reach_from_remote_state(
                hvac_mode, fan_mode, via_bridge=True
            )

    @callback
    def _async_show_sent_state(self, sent_before: dict[str, int | None]) -> None:
        """Show the state accepted commands of a failed action left the unit in."""
        if self._remote_state == sent_before:
            return
        # Every accepted command powered the unit on with the remote's state.
        mode = self._remote_state[_IR_AC_MODE]
        hvac_mode = _IR_AC_TUYA_TO_HA_HVACMODE.get(mode) if mode is not None else None
        if hvac_mode in self._attr_hvac_modes:
            self._attr_hvac_mode = hvac_mode
            self._last_on_mode = hvac_mode
        fan = self._remote_state[_IR_AC_FAN]
        if (
            fan_mode := _IR_AC_TUYA_TO_HA_FAN.get(fan) if fan is not None else None
        ) in self._all_fan_modes:
            self._attr_fan_mode = fan_mode
        if (temperature := self._remote_state[_IR_AC_TEMPERATURE]) is not None:
            self._attr_native_target_temperature = float(temperature)

    async def _async_send_settings(
        self,
        hvac_mode: HVACMode,
        target_temperature: float | None,
        fan_mode: str | None,
    ) -> str | None:
        """Send the settings that differ from the remote state.

        Every command transmits the whole state and powers the unit on, so
        from off a single PowerOn is sent when nothing else changed.
        Return the fan speed used (the mode may not have the wanted one).
        """
        was_off = self._attr_hvac_mode == HVACMode.OFF
        sent_before = self._remote_state.copy()
        fan = self._fan_for_mode(hvac_mode, fan_mode)
        if not await self._async_reach(hvac_mode, fan):
            self._async_show_sent_state(sent_before)
            self.async_write_ha_state()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="infrared_ac_mode_not_supported",
                translation_placeholders={"hvac_mode": hvac_mode},
            )
        if (fixed := self._fixed_temperature(hvac_mode)) is not None:
            target_temperature = None
            self._attr_native_target_temperature = float(fixed)
        if (
            target_temperature is not None
            and self._remote_state[_IR_AC_TEMPERATURE] != target_temperature
        ):
            await self._async_send_ir_command(
                _IR_AC_TEMPERATURE, int(target_temperature)
            )
        if was_off and self._remote_state == sent_before:
            await self._async_send_ir_command(_IR_AC_POWER_ON, _IR_AC_POWER_ON)
        return fan

    async def _async_turn_off(self) -> None:
        """Turn off, within an action."""
        await self._async_send_ir_command(_IR_AC_POWER_OFF, _IR_AC_POWER_OFF)
        self._attr_hvac_mode = HVACMode.OFF
        self.async_write_ha_state()

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode, powering the unit on or off as needed."""
        async with self._async_action():
            if hvac_mode == HVACMode.OFF:
                await self._async_turn_off()
                return
            self._attr_fan_mode = await self._async_send_settings(
                hvac_mode, self._attr_native_target_temperature, self._attr_fan_mode
            )
            self._attr_hvac_mode = hvac_mode
            self._last_on_mode = hvac_mode
            self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature (sent only while the unit is on)."""
        temperature = float(self._quantize_temperature(kwargs[ATTR_TEMPERATURE]))
        async with self._async_action():
            hvac_mode = HVACMode(
                kwargs.get(ATTR_HVAC_MODE, self._attr_hvac_mode or HVACMode.OFF)
            )
            if hvac_mode == HVACMode.OFF:
                if self._attr_hvac_mode != HVACMode.OFF:
                    await self._async_turn_off()
                self._attr_native_target_temperature = temperature
                self.async_write_ha_state()
                return
            self._attr_fan_mode = await self._async_send_settings(
                hvac_mode, temperature, self._attr_fan_mode
            )
            if self._fixed_temperature(hvac_mode) is None:
                self._attr_native_target_temperature = temperature
            self._attr_hvac_mode = hvac_mode
            self._last_on_mode = hvac_mode
            self.async_write_ha_state()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode (sent only while the unit is on)."""
        async with self._async_action():
            if self._attr_hvac_mode != HVACMode.OFF:
                hvac_mode = self._display_mode
                sent_before = self._remote_state.copy()
                if not await self._async_reach(hvac_mode, fan_mode):
                    self._async_show_sent_state(sent_before)
                    self.async_write_ha_state()
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="infrared_ac_fan_mode_not_supported",
                        translation_placeholders={
                            "fan_mode": fan_mode,
                            "hvac_mode": hvac_mode,
                        },
                    )
            self._attr_fan_mode = fan_mode
            self.async_write_ha_state()

    @override
    async def async_turn_on(self) -> None:
        """Turn on in the last used mode."""
        await self.async_set_hvac_mode(self._last_on_mode)

    @override
    async def async_turn_off(self) -> None:
        """Turn off."""
        async with self._async_action():
            await self._async_turn_off()
