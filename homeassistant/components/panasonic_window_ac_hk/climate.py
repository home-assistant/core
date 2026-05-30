"""Climate platform for the Panasonic Window A/C (Hong Kong/Macau)."""

from typing import Any

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_SWING_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import PanasonicWindowAcHKConfigEntry
from .const import FAN_MODES, SWING_MODES
from .encoder import MAX_TEMP, MIN_TEMP
from .entity import PanasonicWindowAcHKEntity

PARALLEL_UPDATES = 1

_MODE_TO_HVAC = {
    "auto": HVACMode.AUTO,
    "cool": HVACMode.COOL,
    "dry": HVACMode.DRY,
    "heat": HVACMode.HEAT,
}
_HVAC_TO_MODE = {hvac: mode for mode, hvac in _MODE_TO_HVAC.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PanasonicWindowAcHKConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the climate entity for one air conditioner."""
    async_add_entities([PanasonicWindowAcHKClimate(entry)])


class PanasonicWindowAcHKClimate(
    PanasonicWindowAcHKEntity, ClimateEntity, RestoreEntity
):
    """Optimistic climate control for one air conditioner (infrared is one-way)."""

    _attr_name = None
    _attr_icon = "mdi:air-conditioner"
    _attr_assumed_state = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.HEAT,
    ]
    _attr_fan_modes = FAN_MODES
    _attr_swing_modes = SWING_MODES
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, entry: PanasonicWindowAcHKConfigEntry) -> None:
        """Initialize the climate entity."""
        super().__init__(entry, "climate")

    async def async_added_to_hass(self) -> None:
        """Restore the last assumed state across restarts (infrared is one-way)."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is None:
            return
        data = self._runtime_data
        if last_state.state == HVACMode.OFF:
            data.power = False
        elif last_state.state in _HVAC_TO_MODE:
            data.power = True
            data.mode = _HVAC_TO_MODE[HVACMode(last_state.state)]
        if (temp := last_state.attributes.get(ATTR_TEMPERATURE)) is not None:
            data.temp = float(temp)
        if (fan := last_state.attributes.get(ATTR_FAN_MODE)) in FAN_MODES:
            data.fan = fan
        if (swing := last_state.attributes.get(ATTR_SWING_MODE)) in SWING_MODES:
            data.swing = swing

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode (OFF when powered off)."""
        if not self._runtime_data.power:
            return HVACMode.OFF
        return _MODE_TO_HVAC[self._runtime_data.mode]

    @property
    def target_temperature(self) -> float:
        """Return the current target temperature."""
        return self._runtime_data.temp

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode."""
        return self._runtime_data.fan

    @property
    def swing_mode(self) -> str:
        """Return the current swing mode."""
        return self._runtime_data.swing

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode (or power off)."""
        if hvac_mode is HVACMode.OFF:
            self._runtime_data.power = False
        else:
            self._runtime_data.power = True
            self._runtime_data.mode = _HVAC_TO_MODE[hvac_mode]
        await self._async_send_full()
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature (0.5 degree steps)."""
        temperature = kwargs[ATTR_TEMPERATURE]
        self._runtime_data.temp = temperature
        if self._runtime_data.power:
            await self._async_send_full()
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan speed."""
        self._runtime_data.fan = fan_mode
        if self._runtime_data.power:
            await self._async_send_full()
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing position."""
        self._runtime_data.swing = swing_mode
        if self._runtime_data.power:
            await self._async_send_full()
        self.async_write_ha_state()
