"""Climate platform for Fujitsu IR integration — Fujitsu AC."""

from typing import Any, override

from infrared_protocols.codes.fujitsu.ac import FujitsuACCode
from infrared_protocols.commands.fujitsu_ac import (
    MAX_TEMP,
    MIN_TEMP,
    FujitsuAcCommand,
    FujitsuAcFanSpeed,
    FujitsuAcFixedCommand,
    FujitsuAcMode,
    FujitsuAcProtocol,
    FujitsuAcSwing,
    temperature_step,
)

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
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
    CONF_PROTOCOL,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    CONF_HVAC_MODES,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    PROTOCOL_EXTENDED,
)
from .entity import FujitsuIrEntity

PARALLEL_UPDATES = 1

FAN_QUIET = "quiet"

_HA_FAN_TO_LIB: dict[str, FujitsuAcFanSpeed] = {
    FAN_AUTO: FujitsuAcFanSpeed.AUTO,
    FAN_QUIET: FujitsuAcFanSpeed.QUIET,
    FAN_LOW: FujitsuAcFanSpeed.LOW,
    FAN_MEDIUM: FujitsuAcFanSpeed.MEDIUM,
    FAN_HIGH: FujitsuAcFanSpeed.HIGH,
}
_LIB_FAN_TO_HA: dict[FujitsuAcFanSpeed, str] = {v: k for k, v in _HA_FAN_TO_LIB.items()}

# Power is a separate message rather than a mode, so this dict intentionally has no
# HVACMode.OFF entry.
_HA_MODE_TO_LIB: dict[HVACMode, FujitsuAcMode] = {
    HVACMode.HEAT_COOL: FujitsuAcMode.AUTO,
    HVACMode.COOL: FujitsuAcMode.COOL,
    HVACMode.HEAT: FujitsuAcMode.HEAT,
    HVACMode.DRY: FujitsuAcMode.DRY,
    HVACMode.FAN_ONLY: FujitsuAcMode.FAN_ONLY,
}
_LIB_MODE_TO_HA: dict[FujitsuAcMode, HVACMode] = {
    v: k for k, v in _HA_MODE_TO_LIB.items()
}

# One protocol field drives both louvres, and its four values are exactly Home
# Assistant's own swing modes.
_HA_SWING_TO_LIB: dict[str, FujitsuAcSwing] = {
    SWING_OFF: FujitsuAcSwing.OFF,
    SWING_VERTICAL: FujitsuAcSwing.VERTICAL,
    SWING_HORIZONTAL: FujitsuAcSwing.HORIZONTAL,
    SWING_BOTH: FujitsuAcSwing.BOTH,
}
_LIB_SWING_TO_HA: dict[FujitsuAcSwing, str] = {
    v: k for k, v in _HA_SWING_TO_LIB.items()
}


