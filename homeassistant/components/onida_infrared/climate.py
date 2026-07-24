"""Climate platform for Onida IR integration — Onida AC."""

from typing import Any, override

from infrared_protocols.commands.onida_ac import (
    MAX_TEMP,
    MIN_TEMP,
    OnidaAcCommand,
    OnidaAcFanSpeed,
    OnidaAcMode,
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
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_HVAC_MODES,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
)
from .entity import OnidaIrEntity

PARALLEL_UPDATES = 1

_HA_FAN_TO_LIB: dict[str, OnidaAcFanSpeed] = {
    FAN_AUTO: OnidaAcFanSpeed.AUTO,
    FAN_LOW: OnidaAcFanSpeed.LOW,
    FAN_MEDIUM: OnidaAcFanSpeed.MEDIUM,
    FAN_HIGH: OnidaAcFanSpeed.HIGH,
}
_LIB_FAN_TO_HA: dict[OnidaAcFanSpeed, str] = {v: k for k, v in _HA_FAN_TO_LIB.items()}

# Every mode other than OFF; the protocol has no OFF mode of its own, power is a
# separate field, so this dict intentionally has no HVACMode.OFF entry.
_HA_MODE_TO_LIB: dict[HVACMode, OnidaAcMode] = {
    HVACMode.AUTO: OnidaAcMode.AUTO,
    HVACMode.COOL: OnidaAcMode.COOL,
    HVACMode.HEAT: OnidaAcMode.HEAT,
    HVACMode.DRY: OnidaAcMode.DRY,
    HVACMode.FAN_ONLY: OnidaAcMode.FAN_ONLY,
}
_LIB_MODE_TO_HA: dict[OnidaAcMode, HVACMode] = {
    v: k for k, v in _HA_MODE_TO_LIB.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Onida AC climate entity from config entry."""
    emitter_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    if receiver_entity_id := entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID):
        async_add_entities(
            [OnidaAcClimateWithReceiver(entry, emitter_entity_id, receiver_entity_id)]
        )
    else:
        async_add_entities([OnidaAcClimateEntity(entry, emitter_entity_id)])


class OnidaAcClimateEntity(
    OnidaIrEntity, InfraredEmitterConsumerEntity, ClimateEntity, RestoreEntity
):
    """Onida AC climate entity controlled via infrared emitter."""

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
        """Initialize Onida AC climate entity."""
        super().__init__(entry, unique_id_suffix="climate", device_name="Onida AC")
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
        self._last_active_lib_mode = _HA_MODE_TO_LIB[self._attr_hvac_modes[1]]

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
            if self._attr_hvac_mode is not HVACMode.OFF:
                self._last_active_lib_mode = _HA_MODE_TO_LIB[self._attr_hvac_mode]
        if (fan_mode := last_state.attributes.get(ATTR_FAN_MODE)) in _HA_FAN_TO_LIB:
            self._attr_fan_mode = fan_mode
        if (temperature := last_state.attributes.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = float(temperature)

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        temp = int(self._attr_target_temperature or MIN_TEMP)
        fan_mode = self._attr_fan_mode or FAN_AUTO
        if hvac_mode is HVACMode.OFF:
            await self._send_command(
                self._build_command(self._last_active_lib_mode, False, temp, fan_mode)
            )
        else:
            lib_mode = _HA_MODE_TO_LIB[hvac_mode]
            await self._send_command(
                self._build_command(lib_mode, True, temp, fan_mode)
            )
            self._last_active_lib_mode = lib_mode

        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature, switching the HVAC mode when one is given."""
        temp = int(kwargs[ATTR_TEMPERATURE])
        hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None:
            self._valid_mode_or_raise("hvac", hvac_mode, self.hvac_modes)

        effective_mode = hvac_mode or self._attr_hvac_mode or HVACMode.OFF
        if effective_mode is not HVACMode.OFF:
            lib_mode = _HA_MODE_TO_LIB[effective_mode]
            await self._send_command(
                self._build_command(
                    lib_mode, True, temp, self._attr_fan_mode or FAN_AUTO
                )
            )
            self._last_active_lib_mode = lib_mode
            if hvac_mode is not None:
                self._attr_hvac_mode = hvac_mode

        self._attr_target_temperature = float(temp)
        self.async_write_ha_state()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        if self._attr_hvac_mode is not HVACMode.OFF:
            temp = int(self._attr_target_temperature or MIN_TEMP)
            await self._send_command(
                self._build_command(self._last_active_lib_mode, True, temp, fan_mode)
            )
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    def _build_command(
        self, mode: OnidaAcMode, power: bool, temp: int, fan_mode: str
    ) -> OnidaAcCommand:
        """Build a command from a mode, power state, a temperature and a fan mode."""
        return OnidaAcCommand(
            power=power,
            mode=mode,
            temperature=temp,
            fan=_HA_FAN_TO_LIB[fan_mode],
            swing_v=False,
            swing_h=False,
            turbo=False,
            display=True,
            blow=False,
        )


class OnidaAcClimateWithReceiver(OnidaAcClimateEntity, InfraredReceiverConsumerEntity):
    """Onida AC climate entity that also tracks a configured infrared receiver."""

    def __init__(
        self, entry: ConfigEntry, emitter_entity_id: str, receiver_entity_id: str
    ) -> None:
        """Initialize Onida AC climate entity with a receiver."""
        super().__init__(entry, emitter_entity_id)
        self._infrared_receiver_entity_id = receiver_entity_id

    @override
    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Update state from a physical remote signal."""
        command = OnidaAcCommand.from_raw_timings(signal.timings)
        if command is None:
            return

        if command.power:
            hvac_mode = _LIB_MODE_TO_HA[command.mode]
            if hvac_mode not in self._attr_hvac_modes:
                return
            self._last_active_lib_mode = command.mode
        else:
            hvac_mode = HVACMode.OFF

        self._attr_hvac_mode = hvac_mode
        self._attr_fan_mode = _LIB_FAN_TO_HA[command.fan]
        self._attr_target_temperature = float(command.temperature)
        self.async_write_ha_state()
