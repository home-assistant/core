"""Provides functionality to interact with climate devices."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import functools as ft
import logging
from typing import Any, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    make_entity_service_schema,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.temperature import convert as convert_temperature

from .const import (  # noqa: F401
    ATTR_AUX_HEAT,
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_HUMIDITY,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    DOMAIN,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    HVAC_MODES,
    SERVICE_SET_AUX_HEAT,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SUPPORT_AUX_HEAT,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)

DEFAULT_MIN_TEMP = 7
DEFAULT_MAX_TEMP = 35
DEFAULT_MIN_HUMIDITY = 30
DEFAULT_MAX_HUMIDITY = 99

ENTITY_ID_FORMAT = DOMAIN + ".{}"
SCAN_INTERVAL = timedelta(seconds=60)

CONVERTIBLE_ATTRIBUTE = [ATTR_TEMPERATURE, ATTR_TARGET_TEMP_LOW, ATTR_TARGET_TEMP_HIGH]

_LOGGER = logging.getLogger(__name__)


SET_TEMPERATURE_SCHEMA = vol.All(
    cv.has_at_least_one_key(
        ATTR_TEMPERATURE, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW
    ),
    make_entity_service_schema(
        {
            vol.Exclusive(ATTR_TEMPERATURE, "temperature"): vol.Coerce(float),
            vol.Inclusive(ATTR_TARGET_TEMP_HIGH, "temperature"): vol.Coerce(float),
            vol.Inclusive(ATTR_TARGET_TEMP_LOW, "temperature"): vol.Coerce(float),
            vol.Optional(ATTR_HVAC_MODE): vol.Coerce(HVACMode),
        }
    ),
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up climate entities."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(SERVICE_TURN_ON, {}, "async_turn_on")
    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")
    component.async_register_entity_service(
        SERVICE_SET_HVAC_MODE,
        {vol.Required(ATTR_HVAC_MODE): vol.Coerce(HVACMode)},
        "async_set_hvac_mode",
    )
    component.async_register_entity_service(
        SERVICE_SET_PRESET_MODE,
        {vol.Required(ATTR_PRESET_MODE): cv.string},
        "async_set_preset_mode",
        [ClimateEntityFeature.PRESET_MODE],
    )
    component.async_register_entity_service(
        SERVICE_SET_AUX_HEAT,
        {vol.Required(ATTR_AUX_HEAT): cv.boolean},
        async_service_aux_heat,
        [ClimateEntityFeature.AUX_HEAT],
    )
    component.async_register_entity_service(
        SERVICE_SET_TEMPERATURE,
        SET_TEMPERATURE_SCHEMA,
        async_service_temperature_set,
        [
            ClimateEntityFeature.TARGET_TEMPERATURE,
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
        ],
    )
    component.async_register_entity_service(
        SERVICE_SET_HUMIDITY,
        {vol.Required(ATTR_HUMIDITY): vol.Coerce(int)},
        "async_set_humidity",
        [ClimateEntityFeature.TARGET_HUMIDITY],
    )
    component.async_register_entity_service(
        SERVICE_SET_FAN_MODE,
        {vol.Required(ATTR_FAN_MODE): cv.string},
        "async_set_fan_mode",
        [ClimateEntityFeature.FAN_MODE],
    )
    component.async_register_entity_service(
        SERVICE_SET_SWING_MODE,
        {vol.Required(ATTR_SWING_MODE): cv.string},
        "async_set_swing_mode",
        [ClimateEntityFeature.SWING_MODE],
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class ClimateEntityDescription(EntityDescription):
    """A class that describes climate entities."""


class ClimateEntity(Entity):
    """Base class for climate entities."""

    entity_description: ClimateEntityDescription
    _attr_current_humidity: int | None = None
    _attr_current_temperature: float | None = None
    _attr_fan_mode: str | None
    _attr_fan_modes: list[str] | None
    _attr_hvac_action: HVACAction | str | None = None
    _attr_hvac_mode: HVACMode | str | None
    _attr_hvac_modes: list[HVACMode] | list[str]
    _attr_is_aux_heat: bool | None
    _attr_max_humidity: int = DEFAULT_MAX_HUMIDITY
    _attr_max_temp: float
    _attr_min_humidity: int = DEFAULT_MIN_HUMIDITY
    _attr_min_temp: float
    _attr_precision: float
    _attr_preset_mode: str | None
    _attr_preset_modes: list[str] | None
    _attr_supported_features: int
    _attr_swing_mode: str | None
    _attr_swing_modes: list[str] | None
    _attr_target_humidity: int | None = None
    _attr_target_temperature_high: float | None
    _attr_target_temperature_low: float | None
    _attr_target_temperature_step: float | None = None
    _attr_target_temperature: float | None = None
    _attr_temperature_unit: str

    @final
    @property
    def state(self) -> str | None:
        """Return the current state."""
        if self.hvac_mode is None:
            return None
        if not isinstance(self.hvac_mode, HVACMode):
            return HVACMode(self.hvac_mode).value
        return self.hvac_mode.value

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        if hasattr(self, "_attr_precision"):
            return self._attr_precision
        if self.hass.config.units.temperature_unit == TEMP_CELSIUS:
            return PRECISION_TENTHS
        return PRECISION_WHOLE

    @property
    def capability_attributes(self) -> dict[str, Any] | None:
        """Return the capability attributes."""
        supported_features = self.supported_features
        data: dict[str, Any] = {
            ATTR_HVAC_MODES: self.hvac_modes,
            ATTR_MIN_TEMP: show_temp(
                self.hass, self.min_temp, self.temperature_unit, self.precision
            ),
            ATTR_MAX_TEMP: show_temp(
                self.hass, self.max_temp, self.temperature_unit, self.precision
            ),
        }

        if self.target_temperature_step:
            data[ATTR_TARGET_TEMP_STEP] = self.target_temperature_step

        if supported_features & ClimateEntityFeature.TARGET_HUMIDITY:
            data[ATTR_MIN_HUMIDITY] = self.min_humidity
            data[ATTR_MAX_HUMIDITY] = self.max_humidity

        if supported_features & ClimateEntityFeature.FAN_MODE:
            data[ATTR_FAN_MODES] = self.fan_modes

        if supported_features & ClimateEntityFeature.PRESET_MODE:
            data[ATTR_PRESET_MODES] = self.preset_modes

        if supported_features & ClimateEntityFeature.SWING_MODE:
            data[ATTR_SWING_MODES] = self.swing_modes

        return data

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        supported_features = self.supported_features
        data: dict[str, str | float | None] = {
            ATTR_CURRENT_TEMPERATURE: show_temp(
                self.hass,
                self.current_temperature,
                self.temperature_unit,
                self.precision,
            ),
        }

        if supported_features & ClimateEntityFeature.TARGET_TEMPERATURE:
            data[ATTR_TEMPERATURE] = show_temp(
                self.hass,
                self.target_temperature,
                self.temperature_unit,
                self.precision,
            )

        if supported_features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE:
            data[ATTR_TARGET_TEMP_HIGH] = show_temp(
                self.hass,
                self.target_temperature_high,
                self.temperature_unit,
                self.precision,
            )
            data[ATTR_TARGET_TEMP_LOW] = show_temp(
                self.hass,
                self.target_temperature_low,
                self.temperature_unit,
                self.precision,
            )

        if self.current_humidity is not None:
            data[ATTR_CURRENT_HUMIDITY] = self.current_humidity

        if supported_features & ClimateEntityFeature.TARGET_HUMIDITY:
            data[ATTR_HUMIDITY] = self.target_humidity

        if supported_features & ClimateEntityFeature.FAN_MODE:
            data[ATTR_FAN_MODE] = self.fan_mode

        if self.hvac_action:
            data[ATTR_HVAC_ACTION] = self.hvac_action

        if supported_features & ClimateEntityFeature.PRESET_MODE:
            data[ATTR_PRESET_MODE] = self.preset_mode

        if supported_features & ClimateEntityFeature.SWING_MODE:
            data[ATTR_SWING_MODE] = self.swing_mode

        if supported_features & ClimateEntityFeature.AUX_HEAT:
            data[ATTR_AUX_HEAT] = STATE_ON if self.is_aux_heat else STATE_OFF

        return data

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return self._attr_temperature_unit

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._attr_current_humidity

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        return self._attr_target_humidity

    @property
    def hvac_mode(self) -> HVACMode | str | None:
        """Return hvac operation ie. heat, cool mode."""
        return self._attr_hvac_mode

    @property
    def hvac_modes(self) -> list[HVACMode] | list[str]:
        """Return the list of available hvac operation modes."""
        return self._attr_hvac_modes

    @property
    def hvac_action(self) -> HVACAction | str | None:
        """Return the current running hvac operation if supported."""
        return self._attr_hvac_action

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._attr_current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._attr_target_temperature

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return self._attr_target_temperature_step

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach.

        Requires ClimateEntityFeature.TARGET_TEMPERATURE_RANGE.
        """
        return self._attr_target_temperature_high

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach.

        Requires ClimateEntityFeature.TARGET_TEMPERATURE_RANGE.
        """
        return self._attr_target_temperature_low

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        return self._attr_preset_mode

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        return self._attr_preset_modes

    @property
    def is_aux_heat(self) -> bool | None:
        """Return true if aux heater.

        Requires ClimateEntityFeature.AUX_HEAT.
        """
        return self._attr_is_aux_heat

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting.

        Requires ClimateEntityFeature.FAN_MODE.
        """
        return self._attr_fan_mode

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes.

        Requires ClimateEntityFeature.FAN_MODE.
        """
        return self._attr_fan_modes

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting.

        Requires ClimateEntityFeature.SWING_MODE.
        """
        return self._attr_swing_mode

    @property
    def swing_modes(self) -> list[str] | None:
        """Return the list of available swing modes.

        Requires ClimateEntityFeature.SWING_MODE.
        """
        return self._attr_swing_modes

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        raise NotImplementedError()

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        await self.hass.async_add_executor_job(
            ft.partial(self.set_temperature, **kwargs)
        )

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        raise NotImplementedError()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self.hass.async_add_executor_job(self.set_humidity, humidity)

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        raise NotImplementedError()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self.hass.async_add_executor_job(self.set_fan_mode, fan_mode)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        raise NotImplementedError()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self.hass.async_add_executor_job(self.set_hvac_mode, hvac_mode)

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        raise NotImplementedError()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        await self.hass.async_add_executor_job(self.set_swing_mode, swing_mode)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        raise NotImplementedError()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.hass.async_add_executor_job(self.set_preset_mode, preset_mode)

    def turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        raise NotImplementedError()

    async def async_turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        await self.hass.async_add_executor_job(self.turn_aux_heat_on)

    def turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        raise NotImplementedError()

    async def async_turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        await self.hass.async_add_executor_job(self.turn_aux_heat_off)

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        if hasattr(self, "turn_on"):
            await self.hass.async_add_executor_job(self.turn_on)  # type: ignore[attr-defined]
            return

        # Fake turn on
        for mode in (HVACMode.HEAT_COOL, HVACMode.HEAT, HVACMode.COOL):
            if mode not in self.hvac_modes:
                continue
            await self.async_set_hvac_mode(mode)
            break

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        if hasattr(self, "turn_off"):
            await self.hass.async_add_executor_job(self.turn_off)  # type: ignore[attr-defined]
            return

        # Fake turn off
        if HVACMode.OFF in self.hvac_modes:
            await self.async_set_hvac_mode(HVACMode.OFF)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return self._attr_supported_features

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if not hasattr(self, "_attr_min_temp"):
            return convert_temperature(
                DEFAULT_MIN_TEMP, TEMP_CELSIUS, self.temperature_unit
            )
        return self._attr_min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if not hasattr(self, "_attr_max_temp"):
            return convert_temperature(
                DEFAULT_MAX_TEMP, TEMP_CELSIUS, self.temperature_unit
            )
        return self._attr_max_temp

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return self._attr_min_humidity

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return self._attr_max_humidity


async def async_service_aux_heat(
    entity: ClimateEntity, service_call: ServiceCall
) -> None:
    """Handle aux heat service."""
    if service_call.data[ATTR_AUX_HEAT]:
        await entity.async_turn_aux_heat_on()
    else:
        await entity.async_turn_aux_heat_off()


async def async_service_temperature_set(
    entity: ClimateEntity, service_call: ServiceCall
) -> None:
    """Handle set temperature service."""
    hass = entity.hass
    kwargs = {}

    for value, temp in service_call.data.items():
        if value in CONVERTIBLE_ATTRIBUTE:
            kwargs[value] = convert_temperature(
                temp, hass.config.units.temperature_unit, entity.temperature_unit
            )
        else:
            kwargs[value] = temp

    await entity.async_set_temperature(**kwargs)
