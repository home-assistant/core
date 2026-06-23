"""Platform for climate integration."""

from typing import Any

from boschshcpy import SHCClimateControl, SHCHeatingCircuit
from boschshcpy.exceptions import JSONRPCError, SHCException

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .entity import SHCEntity, device_excluded

PARALLEL_UPDATES = 1

# Preset mode strings (regulation axis — independent of hvac_mode direction axis).
# Design from PR #329 (jumlu): Bosch separates direction (HEATING/COOLING/OFF)
# from regulation (AUTOMATIC schedule vs MANUAL setpoint + eco/boost overrides).
# We map regulation onto HA preset_mode so AUTO is a preset, not an hvac_mode.
PRESET_AUTO = "auto"
PRESET_MANUAL = "manual"
PRESET_BOOST = "boost"
PRESET_ECO = "eco"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC climate platform."""
    entities: list[ClimateControl | HeatingCircuit] = []
    session = config_entry.runtime_data.session

    for climate in session.device_helper.climate_controls:
        if device_excluded(climate, config_entry.options):
            continue
        room_id = climate.room_id
        entities.append(
            ClimateControl(
                device=climate,
                entry_id=config_entry.entry_id,
                name=session.room(room_id).name,
            )
        )

    for heating_circuit in session.device_helper.heating_circuits:
        if device_excluded(heating_circuit, config_entry.options):
            continue
        entities.append(
            HeatingCircuit(
                device=heating_circuit,
                entry_id=config_entry.entry_id,
                name=heating_circuit.name,
            )
        )

    # DEFERRED (#253, #242): TRV I (model "TRV") and TRV_GEN2 (SHCThermostat)
    # are not added as climate entities here.  Both devices lack a direct
    # setpoint-write API; temperature is controlled at room level via the
    # RoomClimateControl virtual device above.  Adding per-TRV climate entities
    # requires an architectural decision (one entity per TRV vs. room-level only)
    # and possibly a lib change to expose the room association.  Tracked in #253
    # and #242 — do not implement without that design decision.

    if entities:
        async_add_entities(entities)


class ClimateControl(SHCEntity, ClimateEntity):
    """Representation of a SHC room climate control.

    Design from PR #329 (jumlu): two orthogonal Bosch axes mapped onto HA:
      Direction axis  → hvac_mode:   summer_mode=True→OFF, cooling_mode=True→COOL, else→HEAT
      Regulation axis → preset_mode: AUTOMATIC→"auto", MANUAL→"manual", + boost/eco overrides
    """

    _attr_target_temperature_step = 0.5
    _enable_turn_on_off_backwards_compatibility = False
    _attr_translation_key = "room_climate_control"

    def __init__(
        self,
        device: SHCClimateControl,
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize the SHC device."""
        super().__init__(device=device, entry_id=entry_id)
        # Device name = room name (e.g. "Arbeitszimmer").
        # Entity name comes from translation_key "room_climate_control" in strings.json
        # (e.g. "Raumklima" / "Room climate control"), so the friendly name is
        # "<room> Raumklima" — no doubling. _attr_name = None lets HA resolve
        # the name from the translation_key.
        self._room_label = name
        self._attr_name = None
        self._attr_unique_id = f"{device.root_device_id}_{device.id}"

    @property
    def device_name(self):
        """Name of the device."""
        return self._room_label

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.temperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature allowed."""
        return 30.0

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature allowed."""
        return 5.0

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature setpoint."""
        return self._device.setpoint_temperature

    @property
    def target_temperature_step(self) -> float | None:
        """Return the temperature step."""
        return 0.5

    @property
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
    def hvac_modes(self) -> list[HVACMode]:
        """Return available hvac modes."""
        modes = [HVACMode.HEAT]
        if self._device.supports_cooling:
            modes.append(HVACMode.COOL)
        modes.append(HVACMode.OFF)
        return modes

    @property
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
        # getattr guard: has_demand needs boschshcpy >= 0.2.120; tolerate older libs
        return (
            HVACAction.HEATING
            if getattr(self._device, "has_demand", False)
            else HVACAction.IDLE
        )

    @property
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

        if getattr(self._device, "low", False):
            return PRESET_ECO

        if (
            self._device.operation_mode
            == SHCClimateControl.RoomClimateControlService.OperationMode.AUTOMATIC
        ):
            return PRESET_AUTO

        return PRESET_MANUAL

    @property
    def preset_modes(self) -> list[str] | None:
        """Return available preset modes."""
        presets = [PRESET_AUTO, PRESET_MANUAL]
        if self._device.supports_boost_mode:
            presets.append(PRESET_BOOST)
        # `low` is a Python property that always exists, so the old hasattr check
        # always added ECO. Gate on the lib capability (the `low` field actually
        # being present in the device state) instead. Falls back to hasattr for
        # older libs that predate supports_low.
        if getattr(self._device, "supports_low", None) is not None:
            if self._device.supports_low:
                presets.append(PRESET_ECO)
        elif hasattr(self._device, "low"):
            presets.append(PRESET_ECO)
        return presets

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        # P2-B: call async_set_hvac_mode BEFORE the ECO/OFF guard so that a
        # combined temperature+mode call from ECO state can exit ECO first
        # (async_set_hvac_mode clears low=False when in ECO; the device cache
        # reflects the change immediately after the await).
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(
                hvac_mode
            )  # set_temperature args may provide HVAC mode as well

        # P2-B: do NOT re-check preset_mode == PRESET_ECO here.
        # async_set_hvac_mode above already called device.low = False to exit ECO,
        # but put_state_element (HTTP PUT) does NOT update the in-memory _raw_state,
        # so preset_mode still reads ECO from stale cache → the guard would silently
        # skip the setpoint write every time.  Only skip when truly OFF. #196
        if self.hvac_mode == HVACMode.OFF:
            LOGGER.debug(
                "Skipping setting temperature as device %s is off",
                self.device_name,
            )
            return

        if self.preset_mode == PRESET_BOOST:
            LOGGER.warning(
                "Cannot set temperature on device %s while in BOOST mode "
                "(SHC rejects setpoint writes in this state)",
                self.device_name,
            )
            return

        if self.min_temp <= temperature <= self.max_temp:
            try:
                # SHC rejects a setpoint write while operationMode=AUTOMATIC
                # (HTTP 400 WRONG_THERMOSTAT_GROUP_MODE).  For a bare
                # set_temperature (no hvac_mode given, e.g. from a script) drop
                # to MANUAL first — matching the Bosch app.  Gated on no explicit
                # hvac_mode so a combined set_temperature(hvac_mode=auto) is not
                # overridden; kept inside the try + range branch so a failed mode
                # write is caught and an out-of-range value can't cancel the
                # schedule. #73 #180
                if (
                    kwargs.get(ATTR_HVAC_MODE) is None
                    and self._device.operation_mode
                    == SHCClimateControl.RoomClimateControlService.OperationMode.AUTOMATIC
                ):
                    await self._device.async_set_operation_mode(
                        SHCClimateControl.RoomClimateControlService.OperationMode.MANUAL
                    )
                await self._device.async_set_setpoint_temperature(
                    float(round(temperature * 2.0) / 2.0)
                )
            except (JSONRPCError, SHCException) as err:
                LOGGER.warning(
                    "Failed to set temperature on device %s: %s",
                    self.device_name,
                    err,
                )
                raise HomeAssistantError(
                    f"Failed to set temperature on {self.device_name}: {err}"
                ) from err

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode (direction axis).

        #196: ECO (low mode) and HVAC mode are independent state fields on the
        SHC.  The old guard (return-if-ECO) silently blocked turn_off from ECO,
        leaving the device stuck.  We now exit ECO first so the HVAC write always
        proceeds.
        """
        if hvac_mode not in self.hvac_modes:
            return

        try:
            # Exit ECO (low) before applying any HVAC mode change so that
            # turn_off / mode changes are never silently no-oped. #196
            if self.preset_mode == PRESET_ECO:
                await self._device.async_set_low(False)

            if hvac_mode == HVACMode.HEAT:
                await self._device.async_set_summer_mode(False)
                if self._device.supports_cooling:
                    await self._device.async_set_cooling_mode(False)
            elif hvac_mode == HVACMode.COOL:
                await self._device.async_set_summer_mode(False)
                await self._device.async_set_cooling_mode(True)
            elif hvac_mode == HVACMode.OFF:
                if self._device.supports_cooling:
                    await self._device.async_set_cooling_mode(False)
                await self._device.async_set_summer_mode(True)
        except (JSONRPCError, SHCException) as err:
            LOGGER.warning(
                "Failed to set HVAC mode on device %s: %s",
                self.device_name,
                err,
            )
            raise HomeAssistantError(
                f"Failed to set HVAC mode on {self.device_name}: {err}"
            ) from err

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode (regulation axis).

        "auto"   → operationMode=AUTOMATIC (follow schedule)
        "manual" → operationMode=MANUAL + clear boost + clear eco
        "boost"  → boost_mode=True
        "eco"    → low=True  (only if device exposes `low`)
        """
        if self.preset_modes is None or preset_mode not in self.preset_modes:
            return

        try:
            if preset_mode == PRESET_BOOST:
                await self._device.async_set_boost_mode(True)

            elif preset_mode == PRESET_ECO:
                if hasattr(self._device, "low"):
                    # Clear boost first so states don't stack
                    if self._device.supports_boost_mode and self._device.boost_mode:
                        await self._device.async_set_boost_mode(False)
                    await self._device.async_set_low(True)

            elif preset_mode == PRESET_AUTO:
                # Clear overrides then set schedule mode
                if self._device.supports_boost_mode and self._device.boost_mode:
                    await self._device.async_set_boost_mode(False)
                if hasattr(self._device, "low") and self._device.low:
                    await self._device.async_set_low(False)
                await self._device.async_set_operation_mode(
                    SHCClimateControl.RoomClimateControlService.OperationMode.AUTOMATIC
                )

            elif preset_mode == PRESET_MANUAL:
                # Clear overrides then set manual mode
                if self._device.supports_boost_mode and self._device.boost_mode:
                    await self._device.async_set_boost_mode(False)
                if hasattr(self._device, "low") and self._device.low:
                    await self._device.async_set_low(False)
                await self._device.async_set_operation_mode(
                    SHCClimateControl.RoomClimateControlService.OperationMode.MANUAL
                )
        except (JSONRPCError, SHCException) as err:
            LOGGER.warning(
                "Failed to set preset mode on device %s: %s",
                self.device_name,
                err,
            )
            raise HomeAssistantError(
                f"Failed to set preset mode on {self.device_name}: {err}"
            ) from err

    async def async_turn_on(self) -> None:
        """Turn the climate device on."""
        if self.hvac_mode == HVACMode.OFF:
            await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the climate device off."""
        if self.hvac_mode != HVACMode.OFF:
            await self.async_set_hvac_mode(HVACMode.OFF)


