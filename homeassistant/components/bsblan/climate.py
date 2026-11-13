"""BSBLAN platform to control a compatible Climate Device."""

from typing import Any, Final, override

from bsblan import get_hvac_action_category

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BSBLanConfigEntry, BSBLanData
from .const import Setpoint
from .entity import BSBLanCircuitEntity
from .helpers import circuit_temperature_bounds, first_temperature

PARALLEL_UPDATES = 1

HVAC_MODES = [
    HVACMode.AUTO,
    HVACMode.HEAT,
    HVACMode.OFF,
]

PRESET_MODES = [
    PRESET_COMFORT,
    PRESET_ECO,
]

BSBLAN_AUTOMATIC_MODE: Final = 1

# Mapping from Home Assistant HVACMode to BSB-LAN integer values
# BSB-LAN uses: 0=off, 1=auto, 2=eco/reduced, 3=heat/comfort
HA_TO_BSBLAN_HVAC_MODE: Final[dict[HVACMode, int]] = {
    HVACMode.OFF: 0,
    HVACMode.AUTO: BSBLAN_AUTOMATIC_MODE,
    HVACMode.HEAT: 3,
}

# Mapping from BSB-LAN integer values to Home Assistant HVACMode
BSBLAN_TO_HA_HVAC_MODE: Final[dict[int, HVACMode]] = {
    0: HVACMode.OFF,
    BSBLAN_AUTOMATIC_MODE: HVACMode.AUTO,
    2: HVACMode.HEAT,  # permanent reduced, exposed as HEAT with the eco preset
    3: HVACMode.HEAT,
}

# Outside automatic mode, a preset switches the permanent operating mode
PRESET_TO_BSBLAN_HVAC_MODE: Final[dict[str, int]] = {
    PRESET_COMFORT: 3,
    PRESET_ECO: 2,
}
BSBLAN_HVAC_MODE_TO_PRESET: Final[dict[int, str]] = {
    v: k for k, v in PRESET_TO_BSBLAN_HVAC_MODE.items()
}

# In automatic mode, a preset overrides the time program until its next
# switch point (0=no override, 1=reduced, 2=comfort)
PRESET_TO_BSBLAN_TEMPORARY_MODE: Final[dict[str, int]] = {
    PRESET_COMFORT: 2,
    PRESET_ECO: 1,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BSBLanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BSBLAN device based on a config entry."""
    data = entry.runtime_data
    async_add_entities(
        BSBLANClimate(data, circuit) for circuit in data.available_circuits
    )


class BSBLANClimate(BSBLanCircuitEntity, ClimateEntity):
    """Defines a BSBLAN climate device."""

    _attr_name = None
    # Determine preset modes
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    _attr_preset_modes = PRESET_MODES
    _attr_hvac_modes = HVAC_MODES

    def __init__(
        self,
        data: BSBLanData,
        circuit: int,
    ) -> None:
        """Initialize BSBLAN climate device."""
        super().__init__(data.fast_coordinator, data.slow_coordinator, data, circuit)
        mac = format_mac(data.device.MAC)

        # Backward compatible unique ID: circuit 1 keeps old format
        if circuit == 1:
            # Legacy format, kept as migrating existing unique IDs is not worth the risk
            self._attr_unique_id = f"{mac}-climate"  # pylint: disable=home-assistant-entity-unique-id-redundant-platform
        else:
            # Legacy format, kept as migrating existing unique IDs is not worth the risk
            self._attr_unique_id = f"{mac}-climate-{circuit}"  # pylint: disable=home-assistant-entity-unique-id-redundant-platform

        min_temp, max_temp = circuit_temperature_bounds(data.static.get(circuit))
        if min_temp is not None:
            self._attr_min_temp = min_temp
        if max_temp is not None:
            self._attr_max_temp = max_temp
        self._attr_native_temperature_unit = (
            data.fast_coordinator.client.get_temperature_unit
        )
        # PPS accepts neither the temporary override nor permanent reduced mode
        if data.device.is_pps_bus:
            self._attr_supported_features &= ~ClimateEntityFeature.PRESET_MODE

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        if (current_temp := self._circuit_state.current_temperature) is None:
            return None
        return current_temp.value

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the setpoint the controller currently applies."""
        state = self._circuit_state
        return first_temperature(state.current_setpoint, state.target_temperature)

    @property
    def _current_setpoint(self) -> float | None:
        """Return the setpoint the controller applies right now."""
        return first_temperature(self._circuit_state.current_setpoint)

    @property
    def _hvac_mode_value(self) -> int | None:
        """Return the raw hvac_mode value from the coordinator."""
        if (hvac_mode := self._circuit_state.hvac_mode) is None:
            return None
        return hvac_mode.value

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        if (hvac_mode_value := self._hvac_mode_value) is None:
            return None
        return BSBLAN_TO_HA_HVAC_MODE.get(hvac_mode_value)

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac action."""
        if (action := self._circuit_state.hvac_action) is None or action.value is None:
            return None
        hvac_action = HVACAction(get_hvac_action_category(action.value).name.lower())
        # In protection mode the circuit is off unless frost protection heats
        if hvac_action is HVACAction.IDLE and self.hvac_mode is HVACMode.OFF:
            return HVACAction.OFF
        return hvac_action

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the comfort level currently in effect."""
        if (hvac_mode_value := self._hvac_mode_value) is None:
            return None
        if hvac_mode_value != BSBLAN_AUTOMATIC_MODE:
            return BSBLAN_HVAC_MODE_TO_PRESET.get(hvac_mode_value)
        if (current := self._current_setpoint) is None:
            return None
        if current == self._comfort_setpoint:
            return PRESET_COMFORT
        if current == self._reduced_setpoint:
            return PRESET_ECO
        return None

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        # Heat covers permanent comfort and reduced, rewriting it would drop eco
        if hvac_mode == self.hvac_mode == HVACMode.HEAT:
            return
        if (
            hvac_mode == self.hvac_mode == HVACMode.AUTO
            and self.supported_features & ClimateEntityFeature.PRESET_MODE
        ):
            # Ends the temporary override a preset starts in auto
            await self._async_thermostat(temporary_mode=0)
            return
        await self._async_thermostat(hvac_mode=HA_TO_BSBLAN_HVAC_MODE[hvac_mode])

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if self._hvac_mode_value == BSBLAN_AUTOMATIC_MODE:
            await self._async_thermostat(
                temporary_mode=PRESET_TO_BSBLAN_TEMPORARY_MODE[preset_mode]
            )
        else:
            await self._async_thermostat(
                hvac_mode=PRESET_TO_BSBLAN_HVAC_MODE[preset_mode]
            )

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the setpoint of the comfort level currently in effect."""
        temperature = kwargs[ATTR_TEMPERATURE]
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) == self.hvac_mode == HVACMode.HEAT:
            hvac_mode = None
        if (hvac_mode or self.hvac_mode) in (HVACMode.AUTO, HVACMode.OFF):
            # BSB-LAN can't override the setpoint the controller applies in these modes
            if hvac_mode is not None:
                await self.async_set_hvac_mode(hvac_mode)
            return
        # Switching to heat writes the comfort setpoint
        setpoint = (
            Setpoint.REDUCED
            if hvac_mode is None and self.preset_mode == PRESET_ECO
            else Setpoint.NORMAL
        )
        self._validate_setpoint(temperature, setpoint)
        if hvac_mode is not None:
            await self.async_set_hvac_mode(hvac_mode)
        await self._async_set_setpoint(temperature, setpoint)
