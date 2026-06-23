"""Climate platform for LG IR integration — LG AC."""

import logging
from typing import Any, override

from infrared_protocols.commands.lg_ac import (
    LgAcCommand,
    LgAcFanSpeed,
    LgAcMode,
    decode,
)

from homeassistant.components.climate import (
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
    async_subscribe_receiver,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_DEVICE_TYPE,
    CONF_HVAC_MODES,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    FAN_QUIET,
    MAX_TEMP,
    MIN_TEMP,
    LGDeviceType,
)
from .entity import LgIrEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

_HA_FAN_TO_LIB: dict[str, LgAcFanSpeed] = {
    FAN_AUTO: LgAcFanSpeed.AUTO,
    FAN_QUIET: LgAcFanSpeed.QUIET,
    FAN_LOW: LgAcFanSpeed.LOW,
    FAN_MEDIUM: LgAcFanSpeed.MEDIUM,
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LG AC climate entity from config entry."""
    if entry.data[CONF_DEVICE_TYPE] != LGDeviceType.AC:
        return
    async_add_entities([LgAcClimateEntity(entry, entry.data[CONF_INFRARED_ENTITY_ID])])


class LgAcClimateEntity(LgIrEntity, InfraredEmitterConsumerEntity, ClimateEntity):
    """LG AC climate entity controlled via infrared emitter."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_min_temp = float(MIN_TEMP)
    _attr_max_temp = float(MAX_TEMP)
    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_translation_key = "lg_ac"
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )
    _attr_fan_modes = [FAN_AUTO, FAN_QUIET, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    def __init__(self, entry: ConfigEntry, emitter_id: str) -> None:
        """Initialize LG AC climate entity."""
        super().__init__(entry, unique_id_suffix="climate", device_name="LG AC")
        self._infrared_emitter_entity_id = emitter_id

        configured_modes = entry.data.get(
            CONF_HVAC_MODES, [HVACMode.COOL, HVACMode.DRY]
        )
        self._attr_hvac_modes = [HVACMode.OFF] + [HVACMode(m) for m in configured_modes]
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = float(MIN_TEMP)
        self._attr_fan_mode = FAN_AUTO

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to infrared availability and receiver signals."""
        await super().async_added_to_hass()
        receiver_id = self._entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID)
        if receiver_id:
            try:
                self.async_on_remove(
                    async_subscribe_receiver(
                        self.hass, receiver_id, self._on_ir_received
                    )
                )
            except HomeAssistantError:
                _LOGGER.warning(
                    "Could not subscribe to IR receiver %s; "
                    "physical remote state updates will be unavailable",
                    receiver_id,
                )

    @callback
    def _on_ir_received(self, signal: InfraredReceivedSignal) -> None:
        """Update state from physical remote signal."""
        state = decode(signal.timings)
        if state is None:
            return
        self._attr_hvac_mode = _LIB_MODE_TO_HA.get(state.mode, HVACMode.OFF)
        self._attr_fan_mode = _LIB_FAN_TO_HA.get(state.fan, FAN_AUTO)
        if state.temp_c is not None:
            self._attr_target_temperature = float(state.temp_c)
        self.async_write_ha_state()

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        lib_mode = _HA_MODE_TO_LIB[hvac_mode]
        fan = _HA_FAN_TO_LIB.get(self._attr_fan_mode or FAN_AUTO, LgAcFanSpeed.AUTO)
        temp = int(self._attr_target_temperature or MIN_TEMP)
        await self._send_command(self._build_command(lib_mode, temp, fan))
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        temp = int(kwargs[ATTR_TEMPERATURE])
        self._attr_target_temperature = float(temp)
        lib_mode = _HA_MODE_TO_LIB.get(
            self._attr_hvac_mode or HVACMode.OFF, LgAcMode.OFF
        )
        if lib_mode in (LgAcMode.COOL, LgAcMode.HEAT):
            fan = _HA_FAN_TO_LIB.get(self._attr_fan_mode or FAN_AUTO, LgAcFanSpeed.AUTO)
            await self._send_command(
                LgAcCommand(mode=lib_mode, temperature=temp, fan=fan)
            )
        self.async_write_ha_state()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        self._attr_fan_mode = fan_mode
        lib_mode = _HA_MODE_TO_LIB.get(
            self._attr_hvac_mode or HVACMode.OFF, LgAcMode.OFF
        )
        if lib_mode != LgAcMode.OFF:
            fan = _HA_FAN_TO_LIB.get(fan_mode, LgAcFanSpeed.AUTO)
            temp = int(self._attr_target_temperature or MIN_TEMP)
            await self._send_command(self._build_command(lib_mode, temp, fan))
        self.async_write_ha_state()

    def _build_command(
        self, mode: LgAcMode, temp: int, fan: LgAcFanSpeed
    ) -> LgAcCommand:
        if mode in (LgAcMode.COOL, LgAcMode.HEAT):
            return LgAcCommand(mode=mode, temperature=temp, fan=fan)
        return LgAcCommand(mode=mode, fan=fan)
