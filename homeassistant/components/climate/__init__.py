"""Provides functionality to interact with climate devices."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import functools as ft
from functools import cached_property
import logging
from typing import Any, Literal, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.deprecation import (
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (  # noqa: F401
    _DEPRECATED_HVAC_MODE_AUTO,
    _DEPRECATED_HVAC_MODE_COOL,
    _DEPRECATED_HVAC_MODE_DRY,
    _DEPRECATED_HVAC_MODE_FAN_ONLY,
    _DEPRECATED_HVAC_MODE_HEAT,
    _DEPRECATED_HVAC_MODE_HEAT_COOL,
    _DEPRECATED_HVAC_MODE_OFF,
    _DEPRECATED_SUPPORT_FAN_MODE,
    _DEPRECATED_SUPPORT_PRESET_MODE,
    _DEPRECATED_SUPPORT_SWING_MODE,
    _DEPRECATED_SUPPORT_TARGET_HUMIDITY,
    _DEPRECATED_SUPPORT_TARGET_TEMPERATURE,
    _DEPRECATED_SUPPORT_TARGET_TEMPERATURE_RANGE,
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
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_FOCUS,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    FAN_OFF,
    FAN_ON,
    FAN_TOP,
    HVAC_MODES,
    PRESET_ACTIVITY,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_NONE,
    PRESET_SLEEP,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_ON,
    SWING_VERTICAL,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=60)

DEFAULT_MIN_TEMP = 7
DEFAULT_MAX_TEMP = 35
DEFAULT_MIN_HUMIDITY = 30
DEFAULT_MAX_HUMIDITY = 99

CONVERTIBLE_ATTRIBUTE = [ATTR_TEMPERATURE, ATTR_TARGET_TEMP_LOW, ATTR_TARGET_TEMP_HIGH]

# Can be removed in 2025.1 after deprecation period of the new feature flags
CHECK_TURN_ON_OFF_FEATURE_FLAG = (
    ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
)

SET_TEMPERATURE_SCHEMA = vol.All(
    cv.has_at_least_one_key(
        ATTR_TEMPERATURE, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW
    ),
    cv.make_entity_service_schema(
        {
            vol.Exclusive(ATTR_TEMPERATURE, "temperature"): vol.Coerce(float),
            vol.Inclusive(ATTR_TARGET_TEMP_HIGH, "temperature"): vol.Coerce(float),
            vol.Inclusive(ATTR_TARGET_TEMP_LOW, "temperature"): vol.Coerce(float),
            vol.Optional(ATTR_HVAC_MODE): vol.Coerce(HVACMode),
        }
    ),
)

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up climate entities."""
    component = hass.data[DOMAIN] = EntityComponent[ClimateEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_ON,
        None,
        "async_turn_on",
        [ClimateEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF,
        None,
        "async_turn_off",
        [ClimateEntityFeature.TURN_OFF],
    )
    component.async_register_entity_service(
        SERVICE_TOGGLE,
        None,
        "async_toggle",
        [ClimateEntityFeature.TURN_OFF, ClimateEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        SERVICE_SET_HVAC_MODE,
        {vol.Required(ATTR_HVAC_MODE): vol.Coerce(HVACMode)},
        "async_set_hvac_mode",
    )
    component.async_register_entity_service(
        SERVICE_SET_PRESET_MODE,
        {vol.Required(ATTR_PRESET_MODE): cv.string},
        "async_handle_set_preset_mode_service",
        [ClimateEntityFeature.PRESET_MODE],
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
        "async_handle_set_fan_mode_service",
        [ClimateEntityFeature.FAN_MODE],
    )
    component.async_register_entity_service(
        SERVICE_SET_SWING_MODE,
        {vol.Required(ATTR_SWING_MODE): cv.string},
        "async_handle_set_swing_mode_service",
        [ClimateEntityFeature.SWING_MODE],
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[ClimateEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[ClimateEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class ClimateEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes climate entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {
    "temperature_unit",
    "current_humidity",
    "target_humidity",
    "hvac_mode",
    "hvac_modes",
    "hvac_action",
    "current_temperature",
    "target_temperature",
    "target_temperature_step",
    "target_temperature_high",
    "target_temperature_low",
    "preset_mode",
    "preset_modes",
    "fan_mode",
    "fan_modes",
    "swing_mode",
    "swing_modes",
    "supported_features",
    "min_temp",
    "max_temp",
    "min_humidity",
    "max_humidity",
}


class ClimateEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for climate entities."""

    _entity_component_unrecorded_attributes = frozenset(
        {
            ATTR_HVAC_MODES,
            ATTR_FAN_MODES,
            ATTR_SWING_MODES,
            ATTR_MIN_TEMP,
            ATTR_MAX_TEMP,
            ATTR_MIN_HUMIDITY,
            ATTR_MAX_HUMIDITY,
            ATTR_TARGET_TEMP_STEP,
            ATTR_PRESET_MODES,
        }
    )

    entity_description: ClimateEntityDescription
    _attr_current_humidity: int | None = None
    _attr_current_temperature: float | None = None
    _attr_fan_mode: str | None
    _attr_fan_modes: list[str] | None
    _attr_hvac_action: HVACAction | None = None
    _attr_hvac_mode: HVACMode | None
    _attr_hvac_modes: list[HVACMode]
    _attr_max_humidity: float = DEFAULT_MAX_HUMIDITY
    _attr_max_temp: float
    _attr_min_humidity: float = DEFAULT_MIN_HUMIDITY
    _attr_min_temp: float
    _attr_precision: float
    _attr_preset_mode: str | None
    _attr_preset_modes: list[str] | None
    _attr_supported_features: ClimateEntityFeature = ClimateEntityFeature(0)
    _attr_swing_mode: str | None
    _attr_swing_modes: list[str] | None
    _attr_target_humidity: float | None = None
    _attr_target_temperature_high: float | None
    _attr_target_temperature_low: float | None
    _attr_target_temperature_step: float | None = None
    _attr_target_temperature: float | None = None
    _attr_temperature_unit: str

    __mod_supported_features: ClimateEntityFeature = ClimateEntityFeature(0)
    # Integrations should set `_enable_turn_on_off_backwards_compatibility` to False
    # once migrated and set the feature flags TURN_ON/TURN_OFF as needed.
    _enable_turn_on_off_backwards_compatibility: bool = True

    def __getattribute__(self, __name: str) -> Any:
        """Get attribute.

        Modify return of `supported_features` to
        include `_mod_supported_features` if attribute is set.
        """
        if __name != "supported_features":
            return super().__getattribute__(__name)

        # Convert the supported features to ClimateEntityFeature.
        # Remove this compatibility shim in 2025.1 or later.
        _supported_features: ClimateEntityFeature = super().__getattribute__(
            "supported_features"
        )
        _mod_supported_features: ClimateEntityFeature = super().__getattribute__(
            "_ClimateEntity__mod_supported_features"
        )
        if type(_supported_features) is int:  # noqa: E721
            _features = ClimateEntityFeature(_supported_features)
            self._report_deprecated_supported_features_values(_features)
        else:
            _features = _supported_features

        if not _mod_supported_features:
            return _features

        # Add automatically calculated ClimateEntityFeature.TURN_OFF/TURN_ON to
        # supported features and return it
        return _features | _mod_supported_features

    @callback
    def add_to_platform_start(
        self,
        hass: HomeAssistant,
        platform: EntityPlatform,
        parallel_updates: asyncio.Semaphore | None,
    ) -> None:
        """Start adding an entity to a platform."""
        super().add_to_platform_start(hass, platform, parallel_updates)

        def _report_turn_on_off(feature: str, method: str) -> None:
            """Log warning not implemented turn on/off feature."""
            report_issue = self._suggest_report_issue()
            if feature.startswith("TURN"):
                message = (
                    "Entity %s (%s) does not set ClimateEntityFeature.%s"
                    " but implements the %s method. Please %s"
                )
            else:
                message = (
                    "Entity %s (%s) implements HVACMode(s): %s and therefore implicitly"
                    " supports the %s methods without setting the proper"
                    " ClimateEntityFeature. Please %s"
                )
            _LOGGER.warning(
                message,
                self.entity_id,
                type(self),
                feature,
                method,
                report_issue,
            )

        # Adds ClimateEntityFeature.TURN_OFF/TURN_ON depending on service calls implemented
        # This should be removed in 2025.1.
        if self._enable_turn_on_off_backwards_compatibility is False:
            # Return if integration has migrated already
            return

        supported_features = self.supported_features
        if supported_features & CHECK_TURN_ON_OFF_FEATURE_FLAG:
            # The entity supports both turn_on and turn_off, the backwards compatibility
            # checks are not needed
            return

        if not supported_features & ClimateEntityFeature.TURN_OFF and (
            type(self).async_turn_off is not ClimateEntity.async_turn_off
            or type(self).turn_off is not ClimateEntity.turn_off
        ):
            # turn_off implicitly supported by implementing turn_off method
            _report_turn_on_off("TURN_OFF", "turn_off")
            self.__mod_supported_features |= (  # pylint: disable=unused-private-member
                ClimateEntityFeature.TURN_OFF
            )

        if not supported_features & ClimateEntityFeature.TURN_ON and (
            type(self).async_turn_on is not ClimateEntity.async_turn_on
            or type(self).turn_on is not ClimateEntity.turn_on
        ):
            # turn_on implicitly supported by implementing turn_on method
            _report_turn_on_off("TURN_ON", "turn_on")
            self.__mod_supported_features |= (  # pylint: disable=unused-private-member
                ClimateEntityFeature.TURN_ON
            )

        if (modes := self.hvac_modes) and len(modes) >= 2 and HVACMode.OFF in modes:
            # turn_on/off implicitly supported by including more modes than 1 and one of these
            # are HVACMode.OFF
            _modes = [_mode for _mode in modes if _mode is not None]
            _report_turn_on_off(", ".join(_modes or []), "turn_on/turn_off")
            self.__mod_supported_features |= (  # pylint: disable=unused-private-member
                ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
            )

    @final
    @property
    def state(self) -> str | None:
        """Return the current state."""
        hvac_mode = self.hvac_mode
        if hvac_mode is None:
            return None
        # Support hvac_mode as string for custom integration backwards compatibility
        if not isinstance(hvac_mode, HVACMode):
            return HVACMode(hvac_mode).value  # type: ignore[unreachable]
        return hvac_mode.value

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        if hasattr(self, "_attr_precision"):
            return self._attr_precision
        if self.hass.config.units.temperature_unit == UnitOfTemperature.CELSIUS:
            return PRECISION_TENTHS
        return PRECISION_WHOLE

    @property
    def capability_attributes(self) -> dict[str, Any] | None:
        """Return the capability attributes."""
        supported_features = self.supported_features
        temperature_unit = self.temperature_unit
        precision = self.precision
        hass = self.hass

        data: dict[str, Any] = {
            ATTR_HVAC_MODES: self.hvac_modes,
            ATTR_MIN_TEMP: show_temp(hass, self.min_temp, temperature_unit, precision),
            ATTR_MAX_TEMP: show_temp(hass, self.max_temp, temperature_unit, precision),
        }

        if target_temperature_step := self.target_temperature_step:
            data[ATTR_TARGET_TEMP_STEP] = target_temperature_step

        if ClimateEntityFeature.TARGET_HUMIDITY in supported_features:
            data[ATTR_MIN_HUMIDITY] = self.min_humidity
            data[ATTR_MAX_HUMIDITY] = self.max_humidity

        if ClimateEntityFeature.FAN_MODE in supported_features:
            data[ATTR_FAN_MODES] = self.fan_modes

        if ClimateEntityFeature.PRESET_MODE in supported_features:
            data[ATTR_PRESET_MODES] = self.preset_modes

        if ClimateEntityFeature.SWING_MODE in supported_features:
            data[ATTR_SWING_MODES] = self.swing_modes

        return data

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        supported_features = self.supported_features
        temperature_unit = self.temperature_unit
        precision = self.precision
        hass = self.hass

        data: dict[str, str | float | None] = {
            ATTR_CURRENT_TEMPERATURE: show_temp(
                hass, self.current_temperature, temperature_unit, precision
            ),
        }

        if ClimateEntityFeature.TARGET_TEMPERATURE in supported_features:
            data[ATTR_TEMPERATURE] = show_temp(
                hass,
                self.target_temperature,
                temperature_unit,
                precision,
            )

        if ClimateEntityFeature.TARGET_TEMPERATURE_RANGE in supported_features:
            data[ATTR_TARGET_TEMP_HIGH] = show_temp(
                hass, self.target_temperature_high, temperature_unit, precision
            )
            data[ATTR_TARGET_TEMP_LOW] = show_temp(
                hass, self.target_temperature_low, temperature_unit, precision
            )

        if (current_humidity := self.current_humidity) is not None:
            data[ATTR_CURRENT_HUMIDITY] = current_humidity

        if ClimateEntityFeature.TARGET_HUMIDITY in supported_features:
            data[ATTR_HUMIDITY] = self.target_humidity

        if ClimateEntityFeature.FAN_MODE in supported_features:
            data[ATTR_FAN_MODE] = self.fan_mode

        if hvac_action := self.hvac_action:
            data[ATTR_HVAC_ACTION] = hvac_action

        if ClimateEntityFeature.PRESET_MODE in supported_features:
            data[ATTR_PRESET_MODE] = self.preset_mode

        if ClimateEntityFeature.SWING_MODE in supported_features:
            data[ATTR_SWING_MODE] = self.swing_mode

        return data

    @cached_property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return self._attr_temperature_unit

    @cached_property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self._attr_current_humidity

    @cached_property
    def target_humidity(self) -> float | None:
        """Return the humidity we try to reach."""
        return self._attr_target_humidity

    @cached_property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        return self._attr_hvac_mode

    @cached_property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        return self._attr_hvac_modes

    @cached_property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""
        return self._attr_hvac_action

    @cached_property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._attr_current_temperature

    @cached_property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._attr_target_temperature

    @cached_property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return self._attr_target_temperature_step

    @cached_property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach.

        Requires ClimateEntityFeature.TARGET_TEMPERATURE_RANGE.
        """
        return self._attr_target_temperature_high

    @cached_property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach.

        Requires ClimateEntityFeature.TARGET_TEMPERATURE_RANGE.
        """
        return self._attr_target_temperature_low

    @cached_property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        return self._attr_preset_mode

    @cached_property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        return self._attr_preset_modes

    @cached_property
    def fan_mode(self) -> str | None:
        """Return the fan setting.

        Requires ClimateEntityFeature.FAN_MODE.
        """
        return self._attr_fan_mode

    @cached_property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes.

        Requires ClimateEntityFeature.FAN_MODE.
        """
        return self._attr_fan_modes

    @cached_property
    def swing_mode(self) -> str | None:
        """Return the swing setting.

        Requires ClimateEntityFeature.SWING_MODE.
        """
        return self._attr_swing_mode

    @cached_property
    def swing_modes(self) -> list[str] | None:
        """Return the list of available swing modes.

        Requires ClimateEntityFeature.SWING_MODE.
        """
        return self._attr_swing_modes

    @final
    @callback
    def _valid_mode_or_raise(
        self,
        mode_type: Literal["preset", "swing", "fan"],
        mode: str,
        modes: list[str] | None,
    ) -> None:
        """Raise ServiceValidationError on invalid modes."""
        if modes and mode in modes:
            return
        modes_str: str = ", ".join(modes) if modes else ""
        if mode_type == "preset":
            translation_key = "not_valid_preset_mode"
        elif mode_type == "swing":
            translation_key = "not_valid_swing_mode"
        elif mode_type == "fan":
            translation_key = "not_valid_fan_mode"
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={
                "mode": mode,
                "modes": modes_str,
            },
        )

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        raise NotImplementedError

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self.hass.async_add_executor_job(
            ft.partial(self.set_temperature, **kwargs)
        )

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        raise NotImplementedError

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self.hass.async_add_executor_job(self.set_humidity, humidity)

    @final
    async def async_handle_set_fan_mode_service(self, fan_mode: str) -> None:
        """Validate and set new preset mode."""
        self._valid_mode_or_raise("fan", fan_mode, self.fan_modes)
        await self.async_set_fan_mode(fan_mode)

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        raise NotImplementedError

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self.hass.async_add_executor_job(self.set_fan_mode, fan_mode)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        raise NotImplementedError

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self.hass.async_add_executor_job(self.set_hvac_mode, hvac_mode)

    @final
    async def async_handle_set_swing_mode_service(self, swing_mode: str) -> None:
        """Validate and set new preset mode."""
        self._valid_mode_or_raise("swing", swing_mode, self.swing_modes)
        await self.async_set_swing_mode(swing_mode)

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        raise NotImplementedError

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        await self.hass.async_add_executor_job(self.set_swing_mode, swing_mode)

    @final
    async def async_handle_set_preset_mode_service(self, preset_mode: str) -> None:
        """Validate and set new preset mode."""
        self._valid_mode_or_raise("preset", preset_mode, self.preset_modes)
        await self.async_set_preset_mode(preset_mode)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        raise NotImplementedError

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.hass.async_add_executor_job(self.set_preset_mode, preset_mode)

    def turn_on(self) -> None:
        """Turn the entity on."""
        raise NotImplementedError

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        # Forward to self.turn_on if it's been overridden.
        if type(self).turn_on is not ClimateEntity.turn_on:
            await self.hass.async_add_executor_job(self.turn_on)
            return

        # If there are only two HVAC modes, and one of those modes is OFF,
        # then we can just turn on the other mode.
        if len(self.hvac_modes) == 2 and HVACMode.OFF in self.hvac_modes:
            for mode in self.hvac_modes:
                if mode != HVACMode.OFF:
                    await self.async_set_hvac_mode(mode)
                    return

        # Fake turn on
        for mode in (HVACMode.HEAT_COOL, HVACMode.HEAT, HVACMode.COOL):
            if mode not in self.hvac_modes:
                continue
            await self.async_set_hvac_mode(mode)
            return

        raise NotImplementedError

    def turn_off(self) -> None:
        """Turn the entity off."""
        raise NotImplementedError

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        # Forward to self.turn_on if it's been overridden.
        if type(self).turn_off is not ClimateEntity.turn_off:
            await self.hass.async_add_executor_job(self.turn_off)
            return

        # Fake turn off
        if HVACMode.OFF in self.hvac_modes:
            await self.async_set_hvac_mode(HVACMode.OFF)
            return

        raise NotImplementedError

    def toggle(self) -> None:
        """Toggle the entity."""
        raise NotImplementedError

    async def async_toggle(self) -> None:
        """Toggle the entity."""
        # Forward to self.toggle if it's been overridden.
        if type(self).toggle is not ClimateEntity.toggle:
            await self.hass.async_add_executor_job(self.toggle)
            return

        # We assume that since turn_off is supported, HVACMode.OFF is as well.
        if self.hvac_mode == HVACMode.OFF:
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    @cached_property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return self._attr_supported_features

    @cached_property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if not hasattr(self, "_attr_min_temp"):
            return TemperatureConverter.convert(
                DEFAULT_MIN_TEMP, UnitOfTemperature.CELSIUS, self.temperature_unit
            )
        return self._attr_min_temp

    @cached_property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if not hasattr(self, "_attr_max_temp"):
            return TemperatureConverter.convert(
                DEFAULT_MAX_TEMP, UnitOfTemperature.CELSIUS, self.temperature_unit
            )
        return self._attr_max_temp

    @cached_property
    def min_humidity(self) -> float:
        """Return the minimum humidity."""
        return self._attr_min_humidity

    @cached_property
    def max_humidity(self) -> float:
        """Return the maximum humidity."""
        return self._attr_max_humidity


async def async_service_temperature_set(
    entity: ClimateEntity, service_call: ServiceCall
) -> None:
    """Handle set temperature service."""
    hass = entity.hass
    kwargs = {}
    min_temp = entity.min_temp
    max_temp = entity.max_temp
    temp_unit = entity.temperature_unit

    for value, temp in service_call.data.items():
        if value in CONVERTIBLE_ATTRIBUTE:
            kwargs[value] = check_temp = TemperatureConverter.convert(
                temp, hass.config.units.temperature_unit, temp_unit
            )

            _LOGGER.debug(
                "Check valid temperature %d %s (%d %s) in range %d %s - %d %s",
                check_temp,
                entity.temperature_unit,
                temp,
                hass.config.units.temperature_unit,
                min_temp,
                temp_unit,
                max_temp,
                temp_unit,
            )
            if check_temp < min_temp or check_temp > max_temp:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="temp_out_of_range",
                    translation_placeholders={
                        "check_temp": str(check_temp),
                        "min_temp": str(min_temp),
                        "max_temp": str(max_temp),
                    },
                )
        else:
            kwargs[value] = temp

    await entity.async_set_temperature(**kwargs)


# As we import deprecated constants from the const module, we need to add these two functions
# otherwise this module will be logged for using deprecated constants and not the custom component
# These can be removed if no deprecated constant are in this module anymore
__getattr__ = ft.partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = ft.partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
