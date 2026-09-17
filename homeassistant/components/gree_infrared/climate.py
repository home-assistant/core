"""Climate platform for Gree IR integration — Gree AC."""

from dataclasses import dataclass
from typing import Any, override

from infrared_protocols.commands.gree_ac import (
    MAX_TEMP,
    MIN_TEMP,
    GreeAcCommand,
    GreeAcFanSpeed,
    GreeAcMode,
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
from homeassistant.config_entries import ConfigEntry
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

from .const import (
    CONF_HVAC_MODES,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
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

# Every mode other than OFF; the protocol has no OFF mode of its own, power is a
# separate field, so this dict intentionally has no HVACMode.OFF entry.
_HA_MODE_TO_LIB: dict[HVACMode, GreeAcMode] = {
    HVACMode.AUTO: GreeAcMode.AUTO,
    HVACMode.COOL: GreeAcMode.COOL,
    HVACMode.HEAT: GreeAcMode.HEAT,
    HVACMode.DRY: GreeAcMode.DRY,
    HVACMode.FAN_ONLY: GreeAcMode.FAN_ONLY,
}
_LIB_MODE_TO_HA: dict[GreeAcMode, HVACMode] = {v: k for k, v in _HA_MODE_TO_LIB.items()}


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
    entry: ConfigEntry,
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

    def __init__(self, entry: ConfigEntry, emitter_entity_id: str) -> None:
        """Initialize Gree AC climate entity."""
        super().__init__(entry)
        self._infrared_emitter_entity_id = emitter_entity_id

        configured_modes = entry.data.get(
            CONF_HVAC_MODES, [HVACMode.COOL, HVACMode.DRY]
        )
        self._attr_hvac_modes = [HVACMode.OFF] + [HVACMode(m) for m in configured_modes]
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = float(MIN_TEMP)
        self._attr_fan_mode = FAN_AUTO
        # Power-off frames still need a mode field; this tracks the mode to send it
        # with, since the protocol has no dedicated OFF mode.
        self._last_active_hvac_mode = self._attr_hvac_modes[1]

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

    @property
    @override
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Return extra data to be restored alongside the entity's state."""
        return _GreeAcExtraStoredData(
            last_active_hvac_mode=self._last_active_hvac_mode.value
        )

    async def _async_send_state(
        self, hvac_mode: HVACMode, temp: int, fan_mode: str
    ) -> None:
        """Send a full-state frame for the given target state."""
        power = hvac_mode is not HVACMode.OFF
        active_hvac_mode = hvac_mode if power else self._last_active_hvac_mode
        await self._send_command(
            self._build_command(active_hvac_mode, power, temp, fan_mode)
        )
        if power:
            self._last_active_hvac_mode = hvac_mode

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
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    def _build_command(
        self, hvac_mode: HVACMode, power: bool, temp: int, fan_mode: str
    ) -> GreeAcCommand:
        """Build a command from a mode, power state, a temperature and a fan mode."""
        return GreeAcCommand(
            power=power,
            mode=_HA_MODE_TO_LIB[hvac_mode],
            temperature=temp,
            fan=_HA_FAN_TO_LIB[fan_mode],
            swing_v=False,
            swing_h=False,
            turbo=False,
            display=True,
            blow=False,
        )


class GreeAcClimateWithReceiver(GreeAcClimateEntity, InfraredReceiverConsumerEntity):
    """Gree AC climate entity that also tracks a configured infrared receiver."""

    def __init__(
        self, entry: ConfigEntry, emitter_entity_id: str, receiver_entity_id: str
    ) -> None:
        """Initialize Gree AC climate entity with a receiver."""
        super().__init__(entry, emitter_entity_id)
        self._infrared_receiver_entity_id = receiver_entity_id

    @override
    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Update state from a physical remote signal."""
        command = GreeAcCommand.from_raw_timings(signal.timings)
        if command is None:
            return

        # Off frames carry a mode field too, so the mode is recorded either way.
        embedded_hvac_mode = _LIB_MODE_TO_HA[command.mode]
        if embedded_hvac_mode in self._attr_hvac_modes:
            self._last_active_hvac_mode = embedded_hvac_mode
        elif command.power:
            return

        hvac_mode = embedded_hvac_mode if command.power else HVACMode.OFF

        self._attr_hvac_mode = hvac_mode
        self._attr_fan_mode = _LIB_FAN_TO_HA[command.fan]
        self._attr_target_temperature = float(command.temperature)
        self.async_write_ha_state()
