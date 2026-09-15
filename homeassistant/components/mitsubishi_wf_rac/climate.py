"""for Climate integration."""

import logging
from typing import Any, override

from pywfrac import AIRFLOW_UNKNOWN, Aircon, AirconCommands

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_AUTO,
    PRESET_AWAY,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
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
from .coordinator import Device, MitsubishiWfRacConfigEntry
from .entity import WfRacEntity

_LOGGER = logging.getLogger(__name__)
# Zero although this platform writes: the coordinator serialises and spaces
# the requests itself, and merges the ones issued together.
PARALLEL_UPDATES = 0

# The modes whose setpoint the unit actually regulates on. Off and fan-only
# have no setpoint of their own - see _setpoint_range_for_mode.
REGULATING_HVAC_MODES = (HVACMode.AUTO, HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MitsubishiWfRacConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the climate entity."""
    device: Device = entry.runtime_data.device
    async_add_entities([AircoClimate(device)])


def _without_3d_auto(modes: list[str]) -> list[str]:
    """The mode list a unit gets when it cannot hand both vanes to the unit."""
    return [mode for mode in modes if mode != SWING_3D_AUTO]


class AircoClimate(WfRacEntity, ClimateEntity):
    """Representation of a climate entity."""

    _attr_supported_features: ClimateEntityFeature = SUPPORT_FLAGS
    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS
    _attr_hvac_modes: list[HVACMode] = SUPPORTED_HVAC_MODES
    _attr_fan_modes: list[str] = SUPPORTED_FAN_MODES
    _attr_hvac_action: HVACAction | None = None
    _attr_fan_mode: str | None = FAN_AUTO
    _attr_swing_mode: str | None = SWING_VERTICAL_AUTO
    _attr_swing_modes: list[str] | None = SUPPORT_SWING_MODES
    _attr_swing_horizontal_mode: str | None = SWING_HORIZONTAL_AUTO
    _attr_swing_horizontal_modes: list[str] | None = SUPPORT_SWING_HORIZONTAL_MODES
    # The setpoint byte is int(PresetTemp / 0.5), which truncates - so the
    # card offers halves, and async_set_temperature rounds to one before
    # sending, since nothing validates this step on the way in.
    _attr_target_temperature_step: float = 0.5
    # Filled in only for a model that reports VacantProperty (see __init__).
    _attr_preset_modes: list[str] | None = None
    _attr_preset_mode: str | None = None
    _attr_translation_key = "mitsubishi_wf_rac"
    # This entity is the device, so it carries the device name alone.
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device: Device) -> None:
        """Initialize the climate entity."""
        super().__init__(device)
        # Redundant segments, but this id is stored in ~1900 installations of
        # the custom component: shortening it orphans every named entity.
        # pylint: disable-next=home-assistant-entity-unique-id-redundant-domain,home-assistant-entity-unique-id-redundant-platform
        self._attr_unique_id = f"{DOMAIN}-{self._device.airco_id}-climate"
        capabilities = device.airco.Capabilities
        features = SUPPORT_FLAGS
        # Away is the unit's own Home Leave mode, under the name a thermostat
        # card and a voice assistant already ask for.
        if capabilities.vacant_property:
            features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = [PRESET_NONE, PRESET_AWAY]
        # The left/right vane and 3D auto belong to the model line: the
        # manufacturer's table has both off for the ceiling cassettes, which
        # have no horizontal vane to aim.
        if capabilities.wind_direction_lr:
            features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE
        else:
            self._attr_swing_horizontal_mode = None
            self._attr_swing_horizontal_modes = None
        if not capabilities.entrust:
            self._attr_swing_modes = _without_3d_auto(SUPPORT_SWING_MODES)
            if self._attr_swing_horizontal_modes is not None:
                self._attr_swing_horizontal_modes = _without_3d_auto(
                    SUPPORT_SWING_HORIZONTAL_MODES
                )
        self._attr_supported_features = features
        self._apply_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Register with the coordinator and publish the first state."""
        await super().async_added_to_hass()
        self._apply_state()

    def _min_temp_for_mode(self, hvac_mode: HVACMode) -> float:
        """Minimum setpoint depends on hvac_mode.

        The manufacturer's operable table ('21 SRK-T-324) gives 18-30C
        throughout, but cooling goes lower on every model. PresetTempRange2
        models go further per the app's own table: Auto/Cool/Dry to 16, Heat
        to 10 - that heating floor is unconfirmed on hardware.
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

    def _setpoint_range_for_mode(
        self, hvac_mode: HVACMode | None
    ) -> tuple[float, float]:
        """The range a setpoint is held to before it is sent.

        A regulating mode is held to its own range; off, fan-only and an
        unreadable mode get the union, since the value applies to whichever
        mode comes next. The union is where the advertised range starts too,
        because climate validates against it before this entity sees hvac_mode.
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

    def _advertised_range(self) -> tuple[float, float]:
        """The range HA validates against, and the one the slider offers.

        Wider than that union wherever the away preset is offered: Home Leave
        runs at 31C cooling and 10C heating, which the unit reports back as
        its target temperature. They stay reachable through the preset alone -
        a setpoint sent by hand is still held to its mode's range.
        """
        min_temp, max_temp = self._setpoint_range_for_mode(None)
        if self._attr_preset_modes:
            return (
                min(min_temp, HOME_LEAVE_TEMP_HEAT),
                max(max_temp, HOME_LEAVE_TEMP_COOL),
            )
        return (min_temp, max_temp)

    @override
    @property
    def min_temp(self) -> float:
        """Return the lowest setpoint any of this unit's modes allows."""
        return self._advertised_range()[0]

    @override
    @property
    def max_temp(self) -> float:
        """Return the highest setpoint any of this unit's modes allows."""
        return self._advertised_range()[1]

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        set_temp = kwargs[ATTR_TEMPERATURE]

        # The service schema coerces hvac_mode to the enum without checking
        # it against the modes this entity offers.
        requested_hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
        if requested_hvac_mode is not None:
            self._valid_mode_or_raise("hvac", requested_hvac_mode, self.hvac_modes)

        # A call that switches hvac_mode is measured against the mode it
        # switches to, not the one still reported until the next poll.
        target_hvac_mode = (
            requested_hvac_mode
            if requested_hvac_mode is not None
            else self._attr_hvac_mode
        )
        target_hvac_mode = (
            HVACMode.OFF if target_hvac_mode is None else target_hvac_mode
        )
        min_temp, max_temp = self._setpoint_range_for_mode(target_hvac_mode)

        # The message names the mode, which is what tells an automation that
        # set the setpoint first why its value was refused.
        if set_temp < min_temp:
            raise ServiceValidationError(
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
                translation_domain=DOMAIN,
                translation_key="temperature_above_maximum",
                translation_placeholders={
                    "temperature": str(set_temp),
                    "max_temp": str(max_temp),
                    "hvac_mode": str(target_hvac_mode),
                },
            )

        # Nothing validates the step on the way in, and the frame truncates:
        # rounded here, 21.4 reaches the unit as 21.5 rather than 21.0.
        opts: dict[AirconCommands, Any] = {
            AirconCommands.PresetTemp: round(set_temp * 2) / 2
        }

        if requested_hvac_mode is not None:
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
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new target horizontal swing operation."""
        swing_mode = swing_horizontal_mode
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

        The unit has no single "away" command: it enters the mode on the away
        target of the direction it is running in, so the current hvac_mode
        decides. Auto, dry and fan-only have no such target.
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

    @override
    def _mark_state_unknown(self) -> None:
        self._attr_hvac_mode = None
        self._attr_hvac_action = None
        self._attr_target_temperature = None
        self._attr_current_temperature = None
        self._attr_fan_mode = None
        self._attr_swing_mode = None
        self._attr_swing_horizontal_mode = None
        self._attr_preset_mode = None

    @override
    def _update_state(self) -> None:
        """Private update attributes."""
        airco = self._device.airco

        # OperationMode keeps reporting cool/heat while the unit is off.
        mode_from_operation = self._hvac_mode_from_operation

        self._attr_target_temperature = airco.PresetTemp
        self._attr_current_temperature = airco.IndoorTemp
        # Named rather than left to index past the end of the list: a sixth
        # fan mode here would turn the library's "could not read it" marker
        # into a real step and lose the unknown state without a sound.
        if airco.AirFlow == AIRFLOW_UNKNOWN:
            raise IndexError("the unit reported a fan step pywfrac cannot read")
        self._attr_fan_mode = list(FAN_MODE_TRANSLATION.keys())[airco.AirFlow]
        # Only where it is offered: a model line whose table has no 3D auto can
        # still have the bit set in its frame, and a state that is not in
        # swing_modes is one the user cannot select back.
        entrusted = airco.Entrust and SWING_3D_AUTO in (self._attr_swing_modes or ())
        self._attr_swing_mode = (
            SWING_3D_AUTO
            if entrusted
            else list(SWING_MODE_TRANSLATION.keys())[airco.WindDirectionUD]
        )
        if self.supported_features & ClimateEntityFeature.SWING_HORIZONTAL_MODE:
            self._attr_swing_horizontal_mode = (
                SWING_3D_AUTO
                if entrusted
                else list(SWING_HORIZONTAL_MODE_TRANSLATION.keys())[
                    airco.WindDirectionLR
                ]
            )
        self._attr_hvac_mode = mode_from_operation

        if airco.Operation is False:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF
        else:
            self._attr_hvac_action = self._determine_hvac_action(airco)

        # Read back from the Vacant bit, so the preset also follows a Home
        # Leave entered from the official app or the IR remote.
        if self.supported_features & ClimateEntityFeature.PRESET_MODE:
            self._attr_preset_mode = PRESET_AWAY if airco.Vacant else PRESET_NONE

    def _determine_hvac_action(self, airco: Aircon) -> HVACAction:
        """Determine the current HVAC action from operation mode and state.

        CoolHotJudge reflects the unit's own AUTO logic and is inverted - the
        parser reads (content[8] & 8) == 0, so a true CoolHotJudge is HEATING.
        CompressorRunning separates "on" from "running", so a satisfied
        setpoint reports IDLE.
        """
        _mode = airco.OperationMode

        if _mode == 3:
            return HVACAction.FAN

        if _mode == 4:
            return HVACAction.DRYING

        if not airco.CompressorRunning:
            return HVACAction.IDLE

        # AUTO leaves the direction to the unit, so ask it what it picked.
        if _mode == 0:
            return HVACAction.HEATING if airco.CoolHotJudge else HVACAction.COOLING

        if _mode == 1:
            return HVACAction.COOLING

        return HVACAction.HEATING
