"""Climate platform for LG IR integration — LG AC."""

from typing import Any, override

from infrared_protocols.codes.lg.ac import LgAcButton
from infrared_protocols.commands.lg_ac import (
    MAX_TEMP,
    MIN_TEMP,
    LgAcCommand,
    LgAcFanSpeed,
    LgAcFixedCommand,
    LgAcMode,
)

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_OFF,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.infrared import (
    InfraredEmitterConsumerEntity,
    InfraredReceivedSignal,
    InfraredReceiverConsumerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_DEVICE_TYPE,
    CONF_HVAC_MODES,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    LGDeviceType,
)
from .entity import LgIrEntity

PARALLEL_UPDATES = 1

FAN_QUIET = "quiet"
FAN_MEDIUM_LOW = "medium_low"
FAN_MEDIUM_HIGH = "medium_high"

_HA_FAN_TO_LIB: dict[str, LgAcFanSpeed] = {
    FAN_AUTO: LgAcFanSpeed.AUTO,
    FAN_QUIET: LgAcFanSpeed.QUIET,
    FAN_LOW: LgAcFanSpeed.LOW,
    FAN_MEDIUM_LOW: LgAcFanSpeed.MEDIUM_LOW,
    FAN_MEDIUM: LgAcFanSpeed.MEDIUM,
    FAN_MEDIUM_HIGH: LgAcFanSpeed.MEDIUM_HIGH,
    FAN_HIGH: LgAcFanSpeed.HIGH,
}
_LIB_FAN_TO_HA: dict[LgAcFanSpeed, str] = {v: k for k, v in _HA_FAN_TO_LIB.items()}

_HA_MODE_TO_LIB: dict[HVACMode, LgAcMode] = {
    HVACMode.OFF: LgAcMode.OFF,
    HVACMode.COOL: LgAcMode.COOL,
    HVACMode.HEAT: LgAcMode.HEAT,
    HVACMode.DRY: LgAcMode.DRY,
    HVACMode.FAN_ONLY: LgAcMode.FAN_ONLY,
}
_LIB_MODE_TO_HA: dict[LgAcMode, HVACMode] = {v: k for k, v in _HA_MODE_TO_LIB.items()}

# Only these modes carry a temperature in the LG AC protocol frame.
_TEMPERATURE_MODES = (LgAcMode.COOL, LgAcMode.HEAT)

SWING_LOWEST = "lowest"
SWING_LOW = "low"
SWING_MIDDLE_LOW = "middle_low"
SWING_MIDDLE_HIGH = "middle_high"
SWING_HIGH = "high"
SWING_HIGHEST = "highest"
SWING_ON = "swing"

SWING_LEFT = "left"
SWING_MIDDLE_LEFT = "middle_left"
SWING_MIDDLE = "middle"
SWING_MIDDLE_RIGHT = "middle_right"
SWING_RIGHT = "right"

# Oscillates in one half
SWING_LEFT_HALF = "left_half"
SWING_RIGHT_HALF = "right_half"

# The six vane positions plus off and the oscillating "swing" mode share the vertical
# swing dropdown. There is no true centre position on this ladder.
_HA_SWING_TO_LIB: dict[str, LgAcButton] = {
    SWING_OFF: LgAcButton.SWING_V_OFF,
    SWING_HIGHEST: LgAcButton.SWING_V_HIGHEST,
    SWING_HIGH: LgAcButton.SWING_V_HIGH,
    SWING_MIDDLE_HIGH: LgAcButton.SWING_V_MIDDLE_HIGH,
    SWING_MIDDLE_LOW: LgAcButton.SWING_V_MIDDLE_LOW,
    SWING_LOW: LgAcButton.SWING_V_LOW,
    SWING_LOWEST: LgAcButton.SWING_V_LOWEST,
    SWING_ON: LgAcButton.SWING_V_SWING,
}
_LIB_SWING_TO_HA: dict[LgAcButton, str] = {v: k for k, v in _HA_SWING_TO_LIB.items()}

