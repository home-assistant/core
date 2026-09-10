"""Support for Dyson infrared heater/coolers (AM09)."""

import asyncio
from dataclasses import asdict, dataclass
from typing import Any, override

from infrared_protocols.codes.dyson.am09 import DysonAm09Code

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_TEMPERATURE_UNIT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from .const import (
    CONF_COMMAND_STEP_DELAY,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DEFAULT_COMMAND_STEP_DELAY,
    DOMAIN,
    DysonTemperatureUnit,
)

PARALLEL_UPDATES = 1

# HEAT_UP/HEAT_DOWN step by one degree in whatever unit the device itself is
# set to display, so the entity works natively in that unit rather than
# converting; the AM09 covers the same range either way.
_UNITS: dict[DysonTemperatureUnit, UnitOfTemperature] = {
    DysonTemperatureUnit.CELSIUS: UnitOfTemperature.CELSIUS,
    DysonTemperatureUnit.FAHRENHEIT: UnitOfTemperature.FAHRENHEIT,
}
_TEMP_RANGES: dict[DysonTemperatureUnit, tuple[int, int]] = {
    DysonTemperatureUnit.CELSIUS: (1, 37),
    DysonTemperatureUnit.FAHRENHEIT: (34, 99),
}

_SPEED_COUNT = 10
_FAN_MODES = [str(speed) for speed in range(1, _SPEED_COUNT + 1)]

PRESET_FOCUSED = "focused"
PRESET_DIFFUSED = "diffused"


