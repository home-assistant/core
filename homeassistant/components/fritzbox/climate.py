"""Support for AVM FRITZ!SmartHome thermostat devices."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_STATE_BATTERY_LOW,
    ATTR_STATE_HOLIDAY_MODE,
    ATTR_STATE_SUMMER_MODE,
    ATTR_STATE_WINDOW_OPEN,
    DOMAIN,
    LOGGER,
)
from .coordinator import FritzboxConfigEntry, FritzboxDataUpdateCoordinator
from .entity import FritzBoxDeviceEntity
from .model import ClimateExtraAttributes
from .sensor import value_scheduled_preset

HVAC_MODES = [HVACMode.HEAT, HVACMode.OFF]
PRESET_HOLIDAY = "holiday"
PRESET_SUMMER = "summer"
PRESET_MODES = [PRESET_ECO, PRESET_COMFORT]
SUPPORTED_FEATURES = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_OFF
    | ClimateEntityFeature.TURN_ON
)

MIN_TEMPERATURE = 8
MAX_TEMPERATURE = 28

# special temperatures for on/off in Fritz!Box API (modified by pyfritzhome)
ON_API_TEMPERATURE = 127.0
OFF_API_TEMPERATURE = 126.5
ON_REPORT_SET_TEMPERATURE = 30.0
OFF_REPORT_SET_TEMPERATURE = 0.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzboxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the FRITZ!SmartHome thermostat from ConfigEntry."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities(devices: set[str] | None = None) -> None:
        """Add devices."""
        if devices is None:
            devices = coordinator.new_devices
        if not devices:
            return
        async_add_entities(
            FritzboxThermostat(coordinator, ain)
            for ain in devices
            if coordinator.data.devices[ain].has_thermostat
        )

    entry.async_on_unload(coordinator.async_add_listener(_add_entities))

    _add_entities(set(coordinator.data.devices))


class FritzboxThermostat(FritzBoxDeviceEntity, ClimateEntity):
    """The thermostat class for FRITZ!SmartHome thermostats."""

    _attr_precision = PRECISION_HALVES
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "thermostat"

    def __init__(
        self,
        coordinator: FritzboxDataUpdateCoordinator,
        ain: str,
    ) -> None:
        """Initialize the thermostat."""
        self._attr_supported_features = SUPPORTED_FEATURES
        self._attr_hvac_modes = HVAC_MODES
        self._attr_preset_modes = PRESET_MODES
        super().__init__(coordinator, ain)

    @callback
    def async_write_ha_state(self) -> None:
        """Write the state to the HASS state machine."""
        if self.data.holiday_active:
            self._attr_supported_features = ClimateEntityFeature.PRESET_MODE
            self._attr_hvac_modes = [HVACMode.HEAT]
            self._attr_preset_modes = [PRESET_HOLIDAY]
        elif self.data.summer_active:
            self._attr_supported_features = ClimateEntityFeature.PRESET_MODE
            self._attr_hvac_modes = [HVACMode.OFF]
            self._attr_preset_modes = [PRESET_SUMMER]
        else:
            self._attr_supported_features = SUPPORTED_FEATURES
            self._attr_hvac_modes = HVAC_MODES
            self._attr_preset_modes = PRESET_MODES
        return super().async_write_ha_state()

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        if self.data.has_temperature_sensor and self.data.temperature is not None:
            return self.data.temperature  # type: ignore [no-any-return]
        return self.data.actual_temperature  # type: ignore [no-any-return]

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        if self.data.target_temperature == ON_API_TEMPERATURE:
            return ON_REPORT_SET_TEMPERATURE
        if self.data.target_temperature == OFF_API_TEMPERATURE:
            return OFF_REPORT_SET_TEMPERATURE
        return self.data.target_temperature  # type: ignore [no-any-return]

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode == HVACMode.OFF:
            await self.async_set_hvac_mode(hvac_mode)
        elif target_temp is not None:
            await self.hass.async_add_executor_job(
                self.data.set_target_temperature, target_temp
            )
        else:
            return
        await self.coordinator.async_refresh()

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current operation mode."""
        if self.data.holiday_active:
            return HVACMode.HEAT
        if self.data.summer_active:
            return HVACMode.OFF
        if self.data.target_temperature in (
            OFF_REPORT_SET_TEMPERATURE,
            OFF_API_TEMPERATURE,
        ):
            return HVACMode.OFF

        return HVACMode.HEAT

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        if self.data.holiday_active or self.data.summer_active:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="change_hvac_while_active_mode",
            )
        if self.hvac_mode == hvac_mode:
            LOGGER.debug(
                "%s is already in requested hvac mode %s", self.name, hvac_mode
            )
            return
        if hvac_mode == HVACMode.OFF:
            await self.async_set_temperature(temperature=OFF_REPORT_SET_TEMPERATURE)
        else:
            if value_scheduled_preset(self.data) == PRESET_ECO:
                target_temp = self.data.eco_temperature
            else:
                target_temp = self.data.comfort_temperature
            await self.async_set_temperature(temperature=target_temp)

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        if self.data.holiday_active:
            return PRESET_HOLIDAY
        if self.data.summer_active:
            return PRESET_SUMMER
        if self.data.target_temperature == self.data.comfort_temperature:
            return PRESET_COMFORT
        if self.data.target_temperature == self.data.eco_temperature:
            return PRESET_ECO
        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if self.data.holiday_active or self.data.summer_active:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="change_preset_while_active_mode",
            )
        if preset_mode == PRESET_COMFORT:
            await self.async_set_temperature(temperature=self.data.comfort_temperature)
        elif preset_mode == PRESET_ECO:
            await self.async_set_temperature(temperature=self.data.eco_temperature)

    @property
    def min_temp(self) -> int:
        """Return the minimum temperature."""
        return MIN_TEMPERATURE

    @property
    def max_temp(self) -> int:
        """Return the maximum temperature."""
        return MAX_TEMPERATURE

    @property
    def extra_state_attributes(self) -> ClimateExtraAttributes:
        """Return the device specific state attributes."""
        attrs: ClimateExtraAttributes = {
            ATTR_STATE_BATTERY_LOW: self.data.battery_low,
        }

        # the following attributes are available since fritzos 7
        if self.data.battery_level is not None:
            attrs[ATTR_BATTERY_LEVEL] = self.data.battery_level
        if self.data.holiday_active is not None:
            attrs[ATTR_STATE_HOLIDAY_MODE] = self.data.holiday_active
        if self.data.summer_active is not None:
            attrs[ATTR_STATE_SUMMER_MODE] = self.data.summer_active
        if self.data.window_open is not None:
            attrs[ATTR_STATE_WINDOW_OPEN] = self.data.window_open

        return attrs
