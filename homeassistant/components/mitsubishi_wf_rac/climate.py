"""for Climate integration."""

import logging
from typing import Any, override

from pywfrac import Aircon, AirconCommands

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    PRESET_AWAY,
    PRESET_NONE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MitsubishiWfRacConfigEntry
from .const import (
    CONF_INDOOR_OFFSET,
    DOMAIN,
    FAN_MODE_TRANSLATION,
    HOME_LEAVE_TEMP_COOL,
    HOME_LEAVE_TEMP_HEAT,
    HVAC_TRANSLATION,
    NORMAL_TEMP,
    SUPPORT_FLAGS,
    SUPPORT_SWING_HORIZONTAL_MODES,
    SUPPORT_SWING_MODES,
    SUPPORTED_FAN_MODES,
    SUPPORTED_HVAC_MODES,
    SWING_3D_AUTO,
    SWING_HORIZONTAL_AUTO,
    SWING_HORIZONTAL_MODE_TRANSLATION,
    SWING_MODE_TRANSLATION,
    SWING_VERTICAL_AUTO,
)
from .coordinator import Device
from .entity import WfRacEntity

_LOGGER = logging.getLogger(__name__)
# The module accepts one connection at a time and wants a second between
# requests, so entity actions that reach the device run one after another.
PARALLEL_UPDATES = 1

