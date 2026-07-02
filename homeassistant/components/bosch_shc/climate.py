"""Platform for climate integration."""

import logging
from typing import Any, override

from boschshcpy import SHCClimateControl, SHCHeatingCircuit

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Preset mode strings (regulation axis — independent of hvac_mode direction axis).
# Design from PR #329 (jumlu): Bosch separates direction (HEATING/COOLING/OFF)
# from regulation (AUTOMATIC schedule vs MANUAL setpoint + eco/boost overrides).
# We map regulation onto HA preset_mode so AUTO is a preset, not an hvac_mode.
PRESET_AUTO = "auto"
PRESET_MANUAL = "manual"
PRESET_BOOST = "boost"
PRESET_ECO = "eco"


def _set_cool_mode(device: SHCClimateControl) -> None:
    """Set device to cooling mode (groups two sync writes into one executor job)."""
    device.summer_mode = False
    device.cooling_mode = True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC climate platform."""
    session = config_entry.runtime_data

    entities: list[ClimateEntity] = [
        SHCClimateControlEntity(
            device=climate,
            parent_id=session.information.unique_id,
            entry_id=config_entry.entry_id,
        )
        for climate in session.device_helper.climate_controls
    ]

    entities.extend(
        SHCHeatingCircuitEntity(
            device=heating_circuit,
            parent_id=session.information.unique_id,
            entry_id=config_entry.entry_id,
        )
        for heating_circuit in session.device_helper.heating_circuits
    )

    async_add_entities(entities)


class SHCClimateControlEntity(SHCEntity, ClimateEntity):
    """Representation of a SHC room climate control.

    Design from PR #329 (jumlu): two orthogonal Bosch axes mapped onto HA:
      Direction axis  → hvac_mode:   summer_mode=True→OFF, cooling_mode=True→COOL, else→HEAT
      Regulation axis → preset_mode: AUTOMATIC→"auto", MANUAL→"manual", + boost/eco overrides
    """

    _attr_name = None
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_max_temp = 30.0
    _attr_min_temp = 5.0
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        device: SHCClimateControl,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the SHC climate control entity."""
        super().__init__(device=device, parent_id=parent_id, entry_id=entry_id)
        self._attr_unique_id = f"{device.serial}_climate"

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.temperature

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the target temperature setpoint."""
        return self._device.setpoint_temperature

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return the hvac mode (direction axis).

        Maps the Bosch direction field onto HA hvac_mode:
          summer_mode=True                              → OFF
          supports_cooling=True + cooling_mode=True    → COOL
          otherwise                                     → HEAT
        The AUTOMATIC/MANUAL regulation axis is expressed via preset_mode.
        """
        if self._device.summer_mode:
            return HVACMode.OFF

        if self._device.supports_cooling and self._device.cooling_mode:
            return HVACMode.COOL

        return HVACMode.HEAT

    @property
    @override
    def hvac_modes(self) -> list[HVACMode]:
        """Return available hvac modes."""
        modes = [HVACMode.HEAT]
        if self._device.supports_cooling:
            modes.append(HVACMode.COOL)
        modes.append(HVACMode.OFF)
        return modes

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if (
            self._device.supports_cooling
            and self._device.cooling_mode
            and self.hvac_mode == HVACMode.COOL
        ):
            return HVACAction.COOLING
        return HVACAction.HEATING if self._device.has_demand else HVACAction.IDLE

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return preset mode (regulation axis).

        Maps the Bosch regulation fields onto HA preset_mode:
          boost_mode=True               → "boost"
          low=True (eco)                → "eco"   (only if device has `low`)
          operation_mode=AUTOMATIC      → "auto"
          operation_mode=MANUAL (else)  → "manual"
        """
        if self._device.supports_boost_mode and self._device.boost_mode:
            return PRESET_BOOST

        if self._device.supports_low and self._device.low:
            return PRESET_ECO

        if (
            self._device.operation_mode
            == SHCClimateControl.RoomClimateControlService.OperationMode.AUTOMATIC
        ):
            return PRESET_AUTO

        return PRESET_MANUAL

    @property
    @override
    def preset_modes(self) -> list[str] | None:
        """Return available preset modes."""
        presets = [PRESET_AUTO, PRESET_MANUAL]
        if self._device.supports_boost_mode:
            presets.append(PRESET_BOOST)
        if self._device.supports_low:
            presets.append(PRESET_ECO)
        return presets

    @property
    @override
    def supported_features(self) -> ClimateEntityFeature:
        """Return supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(hvac_mode)

        if self.hvac_mode == HVACMode.OFF:
            _LOGGER.debug(
                "Skipping setting temperature as device %s is off",
                self.name,
            )
            return

        if self.preset_mode == PRESET_BOOST:
            _LOGGER.warning(
                "Cannot set temperature on device %s while in BOOST mode",
                self.name,
            )
            return

        if self._attr_min_temp <= temperature <= self._attr_max_temp:
            # SHC rejects a setpoint write while operationMode=AUTOMATIC.
            # For a bare set_temperature (no hvac_mode given) drop to MANUAL
            # first — matching the Bosch app. #73 #180
            if (
                kwargs.get(ATTR_HVAC_MODE) is None
                and self._device.operation_mode
                == SHCClimateControl.RoomClimateControlService.OperationMode.AUTOMATIC
            ):
                await self.hass.async_add_executor_job(
                    setattr,
                    self._device,
                    "operation_mode",
                    SHCClimateControl.RoomClimateControlService.OperationMode.MANUAL,
                )
            await self.hass.async_add_executor_job(
                setattr,
                self._device,
                "setpoint_temperature",
                float(round(temperature * 2.0) / 2.0),
            )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode (direction axis).

        Exit ECO (low) before applying any HVAC mode change so that
        turn_off / mode changes are never silently no-oped. #196
        """
        if hvac_mode not in self.hvac_modes:
            return

        # Exit ECO (low) before applying any HVAC mode change
        if self._device.supports_low and self._device.low:
            await self.hass.async_add_executor_job(setattr, self._device, "low", False)

        if hvac_mode == HVACMode.HEAT:
            await self.hass.async_add_executor_job(
                setattr, self._device, "summer_mode", False
            )
            if self._device.supports_cooling:
                await self.hass.async_add_executor_job(
                    setattr, self._device, "cooling_mode", False
                )
        elif hvac_mode == HVACMode.COOL:
            await self.hass.async_add_executor_job(_set_cool_mode, self._device)
        elif hvac_mode == HVACMode.OFF:
            if self._device.supports_cooling:
                await self.hass.async_add_executor_job(
                    setattr, self._device, "cooling_mode", False
                )
            await self.hass.async_add_executor_job(
                setattr, self._device, "summer_mode", True
            )

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode (regulation axis).

        "auto"   → operationMode=AUTOMATIC (follow schedule)
        "manual" → operationMode=MANUAL + clear boost + clear eco
        "boost"  → boost_mode=True
        "eco"    → low=True  (only if device exposes `low`)
        """
        if self.preset_modes is None or preset_mode not in self.preset_modes:
            return

        if preset_mode == PRESET_BOOST:
            await self.hass.async_add_executor_job(
                setattr, self._device, "boost_mode", True
            )

        elif preset_mode == PRESET_ECO:
            # Clear boost first so states don't stack
            if self._device.supports_boost_mode and self._device.boost_mode:
                await self.hass.async_add_executor_job(
                    setattr, self._device, "boost_mode", False
                )
            await self.hass.async_add_executor_job(setattr, self._device, "low", True)

        elif preset_mode == PRESET_AUTO:
            # Clear overrides then set schedule mode
            if self._device.supports_boost_mode and self._device.boost_mode:
                await self.hass.async_add_executor_job(
                    setattr, self._device, "boost_mode", False
                )
            if self._device.supports_low and self._device.low:
                await self.hass.async_add_executor_job(
                    setattr, self._device, "low", False
                )
            await self.hass.async_add_executor_job(
                setattr,
                self._device,
                "operation_mode",
                SHCClimateControl.RoomClimateControlService.OperationMode.AUTOMATIC,
            )

        elif preset_mode == PRESET_MANUAL:
            # Clear overrides then set manual mode
            if self._device.supports_boost_mode and self._device.boost_mode:
                await self.hass.async_add_executor_job(
                    setattr, self._device, "boost_mode", False
                )
            if self._device.supports_low and self._device.low:
                await self.hass.async_add_executor_job(
                    setattr, self._device, "low", False
                )
            await self.hass.async_add_executor_job(
                setattr,
                self._device,
                "operation_mode",
                SHCClimateControl.RoomClimateControlService.OperationMode.MANUAL,
            )

    @override
    async def async_turn_on(self) -> None:
        """Turn the climate device on."""
        if self.hvac_mode == HVACMode.OFF:
            await self.async_set_hvac_mode(HVACMode.HEAT)

    @override
    async def async_turn_off(self) -> None:
        """Turn the climate device off."""
        if self.hvac_mode != HVACMode.OFF:
            await self.async_set_hvac_mode(HVACMode.OFF)