@dataclass
class _DysonAm09ExtraStoredData(ExtraStoredData):
    """Extra data restored alongside the entity's visible state.

    The adjustable values are withheld from the visible state while the unit is
    off, and the mode standby resumes to was never part of it, so none of them
    can be recovered from last_state alone.
    """

    last_active_mode: str
    temperature_unit: str
    target_temperature: float
    fan_mode: str
    preset_mode: str
    swing_mode: str

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation for storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> _DysonAm09ExtraStoredData | None:
        """Build from a stored dict, or None if it does not look valid."""
        try:
            return cls(
                last_active_mode=restored["last_active_mode"],
                temperature_unit=restored["temperature_unit"],
                target_temperature=float(restored["target_temperature"]),
                fan_mode=restored["fan_mode"],
                preset_mode=restored["preset_mode"],
                swing_mode=restored["swing_mode"],
            )
        except KeyError, TypeError, ValueError:
            return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Dyson infrared heater/cooler platform from a config entry."""
    infrared_emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    step_delay = entry.data.get(CONF_COMMAND_STEP_DELAY, DEFAULT_COMMAND_STEP_DELAY)
    temperature_unit = DysonTemperatureUnit(entry.data[CONF_TEMPERATURE_UNIT])
    async_add_entities(
        [
            DysonInfraredHeaterCooler(
                infrared_emitter_entity_id,
                entry.entry_id,
                entry.title,
                step_delay,
                temperature_unit,
            )
        ]
    )


class DysonInfraredHeaterCooler(
    InfraredEmitterConsumerEntity, ClimateEntity, RestoreEntity
):
    """Representation of a Dyson AM09 heater/cooler entity."""

    _attr_translation_key = "heater_cooler"
    _attr_has_entity_name = True
    _attr_assumed_state = True
    _attr_target_temperature_step = 1.0
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT]
    _attr_fan_modes = _FAN_MODES
    _attr_preset_modes = [PRESET_FOCUSED, PRESET_DIFFUSED]
    _attr_swing_modes = [SWING_OFF, SWING_ON]

    def __init__(
        self,
        infrared_emitter_entity_id: str,
        unique_id: str,
        name: str,
        step_delay: float = DEFAULT_COMMAND_STEP_DELAY,
        temperature_unit: DysonTemperatureUnit = DysonTemperatureUnit.CELSIUS,
    ) -> None:
        """Initialize the Dyson infrared heater/cooler entity."""
        self._infrared_emitter_entity_id = infrared_emitter_entity_id
        self._step_delay = step_delay

        self._attr_temperature_unit = _UNITS[temperature_unit]
        self._attr_min_temp, self._attr_max_temp = _TEMP_RANGES[temperature_unit]

        self._attr_unique_id = unique_id
        self._attr_hvac_mode = HVACMode.OFF
        # Standby restores the mode the unit was in, so the mode it would come
        # back to has to be tracked separately from the reported OFF state.
        self._last_active_mode = HVACMode.COOL
        self._attr_target_temperature = float(self._attr_min_temp)
        self._attr_fan_mode = _FAN_MODES[_SPEED_COUNT // 2 - 1]
        self._attr_preset_mode = PRESET_DIFFUSED
        self._attr_swing_mode = SWING_OFF

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=name,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the assumed state, as infrared cannot read it back from the unit."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        if last_state.state in self._attr_hvac_modes:
            self._attr_hvac_mode = HVACMode(last_state.state)

        if (last_extra_data := await self.async_get_last_extra_data()) is None:
            return
        restored = _DysonAm09ExtraStoredData.from_dict(last_extra_data.as_dict())
        if restored is None:
            return

        if restored.last_active_mode in (HVACMode.COOL, HVACMode.HEAT):
            self._last_active_mode = HVACMode(restored.last_active_mode)
        # A changed temperature unit option rescales the range, which would make
        # the stored target mean a different temperature than it was set to.
        if (
            restored.temperature_unit == self._attr_temperature_unit
            and self._attr_min_temp
            <= restored.target_temperature
            <= self._attr_max_temp
        ):
            self._attr_target_temperature = restored.target_temperature
        if restored.fan_mode in _FAN_MODES:
            self._attr_fan_mode = restored.fan_mode
        if restored.preset_mode in self._attr_preset_modes:
            self._attr_preset_mode = restored.preset_mode
        if restored.swing_mode in self._attr_swing_modes:
            self._attr_swing_mode = restored.swing_mode

    @property
    @override
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Return entity specific state data to be restored."""
        return _DysonAm09ExtraStoredData(
            last_active_mode=self._last_active_mode.value,
            temperature_unit=self._attr_temperature_unit,
            target_temperature=float(
                self._attr_target_temperature or self._attr_min_temp
            ),
            fan_mode=self._attr_fan_mode or _FAN_MODES[0],
            preset_mode=self._attr_preset_mode or PRESET_DIFFUSED,
            swing_mode=self._attr_swing_mode or SWING_OFF,
        )

    @property
    @override
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features.

        The unit ignores everything but the power toggle while in standby, so
        nothing is adjustable until it is running. The AM09 also has no IR
        codes for a cooling target temperature, so TARGET_TEMPERATURE is only
        advertised while heating.
        """
        if self._attr_hvac_mode is HVACMode.OFF:
            return ClimateEntityFeature(0)

        features = (
            ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.SWING_MODE
        )
        if self._attr_hvac_mode is HVACMode.HEAT:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        return features

    async def _async_send_am09_action(self, code: DysonAm09Code) -> None:
        await self._send_command(code.to_command())

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode.

        AM09 has no dedicated OFF code, only a power toggle (POWER), so leaving
        HEAT/COOL relies on the assumed state matching the physical device.
        """
        if hvac_mode == self._attr_hvac_mode:
            return

        if hvac_mode is HVACMode.OFF:
            await self._async_send_am09_action(DysonAm09Code.POWER)
        else:
            needs_mode_select = hvac_mode is not self._last_active_mode
            if self._attr_hvac_mode is HVACMode.OFF:
                await self._async_send_am09_action(DysonAm09Code.POWER)
                if needs_mode_select:
                    await asyncio.sleep(self._step_delay)
            # COOL_ON toggles between cool and heat, and HEAT_UP only selects
            # heat while the unit is cooling, so a mode select is sent solely
            # when the unit is not already in the requested mode. Sending one
            # anyway would toggle straight back out of it.
            if needs_mode_select:
                await self._async_send_am09_action(
                    DysonAm09Code.COOL_ON
                    if hvac_mode is HVACMode.COOL
                    else DysonAm09Code.HEAT_UP
                )
            self._last_active_mode = hvac_mode

        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature by stepping HEAT_UP/HEAT_DOWN.

        Only reachable in heat mode, since TARGET_TEMPERATURE is not advertised
        otherwise and the service call is rejected before it gets here. The
        service may still carry an hvac_mode to switch to first, which the AM09
        can only honor when it is heat.
        """
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            if hvac_mode is not HVACMode.HEAT:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="target_temperature_outside_heat",
                    translation_placeholders={"hvac_mode": hvac_mode},
                )
            await self.async_set_hvac_mode(hvac_mode)

        # round(), not int(), since a system unit differing from the device's
        # unit means this may arrive as a converted, non-integer value.
        target = max(
            self._attr_min_temp,
            min(self._attr_max_temp, round(kwargs[ATTR_TEMPERATURE])),
        )
        current = round(self._attr_target_temperature or self._attr_min_temp)
        if target == current:
            return

        code = DysonAm09Code.HEAT_UP if target > current else DysonAm09Code.HEAT_DOWN
        for step in range(abs(target - current)):
            if step:
                await asyncio.sleep(self._step_delay)
            await self._async_send_am09_action(code)

        self._attr_target_temperature = float(target)
        self.async_write_ha_state()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan speed by stepping SPEED_UP/SPEED_DOWN."""
        target = int(fan_mode)
        current = int(self._attr_fan_mode or _FAN_MODES[0])
        if target == current:
            return

        code = DysonAm09Code.SPEED_UP if target > current else DysonAm09Code.SPEED_DOWN
        for step in range(abs(target - current)):
            if step:
                await asyncio.sleep(self._step_delay)
            await self._async_send_am09_action(code)

        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Toggle oscillation.

        SWING has no dedicated on/off code, only a toggle, so resending it
        when already at the requested mode would flip it the wrong way.
        """
        if swing_mode == self._attr_swing_mode:
            return

        await self._async_send_am09_action(DysonAm09Code.SWING)
        self._attr_swing_mode = swing_mode
        self.async_write_ha_state()

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the airflow diffusion preset."""
        if preset_mode == self._attr_preset_mode:
            return

        code = (
            DysonAm09Code.VENT_THIN
            if preset_mode == PRESET_FOCUSED
            else DysonAm09Code.VENT_WIDE
        )
        await self._async_send_am09_action(code)
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()
