"""Demo platform that offers a fake climate device."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

SUPPORT_FLAGS = ClimateEntityFeature(0)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the demo climate platform."""
    async_add_entities(
        [
            DemoClimate(
                unique_id="climate_1",
                device_name="HeatPump",
                target_temperature=68,
                unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
                preset=None,
                current_temperature=77,
                fan_mode=None,
                target_humidity=None,
                current_humidity=None,
                swing_mode=None,
                hvac_mode=HVACMode.HEAT,
                hvac_action=HVACAction.HEATING,
                target_temp_high=None,
                target_temp_low=None,
                hvac_modes=[HVACMode.HEAT, HVACMode.OFF],
            ),
            DemoClimate(
                unique_id="climate_2",
                device_name="Hvac",
                target_temperature=21,
                unit_of_measurement=UnitOfTemperature.CELSIUS,
                preset=None,
                current_temperature=22,
                fan_mode="on_high",
                target_humidity=67.4,
                current_humidity=54.2,
                swing_mode="off",
                hvac_mode=HVACMode.COOL,
                hvac_action=HVACAction.COOLING,
                target_temp_high=None,
                target_temp_low=None,
                hvac_modes=[cls for cls in HVACMode if cls != HVACMode.HEAT_COOL],
            ),
            DemoClimate(
                unique_id="climate_3",
                device_name="Ecobee",
                target_temperature=None,
                unit_of_measurement=UnitOfTemperature.CELSIUS,
                preset="home",
                preset_modes=["home", "eco", "away"],
                current_temperature=23,
                fan_mode="auto_low",
                target_humidity=None,
                current_humidity=None,
                swing_mode="auto",
                hvac_mode=HVACMode.HEAT_COOL,
                hvac_action=None,
                target_temp_high=24,
                target_temp_low=21,
                hvac_modes=[cls for cls in HVACMode if cls != HVACMode.HEAT],
            ),
        ]
    )


class DemoClimate(ClimateEntity):
    """Representation of a demo climate device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_translation_key = "ubercool"
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        unique_id: str,
        device_name: str,
        target_temperature: float | None,
        unit_of_measurement: str,
        preset: str | None,
        current_temperature: float,
        fan_mode: str | None,
        target_humidity: float | None,
        current_humidity: float | None,
        swing_mode: str | None,
        hvac_mode: HVACMode,
        hvac_action: HVACAction | None,
        target_temp_high: float | None,
        target_temp_low: float | None,
        hvac_modes: list[HVACMode],
        preset_modes: list[str] | None = None,
    ) -> None:
        """Initialize the climate device."""
        self._unique_id = unique_id
        self._attr_supported_features = SUPPORT_FLAGS
        if target_temperature is not None:
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if preset is not None:
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
        if fan_mode is not None:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
        if target_humidity is not None:
            self._attr_supported_features |= ClimateEntityFeature.TARGET_HUMIDITY
        if swing_mode is not None:
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE
        if HVACMode.HEAT_COOL in hvac_modes or HVACMode.AUTO in hvac_modes:
            self._attr_supported_features |= (
                ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            )
        self._attr_supported_features |= (
            ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        )
        self._target_temperature = target_temperature
        self._target_humidity = target_humidity
        self._unit_of_measurement = unit_of_measurement
        self._preset = preset
        self._preset_modes = preset_modes
        self._current_temperature = current_temperature
        self._current_humidity = current_humidity
        self._current_fan_mode = fan_mode
        self._hvac_action = hvac_action
        self._hvac_mode = hvac_mode
        self._current_swing_mode = swing_mode
        self._fan_modes = ["on_low", "on_high", "auto_low", "auto_high", "off"]
        self._hvac_modes = hvac_modes
        self._swing_modes = ["auto", "1", "2", "3", "off"]
        self._target_temperature_high = target_temp_high
        self._target_temperature_low = target_temp_low
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        return self._target_temperature_high

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        return self._target_temperature_low

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self._current_humidity

    @property
    def target_humidity(self) -> float | None:
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current operation ie. heat, cool, idle."""
        return self._hvac_action

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac target hvac state."""
        return self._hvac_mode

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available operation modes."""
        return self._hvac_modes

    @property
    def preset_mode(self) -> str | None:
        """Return preset mode."""
        return self._preset

    @property
    def preset_modes(self) -> list[str] | None:
        """Return preset modes."""
        return self._preset_modes

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_modes(self) -> list[str]:
        """Return the list of available fan modes."""
        return self._fan_modes

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        return self._current_swing_mode

    @property
    def swing_modes(self) -> list[str]:
        """List of available swing modes."""
        return self._swing_modes

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if (
            kwargs.get(ATTR_TARGET_TEMP_HIGH) is not None
            and kwargs.get(ATTR_TARGET_TEMP_LOW) is not None
        ):
            self._target_temperature_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            self._target_temperature_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            self._hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new humidity level."""
        self._target_humidity = humidity
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        self._current_swing_mode = swing_mode
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        self._current_fan_mode = fan_mode
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        self._hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Update preset_mode on."""
        self._preset = preset_mode
        self.async_write_ha_state()
