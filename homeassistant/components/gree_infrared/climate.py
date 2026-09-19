"""Climate platform for Gree IR integration — Gree AC."""

from dataclasses import dataclass, replace
from typing import Any, override

from infrared_protocols.commands.gree_ac import (
    MAX_TEMP,
    MIN_TEMP,
    GreeAcCommand,
    GreeAcFanSpeed,
)

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.infrared import (
    InfraredEmitterConsumerEntity,
    InfraredReceivedSignal,
    InfraredReceiverConsumerEntity,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util.unit_conversion import TemperatureConverter

from . import GreeAcState, GreeIrConfigEntry
from .const import (
    CONF_HVAC_MODES,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DEFAULT_HVAC_MODES,
    HA_MODE_TO_LIB,
    LIB_MODE_TO_HA,
)
from .entity import GreeIrEntity

PARALLEL_UPDATES = 1

_HA_FAN_TO_LIB: dict[str, GreeAcFanSpeed] = {
    FAN_AUTO: GreeAcFanSpeed.AUTO,
    FAN_LOW: GreeAcFanSpeed.LOW,
    FAN_MEDIUM: GreeAcFanSpeed.MEDIUM,
    FAN_HIGH: GreeAcFanSpeed.HIGH,
}
_LIB_FAN_TO_HA: dict[GreeAcFanSpeed, str] = {v: k for k, v in _HA_FAN_TO_LIB.items()}


@dataclass
class _GreeAcExtraStoredData(ExtraStoredData):
    """Extra data restored alongside the entity's visible state.

    Holds the mode the unit was last actively in. The visible state only records
    OFF once the unit is off, but off frames still carry a mode field, so this
    cannot be recovered from last_state.state alone.
    """

    last_active_hvac_mode: str

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation for storage."""
        return {"last_active_hvac_mode": self.last_active_hvac_mode}

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> _GreeAcExtraStoredData | None:
        """Build from a stored dict, or None if it doesn't look valid."""
        last_active_hvac_mode = restored.get("last_active_hvac_mode")
        if not isinstance(last_active_hvac_mode, str):
            return None
        return cls(last_active_hvac_mode=last_active_hvac_mode)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeIrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gree AC climate entity from config entry."""
    emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    if receiver_entity_id := entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID):
        async_add_entities(
            [GreeAcClimateWithReceiver(entry, emitter_entity_id, receiver_entity_id)]
        )
    else:
        async_add_entities([GreeAcClimateEntity(entry, emitter_entity_id)])


class GreeAcClimateEntity(
    GreeIrEntity, InfraredEmitterConsumerEntity, ClimateEntity, RestoreEntity
):
    """Gree AC climate entity controlled via infrared emitter."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_min_temp = float(MIN_TEMP)
    _attr_max_temp = float(MAX_TEMP)
    _attr_should_poll = False
    _attr_assumed_state = True
    # Every mode's frame carries a temperature and a fan field, so both features are
    # always supported regardless of which modes are configured.
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )
    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    def __init__(self, entry: GreeIrConfigEntry, emitter_entity_id: str) -> None:
        """Initialize Gree AC climate entity."""
        super().__init__(entry)
        self._infrared_emitter_entity_id = emitter_entity_id

        configured_modes = entry.data.get(CONF_HVAC_MODES, DEFAULT_HVAC_MODES)
        self._attr_hvac_modes = [HVACMode.OFF] + [HVACMode(m) for m in configured_modes]
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = float(MIN_TEMP)
        self._attr_fan_mode = FAN_AUTO

    @property
    def _last_active_hvac_mode(self) -> HVACMode:
        """Return the mode to send a power-off frame with.

        Those frames still carry a mode field, since the protocol has no dedicated
        OFF mode. It is shared rather than held here because a frame the receiver
        picks up sets it whether or not this entity is enabled.
        """
        return LIB_MODE_TO_HA[self._runtime_data.last_active_mode]

    @_last_active_hvac_mode.setter
    def _last_active_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Record the mode to send a power-off frame with."""
        self._runtime_data.last_active_mode = HA_MODE_TO_LIB[hvac_mode]

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the assumed state, as infrared cannot read it back from the AC."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            if last_state.state in self._attr_hvac_modes:
                self._attr_hvac_mode = HVACMode(last_state.state)
            if (fan_mode := last_state.attributes.get(ATTR_FAN_MODE)) in _HA_FAN_TO_LIB:
                self._attr_fan_mode = fan_mode
            if (temperature := last_state.attributes.get(ATTR_TEMPERATURE)) is not None:
                self._attr_target_temperature = float(
                    round(
                        TemperatureConverter.convert(
                            float(temperature),
                            self.hass.config.units.temperature_unit,
                            self.temperature_unit,
                        )
                    )
                )

        current_mode = self._attr_hvac_mode
        if current_mode is not None and current_mode is not HVACMode.OFF:
            self._last_active_hvac_mode = current_mode
        elif (last_extra_data := await self.async_get_last_extra_data()) is not None:
            restored = _GreeAcExtraStoredData.from_dict(last_extra_data.as_dict())
            if restored is not None and restored.last_active_hvac_mode in (
                mode.value for mode in self._attr_hvac_modes if mode is not HVACMode.OFF
            ):
                self._last_active_hvac_mode = HVACMode(restored.last_active_hvac_mode)

        self._runtime_data.ac_state = self._state_for(
            self._attr_hvac_mode is not HVACMode.OFF,
            self._last_active_hvac_mode,
            int(self._attr_target_temperature or MIN_TEMP),
            self._attr_fan_mode or FAN_AUTO,
        )

    @property
    @override
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Return extra data to be restored alongside the entity's state."""
        return _GreeAcExtraStoredData(
            last_active_hvac_mode=self._last_active_hvac_mode.value
        )

    def _state_for(
        self, power: bool, hvac_mode: HVACMode, temp: int, fan_mode: str
    ) -> GreeAcState:
        """Build a frame state, keeping the feature flags the switches own."""
        return replace(
            self._runtime_data.ac_state,
            power=power,
            mode=HA_MODE_TO_LIB[hvac_mode],
            temperature=temp,
            fan=_HA_FAN_TO_LIB[fan_mode],
        )

    async def _async_send_state(
        self, hvac_mode: HVACMode, temp: int, fan_mode: str
    ) -> None:
        """Send a full-state frame for the given target state."""
        power = hvac_mode is not HVACMode.OFF
        active_hvac_mode = hvac_mode if power else self._last_active_hvac_mode
        async with self._runtime_data.send_lock:
            await self._send_command(
                self._state_for(power, active_hvac_mode, temp, fan_mode).to_command()
            )
            # Rebuilt rather than reused: a frame from the remote may have landed
            # while this one was going out, and what it carries is not this entity's
            # to undo.
            self._runtime_data.ac_state = self._state_for(
                power, active_hvac_mode, temp, fan_mode
            )
        if power:
            self._last_active_hvac_mode = hvac_mode

    async def _async_record_state(self, temp: int, fan_mode: str) -> None:
        """Record a change made while the unit is off, without sending a frame.

        The switches build their frame from the shared state, so a change left out
        of it would go out on the next toggle carrying the value this entity no
        longer shows.
        """
        async with self._runtime_data.send_lock:
            self._runtime_data.ac_state = self._state_for(
                False, self._last_active_hvac_mode, temp, fan_mode
            )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        await self._async_send_state(
            hvac_mode,
            int(self._attr_target_temperature or MIN_TEMP),
            self._attr_fan_mode or FAN_AUTO,
        )
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature, switching the HVAC mode when one is given."""
        temp = round(kwargs[ATTR_TEMPERATURE])
        hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None:
            self._valid_mode_or_raise("hvac", hvac_mode, self.hvac_modes)

        effective_mode = hvac_mode or self._attr_hvac_mode or HVACMode.OFF
        # A temperature change on its own has nothing to send while the unit is off.
        if effective_mode is not HVACMode.OFF or hvac_mode is HVACMode.OFF:
            await self._async_send_state(
                effective_mode, temp, self._attr_fan_mode or FAN_AUTO
            )
        else:
            await self._async_record_state(temp, self._attr_fan_mode or FAN_AUTO)

        if hvac_mode is not None:
            self._attr_hvac_mode = hvac_mode

        self._attr_target_temperature = float(temp)
        self.async_write_ha_state()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        hvac_mode = self._attr_hvac_mode
        if hvac_mode is not None and hvac_mode is not HVACMode.OFF:
            await self._async_send_state(
                hvac_mode, int(self._attr_target_temperature or MIN_TEMP), fan_mode
            )
        else:
            await self._async_record_state(
                int(self._attr_target_temperature or MIN_TEMP), fan_mode
            )
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()


class GreeAcClimateWithReceiver(GreeAcClimateEntity, InfraredReceiverConsumerEntity):
    """Gree AC climate entity that also tracks a configured infrared receiver."""

    def __init__(
        self, entry: GreeIrConfigEntry, emitter_entity_id: str, receiver_entity_id: str
    ) -> None:
        """Initialize Gree AC climate entity with a receiver."""
        super().__init__(entry, emitter_entity_id)
        self._infrared_receiver_entity_id = receiver_entity_id

    @override
    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Update state from a physical remote signal."""
        command = GreeAcCommand.from_raw_timings(signal.timings)
        if command is None or not self._runtime_data.apply_received_command(command):
            return

        state = self._runtime_data.ac_state
        self._attr_hvac_mode = (
            LIB_MODE_TO_HA[state.mode] if state.power else HVACMode.OFF
        )
        self._attr_fan_mode = _LIB_FAN_TO_HA[state.fan]
        self._attr_target_temperature = float(state.temperature)
        self.async_write_ha_state()
