"""Support for NuHeat thermostats."""
import logging
from typing import Any

from nuheat.config import SCHEDULE_HOLD, SCHEDULE_RUN, SCHEDULE_TEMPORARY_HOLD
from nuheat.util import (
    celsius_to_nuheat,
    fahrenheit_to_nuheat,
    nuheat_to_celsius,
    nuheat_to_fahrenheit,
)

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import event as event_helper
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NUHEAT_API_STATE_SHIFT_DELAY

_LOGGER = logging.getLogger(__name__)


# The device does not have an off function.
# To turn it off set to min_temp and PRESET_PERMANENT_HOLD
OPERATION_LIST = [HVACMode.AUTO, HVACMode.HEAT]

PRESET_RUN = "Run Schedule"
PRESET_TEMPORARY_HOLD = "Temporary Hold"
PRESET_PERMANENT_HOLD = "Permanent Hold"

PRESET_MODES = [PRESET_RUN, PRESET_TEMPORARY_HOLD, PRESET_PERMANENT_HOLD]

PRESET_MODE_TO_SCHEDULE_MODE_MAP = {
    PRESET_RUN: SCHEDULE_RUN,
    PRESET_TEMPORARY_HOLD: SCHEDULE_TEMPORARY_HOLD,
    PRESET_PERMANENT_HOLD: SCHEDULE_HOLD,
}

SCHEDULE_MODE_TO_PRESET_MODE_MAP = {
    value: key for key, value in PRESET_MODE_TO_SCHEDULE_MODE_MAP.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the NuHeat thermostat(s)."""
    thermostat, coordinator = hass.data[DOMAIN][config_entry.entry_id]

    temperature_unit = hass.config.units.temperature_unit
    entity = NuHeatThermostat(coordinator, thermostat, temperature_unit)

    # No longer need a service as set_hvac_mode to auto does this
    # since climate 1.0 has been implemented

    async_add_entities([entity], True)


class NuHeatThermostat(CoordinatorEntity, ClimateEntity):
    """Representation of a NuHeat Thermostat."""

    _attr_hvac_modes = OPERATION_LIST
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_has_entity_name = True
    _attr_name = None
    _attr_preset_modes = PRESET_MODES
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator, thermostat, temperature_unit):
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self._thermostat = thermostat
        self._temperature_unit = temperature_unit
        self._schedule_mode = None
        self._target_temperature = None
        self._attr_unique_id = thermostat.serial_number

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        if self._temperature_unit == "C":
            return UnitOfTemperature.CELSIUS

        return UnitOfTemperature.FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._temperature_unit == "C":
            return self._thermostat.celsius

        return self._thermostat.fahrenheit

    @property
    def available(self) -> bool:
        """Return the unique id."""
        return self.coordinator.last_update_success and self._thermostat.online

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the system mode."""
        if hvac_mode == HVACMode.AUTO:
            self._set_schedule_mode(SCHEDULE_RUN)
        elif hvac_mode == HVACMode.HEAT:
            self._set_schedule_mode(SCHEDULE_HOLD)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current setting heat or auto."""
        if self._schedule_mode in (SCHEDULE_TEMPORARY_HOLD, SCHEDULE_HOLD):
            return HVACMode.HEAT
        return HVACMode.AUTO

    @property
    def hvac_action(self) -> HVACAction:
        """Return current operation heat or idle."""
        return HVACAction.HEATING if self._thermostat.heating else HVACAction.IDLE

    @property
    def min_temp(self):
        """Return the minimum supported temperature for the thermostat."""
        if self._temperature_unit == "C":
            return self._thermostat.min_celsius

        return self._thermostat.min_fahrenheit

    @property
    def max_temp(self):
        """Return the maximum supported temperature for the thermostat."""
        if self._temperature_unit == "C":
            return self._thermostat.max_celsius

        return self._thermostat.max_fahrenheit

    @property
    def target_temperature(self):
        """Return the currently programmed temperature."""
        if self._temperature_unit == "C":
            return nuheat_to_celsius(self._target_temperature)

        return nuheat_to_fahrenheit(self._target_temperature)

    @property
    def preset_mode(self):
        """Return current preset mode."""
        return SCHEDULE_MODE_TO_PRESET_MODE_MAP.get(self._schedule_mode, PRESET_RUN)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Update the hold mode of the thermostat."""
        self._set_schedule_mode(
            PRESET_MODE_TO_SCHEDULE_MODE_MAP.get(preset_mode, SCHEDULE_RUN)
        )

    def _set_schedule_mode(self, schedule_mode):
        """Set a schedule mode."""
        self._schedule_mode = schedule_mode
        # Changing the property here does the actual set
        self._thermostat.schedule_mode = schedule_mode
        self._schedule_update()

    def set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        self._set_temperature_and_mode(
            kwargs.get(ATTR_TEMPERATURE), hvac_mode=kwargs.get(ATTR_HVAC_MODE)
        )

    def _set_temperature_and_mode(self, temperature, hvac_mode=None, preset_mode=None):
        """Set temperature and hvac mode at the same time."""
        if self._temperature_unit == "C":
            target_temperature = celsius_to_nuheat(temperature)
        else:
            target_temperature = fahrenheit_to_nuheat(temperature)

        # If they set a temperature without changing the mode
        # to heat, we behave like the device does locally
        # and set a temp hold.
        target_schedule_mode = SCHEDULE_TEMPORARY_HOLD
        if preset_mode:
            target_schedule_mode = PRESET_MODE_TO_SCHEDULE_MODE_MAP.get(
                preset_mode, SCHEDULE_RUN
            )
        elif self._schedule_mode == SCHEDULE_HOLD or (
            hvac_mode and hvac_mode == HVACMode.HEAT
        ):
            target_schedule_mode = SCHEDULE_HOLD

        _LOGGER.debug(
            "Setting NuHeat thermostat temperature to %s %s and schedule mode: %s",
            temperature,
            self.temperature_unit,
            target_schedule_mode,
        )

        self._thermostat.set_target_temperature(
            target_temperature, target_schedule_mode
        )
        self._schedule_mode = target_schedule_mode
        self._target_temperature = target_temperature
        self._schedule_update()

    def _schedule_update(self):
        if not self.hass:
            return

        # Update the new state
        self.schedule_update_ha_state(False)

        # nuheat has a delay switching state
        # so we schedule a poll of the api
        # in the future to make sure the change actually
        # took effect
        event_helper.call_later(
            self.hass, NUHEAT_API_STATE_SHIFT_DELAY, self._forced_refresh
        )

    async def _forced_refresh(self, *_) -> None:
        """Force a refresh."""
        await self.coordinator.async_refresh()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._update_internal_state()

    @callback
    def _update_internal_state(self):
        """Update our internal state from the last api response."""
        self._schedule_mode = self._thermostat.schedule_mode
        self._target_temperature = self._thermostat.target_temperature

    @callback
    def _handle_coordinator_update(self):
        """Get the latest state from the thermostat."""
        self._update_internal_state()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._thermostat.serial_number)},
            serial_number=self._thermostat.serial_number,
            name=self._thermostat.room,
            model="nVent Signature",
            manufacturer=MANUFACTURER,
            suggested_area=self._thermostat.room,
        )