# The modes whose setpoint the unit actually regulates on. Off and fan-only
# have no setpoint of their own - see _setpoint_range_for_mode.
REGULATING_HVAC_MODES = (HVACMode.AUTO, HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MitsubishiWfRacConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup climate entities."""
    device: Device = entry.runtime_data.device
    _LOGGER.info("Setup climate for: %s, %s", device.device_name, device.airco_id)
    async_add_entities([AircoClimate(device)])


class AircoClimate(WfRacEntity, ClimateEntity):
    """Representation of a climate entity."""

    _attr_supported_features: ClimateEntityFeature = SUPPORT_FLAGS
    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS
    _attr_hvac_modes: list[HVACMode] = SUPPORTED_HVAC_MODES
    _attr_fan_modes: list[str] = SUPPORTED_FAN_MODES
    _attr_hvac_mode: HVACMode = HVACMode.OFF
    _attr_hvac_action: HVACAction | None = None
    _attr_fan_mode: str = FAN_AUTO
    _attr_swing_mode: str | None = SWING_VERTICAL_AUTO
    _attr_swing_modes: list[str] | None = SUPPORT_SWING_MODES
    _attr_swing_horizontal_mode: str | None = SWING_HORIZONTAL_AUTO
    _attr_swing_horizontal_modes: list[str] | None = SUPPORT_SWING_HORIZONTAL_MODES
    # 0.5 K is what the wire format carries: the setpoint byte is
    # int(PresetTemp / 0.5), which truncates. Without declaring the step, HA
    # offers 0.1 K and the unit silently drops the remainder - 21.4 arrives as
    # 21.0. A target_offset that isn't a multiple of 0.5 still shifts the
    # displayed target off the grid; that is the offset's job, and it stays
    # visible rather than the UI promising a resolution the device lacks.
    _attr_target_temperature_step: float = 0.5
    # Only filled in when the model reports VacantProperty (see __init__);
    # ClimateEntity has no class-level default for either of these.
    _attr_preset_modes: list[str] | None = None
    _attr_preset_mode: str | None = None
    _attr_translation_key = "mitsubishi_wf_rac"

    def __init__(self, device: Device) -> None:
        """Initialize the climate entity."""
        super().__init__(device)
        self._attr_name = device.device_name
        self._attr_unique_id = f"{DOMAIN}-{self._device.airco_id}-climate"
        # Away is the unit's own Home Leave mode, offered here as the preset a
        # thermostat card and a voice assistant already know how to ask for.
        # HomeLeaveModeSelect in select.py stays: it can name the direction
        # (away_cool/away_heat), which a single preset cannot, and it is what
        # existing automations target. Same capability gate as that select.
        if device.airco.Capabilities.vacant_property:
            self._attr_supported_features = (
                SUPPORT_FLAGS | ClimateEntityFeature.PRESET_MODE
            )
            self._attr_preset_modes = [PRESET_NONE, PRESET_AWAY]
        self._update_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Register with the coordinator and publish the first state."""
        await super().async_added_to_hass()
        self._update_state()

    def _min_temp_for_mode(self, hvac_mode: HVACMode) -> float:
        """Minimum setpoint depends on hvac_mode.

        Per Mitsubishi Heavy Industries' official operable table ('21
        SRK-T-324, models SRK60ZSX-W/A and SRK100ZR-W): indoor unit only
        accepts 18-30C. Cooling reliably goes lower than that in practice
        regardless of model, so that override applies unconditionally.
        Models with the app's PresetTempRange2 capability (`ModelNoType`/
        `TempItemType` in the app, see pywfrac's capabilities module) go further,
        per the app's own table (Constants.java TempItemType.getMin/getMax):
        Auto/Cool/Dry down to 16, Heat down to 10. That 10C heating floor is
        unconfirmed on real hardware - the plain-setpoint reset to 18C after a
        power cycle that's documented for the default range was only ever
        observed on hardware without this capability.
        """
        if self._device.airco.Capabilities.preset_temp_range_2:
            if hvac_mode == HVACMode.HEAT:
                return 10
            if hvac_mode in (HVACMode.COOL, HVACMode.DRY, HVACMode.AUTO):
                return 16
        return 16 if hvac_mode == HVACMode.COOL else 18

    def _max_temp_for_mode(self, hvac_mode: HVACMode) -> float:
        """Return the highest setpoint this hvac_mode allows.

        Depends on hvac_mode for PresetTempRange2 models - see
        _min_temp_for_mode.
        """
        if self._device.airco.Capabilities.preset_temp_range_2 and hvac_mode in (
            HVACMode.COOL,
            HVACMode.DRY,
        ):
            return 33
        return 30

    def _setpoint_range_for_mode(self, hvac_mode: HVACMode) -> tuple[float, float]:
        """The range a setpoint is held to, for display and before sending.

        A regulating mode is held to its own range. Off and fan-only have none:
        the value applies to whichever regulating mode is turned on next, often
        in the very next step of the same automation. Holding it to the default
        18C floor there rejects a cooling setpoint the unit takes happily once
        it is cooling, which is what it did until #317.
        """
        if hvac_mode in REGULATING_HVAC_MODES:
            return (
                self._min_temp_for_mode(hvac_mode),
                self._max_temp_for_mode(hvac_mode),
            )
        return (
            min(self._min_temp_for_mode(mode) for mode in REGULATING_HVAC_MODES),
            max(self._max_temp_for_mode(mode) for mode in REGULATING_HVAC_MODES),
        )

    @override
    @property
    def min_temp(self) -> float:
        """Return the lowest setpoint the current mode allows."""
        return self._setpoint_range_for_mode(self._attr_hvac_mode)[0]

    @override
    @property
    def max_temp(self) -> float:
        """Return the highest setpoint the current mode allows."""
        return self._setpoint_range_for_mode(self._attr_hvac_mode)[1]

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        set_temp = kwargs.get(ATTR_TEMPERATURE)
        if set_temp is None:
            raise ServiceValidationError(
                "Temperature is required",
                translation_domain=DOMAIN,
                translation_key="temperature_required",
            )

        # If this call also switches hvac_mode, the minimum must reflect the mode
        # being switched to, not the (still stale until the next poll) current one.
        target_hvac_mode = kwargs.get("hvac_mode", self._attr_hvac_mode)
        target_hvac_mode = (
            HVACMode.OFF if target_hvac_mode is None else target_hvac_mode
        )
        min_temp, max_temp = self._setpoint_range_for_mode(target_hvac_mode)

        # Naming the mode is the whole message: the range depends on it, and
        # an automation that sets a setpoint before switching mode gets
        # measured against the mode it is leaving. Saying so - and that
        # hvac_mode belongs in the same call - is the difference between a
        # rejection and a fix (#317).
        if set_temp < min_temp:
            raise ServiceValidationError(
                f"Temperature {set_temp} is below minimum {min_temp}",
                translation_domain=DOMAIN,
                translation_key="temperature_below_minimum",
                translation_placeholders={
                    "temperature": str(set_temp),
                    "min_temp": str(min_temp),
                    "hvac_mode": str(target_hvac_mode),
                },
            )

        if set_temp > max_temp:
            raise ServiceValidationError(
                f"Temperature {set_temp} is above maximum {max_temp}",
                translation_domain=DOMAIN,
                translation_key="temperature_above_maximum",
                translation_placeholders={
                    "temperature": str(set_temp),
                    "max_temp": str(max_temp),
                    "hvac_mode": str(target_hvac_mode),
                },
            )

        # The AC unit's own thermostat logic uses its own indoor sensor reading,
        # subject to the same calibration bias CONF_INDOOR_OFFSET corrects for
        # display (see sensor.py). To make the unit actually reach the
        # user-requested real room temperature despite that bias, the offset is
        # subtracted from the commanded setpoint before sending - the displayed
        # target_temperature itself is unaffected. Resolved against the mode
        # the unit will be in after this command (target_hvac_mode), since
        # cooling and heating have opposite-sign return-air bias.
        target_offset = self._resolve_target_offset(target_hvac_mode)
        target_temp = set_temp - target_offset
        target_temp = max(min_temp, min(max_temp, target_temp))

        opts: dict[AirconCommands, Any] = {AirconCommands.PresetTemp: target_temp}

        if "hvac_mode" in kwargs:
            opts.update(
                {
                    AirconCommands.OperationMode: self._device.airco.OperationMode
                    if target_hvac_mode == HVACMode.OFF
                    else HVAC_TRANSLATION[target_hvac_mode],
                    AirconCommands.Operation: target_hvac_mode != HVACMode.OFF,
                }
            )

        await self._device.async_queue_command(opts)

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self._device.async_queue_command(
            {AirconCommands.AirFlow: FAN_MODE_TRANSLATION[fan_mode]}
        )

    @override
    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self._device.async_queue_command({AirconCommands.Operation: True})

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self._device.async_queue_command(
            {
                AirconCommands.OperationMode: self._device.airco.OperationMode
                if hvac_mode == HVACMode.OFF
                else HVAC_TRANSLATION[hvac_mode],
                AirconCommands.Operation: hvac_mode != HVACMode.OFF,
            }
        )

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        _swing_auto = swing_mode == SWING_3D_AUTO
        if _swing_auto:
            await self._device.async_queue_command(
                {
                    AirconCommands.Entrust: _swing_auto,
                }
            )
        else:
            await self._device.async_queue_command(
                {
                    AirconCommands.WindDirectionUD: SWING_MODE_TRANSLATION[swing_mode],
                    AirconCommands.Entrust: False,
                }
            )

    @override
    async def async_set_swing_horizontal_mode(self, swing_mode: str) -> None:
        """Set new target horizontal swing operation."""
        _swing_auto = swing_mode == SWING_3D_AUTO
        if _swing_auto:
            await self._device.async_queue_command(
                {
                    AirconCommands.Entrust: _swing_auto,
                }
            )
        else:
            await self._device.async_queue_command(
                {
                    AirconCommands.WindDirectionLR: SWING_HORIZONTAL_MODE_TRANSLATION[
                        swing_mode
                    ],
                    AirconCommands.Entrust: False,
                }
            )

    @override
    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self._device.async_queue_command({AirconCommands.Operation: False})

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Enter or leave the unit's Home Leave mode.

        The unit has no single "away" command: it enters the mode when it is
        given the away target of the direction it is running in, which is why
        the current hvac_mode decides between them. A unit in auto, dry or
        fan-only has no such target to send, so the direction has to be named
        through HomeLeaveModeSelect instead of guessed at here.
        """
        if preset_mode == PRESET_NONE:
            await self._device.async_queue_command(
                {AirconCommands.PresetTemp: NORMAL_TEMP}
            )
            return

        if self._attr_hvac_mode == HVACMode.COOL:
            away_temp = HOME_LEAVE_TEMP_COOL
        elif self._attr_hvac_mode == HVACMode.HEAT:
            away_temp = HOME_LEAVE_TEMP_HEAT
        else:
            raise ServiceValidationError(
                f"Home Leave mode needs cooling or heating, not {self._attr_hvac_mode}",
                translation_domain=DOMAIN,
                translation_key="preset_away_needs_cool_or_heat",
                translation_placeholders={"hvac_mode": str(self._attr_hvac_mode)},
            )

        await self._device.async_queue_command(
            {
                AirconCommands.Operation: True,
                AirconCommands.OperationMode: HVAC_TRANSLATION[self._attr_hvac_mode],
                AirconCommands.PresetTemp: away_temp,
            }
        )

    def _require_home_leave_mode_capability(self) -> None:
        if not self._device.airco.Capabilities.home_leave_mode:
            raise ServiceValidationError(
                "This model does not report the HomeLeaveMode capability",
                translation_domain=DOMAIN,
                translation_key="home_leave_mode_not_supported",
            )

    @override
    def _update_state(self) -> None:
        """Private update attributes."""
        airco = self._device.airco

        # Apply indoor offset
        indoor_offset = self._device.options.get(CONF_INDOOR_OFFSET, 0.0)
        # Both the displayed hvac_mode and the target_offset resolution need
        # the underlying cool/heat mode, so it's computed once here and shared
        # between them.
        mode_from_operation = self._hvac_mode_from_operation
        # Mirror the subtraction in async_set_temperature() so the displayed
        # target_temperature agrees with what the user set - PresetTemp itself
        # holds the offset-lowered value that was actually sent to the device.
        target_offset = self._resolve_target_offset(mode_from_operation)

        self._attr_target_temperature = airco.PresetTemp + target_offset
        # The unit's own reading, plus the calibration offset that corrects it.
        self._attr_current_temperature = airco.IndoorTemp + indoor_offset
        self._attr_fan_mode = list(FAN_MODE_TRANSLATION.keys())[airco.AirFlow]
        self._attr_swing_mode = (
            SWING_3D_AUTO
            if airco.Entrust
            else list(SWING_MODE_TRANSLATION.keys())[airco.WindDirectionUD]
        )
        self._attr_swing_horizontal_mode = (
            SWING_3D_AUTO
            if airco.Entrust
            else list(SWING_HORIZONTAL_MODE_TRANSLATION.keys())[airco.WindDirectionLR]
        )
        self._attr_hvac_mode = mode_from_operation

        if airco.Operation is False:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF
        else:
            _new_mode: HVACMode = HVACMode.OFF
            _mode = airco.OperationMode
            if _mode == 0:
                _new_mode = HVACMode.AUTO
            elif _mode == 1:
                _new_mode = HVACMode.COOL
            elif _mode == 2:
                _new_mode = HVACMode.HEAT
            elif _mode == 3:
                _new_mode = HVACMode.FAN_ONLY
            elif _mode == 4:
                _new_mode = HVACMode.DRY
            self._attr_hvac_mode = _new_mode

            # Determine hvac_action based on operation mode and state
            self._attr_hvac_action = self._determine_hvac_action(airco)

        # Read back from the same Vacant bit HomeLeaveModeSelect uses, so the
        # two never disagree - including when the mode was entered from the
        # official app or the IR remote.
        if self.supported_features & ClimateEntityFeature.PRESET_MODE:
            self._attr_preset_mode = PRESET_AWAY if airco.Vacant else PRESET_NONE

    def _determine_hvac_action(self, airco: Aircon) -> HVACAction:
        """Determine the current HVAC action from operation mode and state.

        CoolHotJudge (content[8] & 8) reflects what the unit's own AUTO logic
        is doing - set means COOLING, clear means HEATING. CompressorRunning
        (content[9] & 2) distinguishes "unit on" from "compressor actually
        running" (e.g. setpoint satisfied), same signal as the Compressor
        binary sensor - used here so COOL/HEAT/AUTO can report IDLE instead
        of claiming to cool/heat while the compressor is stopped.
        """
        if not airco.Operation:
            return HVACAction.OFF

        _mode = airco.OperationMode

        # FAN_ONLY mode
        if _mode == 3:
            return HVACAction.FAN

        # DRY mode
        if _mode == 4:
            return HVACAction.DRYING

        if not airco.CompressorRunning:
            return HVACAction.IDLE

        # AUTO mode - use CoolHotJudge directly (unit tells us what it's doing)
        if _mode == 0:
            return HVACAction.HEATING if airco.CoolHotJudge else HVACAction.COOLING

        # COOL mode
        if _mode == 1:
            return HVACAction.COOLING

        # HEAT mode
        if _mode == 2:
            return HVACAction.HEATING

        # Unknown mode with compressor running - nothing better to report
        return HVACAction.IDLE