def _config_entry_protocol(entry: ConfigEntry) -> FujitsuAcProtocol:
    """Return the protocol the configured remote family speaks."""
    if entry.data.get(CONF_PROTOCOL) == PROTOCOL_EXTENDED:
        return FujitsuAcProtocol.EXTENDED
    return FujitsuAcProtocol.STANDARD


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fujitsu AC climate entity from config entry."""
    emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    if receiver_entity_id := entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID):
        async_add_entities(
            [FujitsuAcClimateWithReceiver(entry, emitter_entity_id, receiver_entity_id)]
        )
    else:
        async_add_entities([FujitsuAcClimateEntity(entry, emitter_entity_id)])


class FujitsuAcClimateEntity(
    FujitsuIrEntity, InfraredEmitterConsumerEntity, ClimateEntity, RestoreEntity
):
    """Fujitsu AC climate entity controlled via infrared emitter."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = float(MIN_TEMP)
    _attr_max_temp = float(MAX_TEMP)
    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_translation_key = "fujitsu_ac"
    # Every mode's state message carries a temperature, a fan and a swing field, so all
    # of these features work regardless of which modes are configured.
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )
    _attr_fan_modes = [FAN_AUTO, FAN_QUIET, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_swing_modes = [SWING_OFF, SWING_VERTICAL, SWING_HORIZONTAL, SWING_BOTH]

    def __init__(self, entry: ConfigEntry, emitter_entity_id: str) -> None:
        """Initialize Fujitsu AC climate entity."""
        super().__init__(entry)
        self._infrared_emitter_entity_id = emitter_entity_id
        self._protocol = _config_entry_protocol(entry)
        self._attr_target_temperature_step = temperature_step(self._protocol)

        configured_modes = entry.data[CONF_HVAC_MODES]
        self._attr_hvac_modes = [HVACMode.OFF] + [HVACMode(m) for m in configured_modes]
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = float(MIN_TEMP)
        self._attr_fan_mode = FAN_AUTO
        self._attr_swing_mode = SWING_OFF

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

        attributes = last_state.attributes
        if last_state.state in self._attr_hvac_modes:
            self._attr_hvac_mode = HVACMode(last_state.state)
        if (fan_mode := attributes.get(ATTR_FAN_MODE)) in self._attr_fan_modes:
            self._attr_fan_mode = fan_mode
        if (swing_mode := attributes.get(ATTR_SWING_MODE)) in self._attr_swing_modes:
            self._attr_swing_mode = swing_mode
        if (temperature := attributes.get(ATTR_TEMPERATURE)) is not None:
            # State attributes are persisted in the system unit, while this entity is
            # pinned to Celsius because the protocol is, so a Fahrenheit installation
            # stores a number that means nothing on this scale.
            self._attr_target_temperature = self._snap_temperature(
                TemperatureConverter.convert(
                    float(temperature),
                    self.hass.config.units.temperature_unit,
                    self.temperature_unit,
                )
            )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        await self._async_send_mode(hvac_mode)
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature, switching the HVAC mode when one is given."""
        temperature = self._snap_temperature(float(kwargs[ATTR_TEMPERATURE]))
        hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None:
            self._valid_mode_or_raise("hvac", hvac_mode, self.hvac_modes)

        effective_mode = hvac_mode or self._attr_hvac_mode or HVACMode.OFF
        # A unit staying off has nothing to send the temperature with; it is kept for
        # the next state message instead.
        if hvac_mode is not None or effective_mode is not HVACMode.OFF:
            await self._async_send_mode(effective_mode, temperature=temperature)
            if hvac_mode is not None:
                self._attr_hvac_mode = hvac_mode

        self._attr_target_temperature = temperature
        self.async_write_ha_state()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        if (mode := self._active_lib_mode) is not None:
            await self._async_send_state(mode, fan_mode=fan_mode)
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode, which drives both louvres from one protocol field."""
        if (mode := self._active_lib_mode) is not None:
            await self._async_send_state(mode, swing_mode=swing_mode)
        self._attr_swing_mode = swing_mode
        self.async_write_ha_state()

    @property
    def _active_lib_mode(self) -> FujitsuAcMode | None:
        """Return the protocol mode the unit runs in, or None while it is off."""
        hvac_mode = self._attr_hvac_mode
        if hvac_mode is None or hvac_mode is HVACMode.OFF:
            return None
        return _HA_MODE_TO_LIB[hvac_mode]

    async def _async_send_mode(
        self, hvac_mode: HVACMode, *, temperature: float | None = None
    ) -> None:
        """Send the message that puts the unit into the given HVAC mode."""
        if hvac_mode is HVACMode.OFF:
            await self._send_command(FujitsuACCode.POWER_OFF.to_command())
            return

        await self._async_send_state(
            _HA_MODE_TO_LIB[hvac_mode],
            # A state message only starts a unit that is off when it carries this flag.
            power=self._attr_hvac_mode is HVACMode.OFF,
            temperature=temperature,
        )

    async def _async_send_state(
        self,
        mode: FujitsuAcMode,
        *,
        power: bool = False,
        temperature: float | None = None,
        fan_mode: str | None = None,
        swing_mode: str | None = None,
    ) -> None:
        """Send a state message, taking whatever is not given from the assumed state."""
        if temperature is None:
            temperature = self._attr_target_temperature or float(MIN_TEMP)
        swing = swing_mode or self._attr_swing_mode or SWING_OFF
        await self._send_command(
            FujitsuAcCommand(
                protocol=self._protocol,
                power=power,
                mode=mode,
                temperature=temperature,
                fan=_HA_FAN_TO_LIB[fan_mode or self._attr_fan_mode or FAN_AUTO],
                swing=_HA_SWING_TO_LIB[swing],
            )
        )

    def _snap_temperature(self, temperature: float) -> float:
        """Round a temperature onto the grid the configured format can carry exactly.

        Every temperature reaching this entity from outside goes through here: Home
        Assistant does not enforce the step on a service call, a restored state was
        stored on whatever grid the system unit uses, and a remote can send a half
        degree to a unit configured for whole ones. The protocol rejects anything else.
        """
        step: float = temperature_step(self._protocol)
        snapped = round(temperature / step) * step
        return min(max(snapped, float(MIN_TEMP)), float(MAX_TEMP))


class FujitsuAcClimateWithReceiver(
    FujitsuAcClimateEntity, InfraredReceiverConsumerEntity
):
    """Fujitsu AC climate entity that also tracks an infrared receiver."""

    def __init__(
        self, entry: ConfigEntry, emitter_entity_id: str, receiver_entity_id: str
    ) -> None:
        """Initialize Fujitsu AC climate entity with a receiver."""
        super().__init__(entry, emitter_entity_id)
        self._infrared_receiver_entity_id = receiver_entity_id

    @override
    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Update state from a physical remote signal."""
        command = FujitsuAcCommand.from_raw_timings(signal.timings)
        if command is None:
            # The other message a remote sends that changes this entity's state is
            # power off, which carries nothing but its own type.
            fixed = FujitsuAcFixedCommand.from_raw_timings(signal.timings)
            if fixed is not None and fixed.code == FujitsuACCode.POWER_OFF:
                self._attr_hvac_mode = HVACMode.OFF
                self.async_write_ha_state()
            return

        if command.protocol is not self._protocol:
            return

        hvac_mode = _LIB_MODE_TO_HA[command.mode]
        if hvac_mode not in self._attr_hvac_modes:
            return

        self._attr_hvac_mode = hvac_mode
        # A remote set to Fahrenheit sends its own scale, and this entity is Celsius.
        self._attr_target_temperature = self._snap_temperature(
            TemperatureConverter.convert(
                command.temperature,
                UnitOfTemperature.FAHRENHEIT,
                UnitOfTemperature.CELSIUS,
            )
            if command.is_fahrenheit
            else command.temperature
        )
        self._attr_fan_mode = _LIB_FAN_TO_HA[command.fan]
        self._attr_swing_mode = _LIB_SWING_TO_HA[command.swing]

        self.async_write_ha_state()