class HeatingCircuit(SHCEntity, ClimateEntity):
    """Representation of a SHC heating circuit.

    The HeatingCircuit service exposes a setpoint temperature and an operation
    mode (AUTOMATIC/MANUAL); there is no measured room temperature and the on
    state is read-only, so this maps to a HEAT/AUTO climate entity with a
    heating/idle action and no OFF mode.
    """

    _attr_target_temperature_step = 0.5
    _enable_turn_on_off_backwards_compatibility = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_max_temp = 30.0
    _attr_min_temp = 5.0
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(
        self,
        device: SHCHeatingCircuit,
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize the SHC heating circuit."""
        super().__init__(device=device, entry_id=entry_id)
        self._attr_name = name
        self._attr_unique_id = f"{device.root_device_id}_{device.id}"

    @property
    def current_temperature(self) -> float | None:
        """Heating circuits expose no measured temperature."""
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the setpoint temperature."""
        return self._device.setpoint_temperature

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the hvac mode derived from the operation mode."""
        if (
            self._device.operation_mode
            == SHCHeatingCircuit.HeatingCircuitService.OperationMode.AUTOMATIC
        ):
            return HVACMode.AUTO
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return whether the circuit is currently heating."""
        return HVACAction.HEATING if self._device.on else HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new setpoint temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        if self.min_temp <= temperature <= self.max_temp:
            try:
                await self._device.async_set_setpoint_temperature(
                    float(round(temperature * 2.0) / 2.0)
                )
            except (JSONRPCError, SHCException) as err:
                LOGGER.warning(
                    "Failed to set temperature on HeatingCircuit %s: %s",
                    self._attr_unique_id,
                    err,
                )
                raise HomeAssistantError(
                    f"Failed to set temperature on HeatingCircuit {self._attr_unique_id}: {err}"
                ) from err

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the operation mode."""
        if hvac_mode not in self.hvac_modes:
            return
        mode = (
            SHCHeatingCircuit.HeatingCircuitService.OperationMode.AUTOMATIC
            if hvac_mode == HVACMode.AUTO
            else SHCHeatingCircuit.HeatingCircuitService.OperationMode.MANUAL
        )
        try:
            await self._device.async_set_operation_mode(mode)
        except (JSONRPCError, SHCException) as err:
            LOGGER.warning(
                "Failed to set HVAC mode on HeatingCircuit %s: %s",
                self._attr_unique_id,
                err,
            )
            raise HomeAssistantError(
                f"Failed to set HVAC mode on HeatingCircuit {self._attr_unique_id}: {err}"
            ) from err