_HA_SWING_H_TO_LIB: dict[str, LgAcButton] = {
    SWING_OFF: LgAcButton.SWING_H_OFF,
    SWING_LEFT: LgAcButton.SWING_H_LEFT,
    SWING_MIDDLE_LEFT: LgAcButton.SWING_H_MIDDLE_LEFT,
    SWING_MIDDLE: LgAcButton.SWING_H_MIDDLE,
    SWING_MIDDLE_RIGHT: LgAcButton.SWING_H_MIDDLE_RIGHT,
    SWING_RIGHT: LgAcButton.SWING_H_RIGHT,
    SWING_LEFT_HALF: LgAcButton.SWING_H_MIDDLE_TO_LEFT,
    SWING_RIGHT_HALF: LgAcButton.SWING_H_MIDDLE_TO_RIGHT,
    SWING_ON: LgAcButton.SWING_H_SWING,
}
_LIB_SWING_H_TO_HA: dict[LgAcButton, str] = {
    v: k for k, v in _HA_SWING_H_TO_LIB.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LG AC climate entity from config entry."""
    if entry.data[CONF_DEVICE_TYPE] != LGDeviceType.AC:
        return

    emitter_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    if receiver_entity_id := entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID):
        async_add_entities(
            [LgAcClimateWithReceiver(entry, emitter_entity_id, receiver_entity_id)]
        )
    else:
        async_add_entities([LgAcClimateEntity(entry, emitter_entity_id)])


class LgAcClimateEntity(
    LgIrEntity, InfraredEmitterConsumerEntity, ClimateEntity, RestoreEntity
):
    """LG AC climate entity controlled via infrared emitter."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_min_temp = float(MIN_TEMP)
    _attr_max_temp = float(MAX_TEMP)
    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_translation_key = "lg_ac"
    _attr_fan_modes = [
        FAN_AUTO,
        FAN_QUIET,
        FAN_LOW,
        FAN_MEDIUM_LOW,
        FAN_MEDIUM,
        FAN_MEDIUM_HIGH,
        FAN_HIGH,
    ]
    _attr_swing_modes = list(_HA_SWING_TO_LIB)
    _attr_swing_horizontal_modes = list(_HA_SWING_H_TO_LIB)

    def __init__(self, entry: ConfigEntry, emitter_entity_id: str) -> None:
        """Initialize LG AC climate entity."""
        super().__init__(entry, unique_id_suffix="climate", device_name="LG AC")
        self._infrared_emitter_entity_id = emitter_entity_id

        configured_modes = entry.data.get(
            CONF_HVAC_MODES, [HVACMode.COOL, HVACMode.DRY]
        )
        self._attr_hvac_modes = [HVACMode.OFF] + [HVACMode(m) for m in configured_modes]
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = float(MIN_TEMP)
        self._attr_fan_mode = FAN_AUTO
        self._attr_swing_mode = SWING_OFF
        self._attr_swing_horizontal_mode = SWING_OFF

        self._attr_supported_features = (
            ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.SWING_HORIZONTAL_MODE
        )
        # Without a temperature-carrying mode no target temperature can ever be sent.
        if any(
            _HA_MODE_TO_LIB[mode] in _TEMPERATURE_MODES
            for mode in self._attr_hvac_modes
        ):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the assumed state, as infrared cannot read it back from the AC."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            return

        if last_state.state in self._attr_hvac_modes:
            self._attr_hvac_mode = HVACMode(last_state.state)
        if (fan_mode := last_state.attributes.get(ATTR_FAN_MODE)) in _HA_FAN_TO_LIB:
            self._attr_fan_mode = fan_mode
        if (temperature := last_state.attributes.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = float(temperature)
        if (swing := last_state.attributes.get(ATTR_SWING_MODE)) in _HA_SWING_TO_LIB:
            self._attr_swing_mode = swing
        if (
            swing_h := last_state.attributes.get(ATTR_SWING_HORIZONTAL_MODE)
        ) in _HA_SWING_H_TO_LIB:
            self._attr_swing_horizontal_mode = swing_h

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        temp = int(self._attr_target_temperature or MIN_TEMP)
        await self._send_command(
            self._build_command(
                _HA_MODE_TO_LIB[hvac_mode], temp, self._attr_fan_mode or FAN_AUTO
            )
        )
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature, switching the HVAC mode when one is given."""
        temp = int(kwargs[ATTR_TEMPERATURE])
        hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None:
            self._valid_mode_or_raise("hvac", hvac_mode, self.hvac_modes)

        lib_mode = _HA_MODE_TO_LIB.get(
            hvac_mode or self._attr_hvac_mode or HVACMode.OFF, LgAcMode.OFF
        )
        if hvac_mode is not None or lib_mode in _TEMPERATURE_MODES:
            await self._send_command(
                self._build_command(lib_mode, temp, self._attr_fan_mode or FAN_AUTO)
            )
            if hvac_mode is not None:
                self._attr_hvac_mode = hvac_mode

        self._attr_target_temperature = float(temp)
        self.async_write_ha_state()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        lib_mode = _HA_MODE_TO_LIB.get(
            self._attr_hvac_mode or HVACMode.OFF, LgAcMode.OFF
        )
        if lib_mode is not LgAcMode.OFF:
            temp = int(self._attr_target_temperature or MIN_TEMP)
            await self._send_command(self._build_command(lib_mode, temp, fan_mode))
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the vertical swing mode.

        Each vane position is a self-contained fixed code, so it is sent directly
        rather than folded into the current state frame.
        """
        await self._send_command(_HA_SWING_TO_LIB[swing_mode].to_command())
        self._attr_swing_mode = swing_mode
        self.async_write_ha_state()

    @override
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set the horizontal swing mode."""
        await self._send_command(_HA_SWING_H_TO_LIB[swing_horizontal_mode].to_command())
        self._attr_swing_horizontal_mode = swing_horizontal_mode
        self.async_write_ha_state()

    def _build_command(self, mode: LgAcMode, temp: int, fan_mode: str) -> LgAcCommand:
        """Build a command from a mode, a temperature and a fan mode.

        The library drops the temperature for the modes whose frames cannot carry one,
        so it can be passed unconditionally.
        """
        return LgAcCommand(mode=mode, temperature=temp, fan=_HA_FAN_TO_LIB[fan_mode])


class LgAcClimateWithReceiver(LgAcClimateEntity, InfraredReceiverConsumerEntity):
    """LG AC climate entity that also tracks a configured infrared receiver."""

    def __init__(
        self, entry: ConfigEntry, emitter_entity_id: str, receiver_entity_id: str
    ) -> None:
        """Initialize LG AC climate entity with a receiver."""
        super().__init__(entry, emitter_entity_id)
        self._infrared_receiver_entity_id = receiver_entity_id

    @override
    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Update state from a physical remote signal."""
        command = LgAcCommand.from_raw_timings(signal.timings)
        if command is None:
            self._handle_fixed_signal(signal)
            return

        hvac_mode = _LIB_MODE_TO_HA[command.mode]
        if hvac_mode not in self._attr_hvac_modes:
            return
        self._attr_hvac_mode = hvac_mode

        # Power-off frames omit fan and temperature, so preserve the last known values.
        if command.fan is not None:
            self._attr_fan_mode = _LIB_FAN_TO_HA[command.fan]
        if command.temperature is not None:
            self._attr_target_temperature = float(command.temperature)

        self.async_write_ha_state()

    @callback
    def _handle_fixed_signal(self, signal: InfraredReceivedSignal) -> None:
        """Update the swing state from a fixed-code frame (e.g. a vane button)."""
        command = LgAcFixedCommand.from_raw_timings(signal.timings)
        if command is None:
            return
        try:
            button = LgAcButton(command.command)
        except ValueError:
            return

        if (swing := _LIB_SWING_TO_HA.get(button)) is not None:
            self._attr_swing_mode = swing
            self.async_write_ha_state()
        elif (swing_h := _LIB_SWING_H_TO_HA.get(button)) is not None:
            self._attr_swing_horizontal_mode = swing_h
            self.async_write_ha_state()