class SHCHeatingCircuitEntity(SHCEntity, ClimateEntity):
    """Representation of a SHC heating circuit.

    The HeatingCircuit service exposes a setpoint temperature and an operation
    mode (AUTOMATIC/MANUAL); there is no measured room temperature and the on
    state is read-only, so this maps to a HEAT/AUTO climate entity with a
    heating/idle action and no OFF mode.
    """

    _attr_name = None
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_max_temp = 30.0
    _attr_min_temp = 5.0
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(
        self,
        device: SHCHeatingCircuit,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the SHC heating circuit entity."""
        super().__init__(device=device, parent_id=parent_id, entry_id=entry_id)
        self._attr_unique_id = f"{device.serial}_heating_circuit"

    @property
    @override
    def current_temperature(self) -> float | None:
        """Heating circuits expose no measured temperature."""
        return None

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the setpoint temperature."""
        return self._device.setpoint_temperature

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return the hvac mode derived from the operation mode."""
        if (
            self._device.operation_mode
            == SHCHeatingCircuit.HeatingCircuitService.OperationMode.AUTOMATIC
        ):
            return HVACMode.AUTO
        return HVACMode.HEAT

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        """Return whether the circuit is currently heating."""
        return HVACAction.HEATING if self._device.on else HVACAction.IDLE

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new setpoint temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        if self._attr_min_temp <= temperature <= self._attr_max_temp:
            await self.hass.async_add_executor_job(
                setattr,
                self._device,
                "setpoint_temperature",
                float(round(temperature * 2.0) / 2.0),
            )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the operation mode."""
        if hvac_mode not in self.hvac_modes:
            return
        mode = (
            SHCHeatingCircuit.HeatingCircuitService.OperationMode.AUTOMATIC
            if hvac_mode == HVACMode.AUTO
            else SHCHeatingCircuit.HeatingCircuitService.OperationMode.MANUAL
        )
        await self.hass.async_add_executor_job(
            setattr, self._device, "operation_mode", mode
        )
