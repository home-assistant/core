"""Demo platform that offers a fake climate device."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN

SUPPORT_FLAGS = 0


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Demo climate devices."""
    async_add_entities(
        [
            DemoClimate(
                unique_id="climate_1",
                name="HeatPump",
                target_temperature=68,
                unit_of_measurement=TEMP_FAHRENHEIT,
                preset=None,
                current_temperature=77,
                fan_mode=None,
                target_humidity=None,
                current_humidity=None,
                swing_mode=None,
                hvac_mode=HVACMode.HEAT,
                hvac_action=HVACAction.HEATING,
                aux=None,
                target_temp_high=None,
                target_temp_low=None,
                hvac_modes=[HVACMode.HEAT, HVACMode.OFF],
            ),
            DemoClimate(
                unique_id="climate_2",
                name="Hvac",
                target_temperature=21,
                unit_of_measurement=TEMP_CELSIUS,
                preset=None,
                current_temperature=22,
                fan_mode="On High",
                target_humidity=67,
                current_humidity=54,
                swing_mode="Off",
                hvac_mode=HVACMode.COOL,
                hvac_action=HVACAction.COOLING,
                aux=False,
                target_temp_high=None,
                target_temp_low=None,
                hvac_modes=[cls.value for cls in HVACMode if cls != HVACMode.HEAT_COOL],
            ),
            DemoClimate(
                unique_id="climate_3",
                name="Ecobee",
                target_temperature=None,
                unit_of_measurement=TEMP_CELSIUS,
                preset="home",
                preset_modes=["home", "eco"],
                current_temperature=23,
                fan_mode="Auto Low",
                target_humidity=None,
                current_humidity=None,
                swing_mode="Auto",
                hvac_mode=HVACMode.HEAT_COOL,
                hvac_action=None,
                aux=None,
                target_temp_high=24,
                target_temp_low=21,
                hvac_modes=[cls.value for cls in HVACMode if cls != HVACMode.HEAT],
            ),
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo climate devices config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoClimate(ClimateEntity):
    """Representation of a demo climate device."""

    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        name: str,
        target_temperature: float | None,
        unit_of_measurement: str,
        preset: str | None,
        current_temperature: float,
        fan_mode: str | None,
        target_humidity: int | None,
        current_humidity: int | None,
        swing_mode: str | None,
        hvac_mode: HVACMode,
        hvac_action: HVACAction | None,
        aux: bool | None,
        target_temp_high: float | None,
        target_temp_low: float | None,
        hvac_modes: list[HVACMode],
        preset_modes: list[str] | None = None,
    ) -> None:
        """Initialize the climate device."""
        self._unique_id = unique_id
        self._attr_name = name
        self._support_flags = SUPPORT_FLAGS
        if target_temperature is not None:
            self._support_flags = (
                self._support_flags | ClimateEntityFeature.TARGET_TEMPERATURE
            )
        if preset is not None:
            self._support_flags = self._support_flags | ClimateEntityFeature.PRESET_MODE
        if fan_mode is not None:
            self._support_flags = self._support_flags | ClimateEntityFeature.FAN_MODE
        if target_humidity is not None:
            self._support_flags = (
                self._support_flags | ClimateEntityFeature.TARGET_HUMIDITY
            )
        if swing_mode is not None:
            self._support_flags = self._support_flags | ClimateEntityFeature.SWING_MODE
        if aux is not None:
            self._support_flags = self._support_flags | ClimateEntityFeature.AUX_HEAT
        if HVACMode.HEAT_COOL in hvac_modes or HVACMode.AUTO in hvac_modes:
            self._support_flags = (
                self._support_flags | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
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
        self._aux = aux
        self._current_swing_mode = swing_mode
        self._fan_modes = ["On Low", "On High", "Auto Low", "Auto High", "Off"]
        self._hvac_modes = hvac_modes
        self._swing_modes = ["Auto", "1", "2", "3", "Off"]
        self._target_temperature_high = target_temp_high
        self._target_temperature_low = target_temp_low

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            name=self.name,
        )

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return self._support_flags

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
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._current_humidity

    @property
    def target_humidity(self) -> int | None:
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
    def is_aux_heat(self) -> bool | None:
        """Return true if aux heat is on."""
        return self._aux

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

    async def async_turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        self._aux = True
        self.async_write_ha_state()

    async def async_turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        self._aux = False
        self.async_write_ha_state()
