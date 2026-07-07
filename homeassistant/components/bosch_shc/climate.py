"""Platform for climate integration."""

from typing import Any, override

from boschshcpy import SHCClimateControl, SHCHeatingCircuit

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PRESET_BOOST,
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .const import DOMAIN
from .entity import SHCEntity

PARALLEL_UPDATES = 1


def _set_cool_mode(device: SHCClimateControl) -> None:
    """Set device to cooling mode."""
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

    Two orthogonal Bosch axes are mapped onto HA:
      Direction axis  → hvac_mode:   summer_mode=True→OFF, cooling_mode=True→COOL,
                                      operation_mode=AUTOMATIC→AUTO, else→HEAT
      Regulation axis → preset_mode: transient overrides only — boost/eco
    AUTO is a real hvac_mode (not a preset) so the thermostat card renders as
    idle/following-schedule instead of permanently showing the HEAT color
    while the schedule is in control.
    """

    _attr_name = None
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_max_temp = 30.0
    _attr_min_temp = 5.0

    @property
    @override
    def supported_features(self) -> ClimateEntityFeature:
        """Return supported features.

        PRESET_MODE is only advertised when the device actually has a boost
        or eco override to offer.
        """
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        if self.preset_modes:
            features |= ClimateEntityFeature.PRESET_MODE
        return features

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
          operation_mode=AUTOMATIC                      → AUTO
          otherwise (MANUAL)                            → HEAT
        """
        if self._device.summer_mode:
            return HVACMode.OFF

        if self._device.supports_cooling and self._device.cooling_mode:
            return HVACMode.COOL

        if (
            self._device.operation_mode
            == SHCClimateControl.RoomClimateControlService.OperationMode.AUTOMATIC
        ):
            return HVACMode.AUTO

        return HVACMode.HEAT

    @property
    @override
    def hvac_modes(self) -> list[HVACMode]:
        """Return available hvac modes."""
        modes = [HVACMode.AUTO, HVACMode.HEAT]
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
        """Return preset mode (transient overrides only).

        boost_mode=True   → "boost"  (only if device supports boost)
        low=True (eco)    → "eco"    (only if device has `low`)
        otherwise         → None
        """
        if self._device.supports_boost_mode and self._device.boost_mode:
            return PRESET_BOOST

        if self._device.supports_low and self._device.low:
            return PRESET_ECO

        return None

    @property
    @override
    def preset_modes(self) -> list[str] | None:
        """Return available preset modes.

        Returns None when the device offers neither override (no PRESET_MODE
        feature is advertised in that case).
        """
        presets = []
        if self._device.supports_boost_mode:
            presets.append(PRESET_BOOST)
        if self._device.supports_low:
            presets.append(PRESET_ECO)
        return presets or None

    @override
    def set_temperature(self, **kwargs: Any) -> None:
        """Set the temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode == HVACMode.OFF or (
            hvac_mode is None and self.hvac_mode == HVACMode.OFF
        ):
            # Reject before touching the device — applying hvac_mode=off
            # first would turn it off as a side effect of a call that's
            # about to fail anyway.
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="set_temperature_while_off",
                translation_placeholders={"name": self._device.name},
            )

        if hvac_mode is not None:
            self.set_hvac_mode(hvac_mode)

        if hvac_mode == HVACMode.AUTO:
            # The schedule controls the setpoint in AUTO; honour the mode
            # change and stop here rather than falling through to the
            # AUTOMATIC→MANUAL write below.
            return

        if self.preset_mode == PRESET_BOOST:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="set_temperature_while_boost",
                translation_placeholders={"name": self._device.name},
            )

        # SHC rejects a setpoint write while operationMode=AUTOMATIC; drop to
        # MANUAL first, matching the Bosch app.
        if (
            self._device.operation_mode
            == SHCClimateControl.RoomClimateControlService.OperationMode.AUTOMATIC
        ):
            self._device.operation_mode = (
                SHCClimateControl.RoomClimateControlService.OperationMode.MANUAL
            )
        self._device.setpoint_temperature = float(round(temperature * 2.0) / 2.0)

    @override
    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode (direction axis).

        Exit ECO (low) before applying any HVAC mode change so that
        turn_off / mode changes are never silently no-oped.
        """
        if hvac_mode not in self.hvac_modes:
            return

        if self._device.supports_low and self._device.low:
            self._device.low = False

        if hvac_mode == HVACMode.AUTO:
            self._device.summer_mode = False
            if self._device.supports_cooling:
                self._device.cooling_mode = False
            self._device.operation_mode = (
                SHCClimateControl.RoomClimateControlService.OperationMode.AUTOMATIC
            )
        elif hvac_mode == HVACMode.HEAT:
            self._device.summer_mode = False
            if self._device.supports_cooling:
                self._device.cooling_mode = False
            self._device.operation_mode = (
                SHCClimateControl.RoomClimateControlService.OperationMode.MANUAL
            )
        elif hvac_mode == HVACMode.COOL:
            _set_cool_mode(self._device)
        elif hvac_mode == HVACMode.OFF:
            if self._device.supports_cooling:
                self._device.cooling_mode = False
            self._device.summer_mode = True

    @override
    def set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode (transient overrides only).

        "boost"  → boost_mode=True
        "eco"    → low=True  (only if device exposes `low`)
        """
        if self.preset_modes is None or preset_mode not in self.preset_modes:
            return

        if preset_mode == PRESET_BOOST:
            self._device.boost_mode = True

        elif preset_mode == PRESET_ECO:
            # Clear boost first so states don't stack
            if self._device.supports_boost_mode and self._device.boost_mode:
                self._device.boost_mode = False
            self._device.low = True

    @override
    def turn_on(self) -> None:
        """Turn the climate device on."""
        if self.hvac_mode == HVACMode.OFF:
            self.set_hvac_mode(HVACMode.AUTO)

    @override
    def turn_off(self) -> None:
        """Turn the climate device off."""
        if self.hvac_mode != HVACMode.OFF:
            self.set_hvac_mode(HVACMode.OFF)


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
    def set_temperature(self, **kwargs: Any) -> None:
        """Set a new setpoint temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._device.setpoint_temperature = float(round(temperature * 2.0) / 2.0)

    @override
    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the operation mode."""
        if hvac_mode not in self.hvac_modes:
            return
        self._device.operation_mode = (
            SHCHeatingCircuit.HeatingCircuitService.OperationMode.AUTOMATIC
            if hvac_mode == HVACMode.AUTO
            else SHCHeatingCircuit.HeatingCircuitService.OperationMode.MANUAL
        )
