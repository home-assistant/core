"""Provides functionality to interact with climate devices."""

from datetime import timedelta
import functools as ft
import logging
from typing import TYPE_CHECKING, Any, Literal, final, override

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry

# ATTR_TEMPERATURE and the SERVICE_* constants are re-exported for integrations
# importing them from the climate component root.
from homeassistant.const import (  # noqa: F401
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.deprecation import (
    DeprecatedEntityAlias,
    migrate_deprecated_entity_members,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.frame import ReportBehavior
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (  # noqa: F401
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
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_HORIZONTAL_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TARGET_HUMIDITY_STEP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    DATA_COMPONENT,
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
    INTENT_SET_FAN_MODE,
    INTENT_SET_TEMPERATURE,
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
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_ON,
    SWING_VERTICAL,
    ClimateEntityCapabilityAttribute,
    ClimateEntityFeature,
    ClimateEntityStateAttribute,
    HVACAction,
    HVACMode,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=60)

DEFAULT_MIN_TEMP = 7
DEFAULT_MAX_TEMP = 35
DEFAULT_MIN_HUMIDITY = 30
DEFAULT_MAX_HUMIDITY = 99


# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up climate entities."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[ClimateEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class ClimateEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes climate entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {
    "native_temperature_unit",
    "current_humidity",
    "target_humidity",
    "hvac_mode",
    "hvac_modes",
    "hvac_action",
    "native_current_temperature",
    "native_target_temperature",
    "target_temperature_step",
    "native_target_temperature_high",
    "native_target_temperature_low",
    "preset_mode",
    "preset_modes",
    "fan_mode",
    "fan_modes",
    "swing_mode",
    "swing_modes",
    "swing_horizontal_mode",
    "swing_horizontal_modes",
    "supported_features",
    "min_temp",
    "max_temp",
    "min_humidity",
    "max_humidity",
    "target_humidity_step",
}


class ClimateEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for climate entities."""

    _entity_component_unrecorded_attributes = frozenset(
        {
            ClimateEntityCapabilityAttribute.HVAC_MODES,
            ClimateEntityCapabilityAttribute.FAN_MODES,
            ClimateEntityCapabilityAttribute.SWING_MODES,
            ClimateEntityCapabilityAttribute.MIN_TEMP,
            ClimateEntityCapabilityAttribute.MAX_TEMP,
            ClimateEntityCapabilityAttribute.MIN_HUMIDITY,
            ClimateEntityCapabilityAttribute.MAX_HUMIDITY,
            ClimateEntityCapabilityAttribute.TARGET_HUMIDITY_STEP,
            ClimateEntityCapabilityAttribute.TARGET_TEMP_STEP,
            ClimateEntityCapabilityAttribute.PRESET_MODES,
        }
    )

    entity_description: ClimateEntityDescription
    _attr_current_humidity: float | None = None
    _attr_fan_mode: str | None
    _attr_fan_modes: list[str] | None
    _attr_hvac_action: HVACAction | None = None
    _attr_hvac_mode: HVACMode | None
    _attr_hvac_modes: list[HVACMode]
    _attr_max_humidity: float = DEFAULT_MAX_HUMIDITY
    _attr_max_temp: float
    _attr_min_humidity: float = DEFAULT_MIN_HUMIDITY
    _attr_min_temp: float
    _attr_native_current_temperature: float | None = None
    _attr_native_target_temperature: float | None = None
    _attr_native_target_temperature_high: float | None
    _attr_native_target_temperature_low: float | None
    _attr_native_temperature_unit: str
    _attr_precision: float
    _attr_preset_mode: str | None
    _attr_preset_modes: list[str] | None
    _attr_supported_features: ClimateEntityFeature = ClimateEntityFeature(0)
    _attr_swing_mode: str | None
    _attr_swing_modes: list[str] | None
    _attr_swing_horizontal_mode: str | None
    _attr_swing_horizontal_modes: list[str] | None
    _attr_target_humidity: float | None = None
    _attr_target_humidity_step: int | None = None
    _attr_target_temperature_step: float | None = None

    @override
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Serve the native temperature API of subclasses still providing the old one."""
        super().__init_subclass__(**kwargs)
        migrate_deprecated_entity_members(cls, ClimateEntity)

    @final
    @property
    @override
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
    @override
    def capability_attributes(self) -> dict[str, Any] | None:
        """Return the capability attributes."""
        supported_features = self.supported_features
        native_temperature_unit = self.native_temperature_unit
        precision = self.precision
        hass = self.hass

        data: dict[str, Any] = {
            ClimateEntityCapabilityAttribute.HVAC_MODES: self.hvac_modes,
            ClimateEntityCapabilityAttribute.MIN_TEMP: show_temp(
                hass, self.min_temp, native_temperature_unit, precision
            ),
            ClimateEntityCapabilityAttribute.MAX_TEMP: show_temp(
                hass, self.max_temp, native_temperature_unit, precision
            ),
        }

        if target_temperature_step := self.target_temperature_step:
            data[ClimateEntityCapabilityAttribute.TARGET_TEMP_STEP] = (
                target_temperature_step
            )

        if ClimateEntityFeature.TARGET_HUMIDITY in supported_features:
            data[ClimateEntityCapabilityAttribute.MIN_HUMIDITY] = self.min_humidity
            data[ClimateEntityCapabilityAttribute.MAX_HUMIDITY] = self.max_humidity

            if self.target_humidity_step is not None:
                data[ClimateEntityCapabilityAttribute.TARGET_HUMIDITY_STEP] = (
                    self.target_humidity_step
                )

        if ClimateEntityFeature.FAN_MODE in supported_features:
            data[ClimateEntityCapabilityAttribute.FAN_MODES] = self.fan_modes

        if ClimateEntityFeature.PRESET_MODE in supported_features:
            data[ClimateEntityCapabilityAttribute.PRESET_MODES] = self.preset_modes

        if ClimateEntityFeature.SWING_MODE in supported_features:
            data[ClimateEntityCapabilityAttribute.SWING_MODES] = self.swing_modes

        if ClimateEntityFeature.SWING_HORIZONTAL_MODE in supported_features:
            data[ClimateEntityCapabilityAttribute.SWING_HORIZONTAL_MODES] = (
                self.swing_horizontal_modes
            )

        return data

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        supported_features = self.supported_features
        native_temperature_unit = self.native_temperature_unit
        precision = self.precision
        hass = self.hass

        data: dict[str, str | float | None] = {
            ClimateEntityStateAttribute.CURRENT_TEMPERATURE: show_temp(
                hass,
                self.native_current_temperature,
                native_temperature_unit,
                precision,
            ),
            ClimateEntityStateAttribute.TEMPERATURE_UNIT: (
                hass.config.units.temperature_unit
            ),
        }

        if ClimateEntityFeature.TARGET_TEMPERATURE in supported_features:
            data[ClimateEntityStateAttribute.TARGET_TEMPERATURE] = show_temp(
                hass,
                self.native_target_temperature,
                native_temperature_unit,
                precision,
            )

        if ClimateEntityFeature.TARGET_TEMPERATURE_RANGE in supported_features:
            data[ClimateEntityStateAttribute.TARGET_TEMP_HIGH] = show_temp(
                hass,
                self.native_target_temperature_high,
                native_temperature_unit,
                precision,
            )
            data[ClimateEntityStateAttribute.TARGET_TEMP_LOW] = show_temp(
                hass,
                self.native_target_temperature_low,
                native_temperature_unit,
                precision,
            )

        if (current_humidity := self.current_humidity) is not None:
            data[ClimateEntityStateAttribute.CURRENT_HUMIDITY] = current_humidity

        if ClimateEntityFeature.TARGET_HUMIDITY in supported_features:
            data[ClimateEntityStateAttribute.TARGET_HUMIDITY] = self.target_humidity

        if ClimateEntityFeature.FAN_MODE in supported_features:
            data[ClimateEntityStateAttribute.FAN_MODE] = self.fan_mode

        if hvac_action := self.hvac_action:
            data[ClimateEntityStateAttribute.HVAC_ACTION] = hvac_action

        if ClimateEntityFeature.PRESET_MODE in supported_features:
            data[ClimateEntityStateAttribute.PRESET_MODE] = self.preset_mode

        if ClimateEntityFeature.SWING_MODE in supported_features:
            data[ClimateEntityStateAttribute.SWING_MODE] = self.swing_mode

        if ClimateEntityFeature.SWING_HORIZONTAL_MODE in supported_features:
            data[ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE] = (
                self.swing_horizontal_mode
            )

        return data

    @cached_property
    def native_temperature_unit(self) -> str:
        """Return the unit of measurement the entity reports temperatures in."""
        return self._attr_native_temperature_unit

    if TYPE_CHECKING:
        _attr_temperature_unit: str

        @cached_property
        def temperature_unit(self) -> str:
            """Deprecated, use native_temperature_unit instead."""

    else:
        temperature_unit = DeprecatedEntityAlias[str](
            "native_temperature_unit",
            "2027.11",
            core_integration_behavior=ReportBehavior.IGNORE,
        )
        _attr_temperature_unit = DeprecatedEntityAlias[str](
            "_attr_native_temperature_unit",
            "2027.11",
            core_integration_behavior=ReportBehavior.IGNORE,
        )

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
    def native_current_temperature(self) -> float | None:
        """Return the current temperature in the native unit."""
        return self._attr_native_current_temperature

    if TYPE_CHECKING:
        _attr_current_temperature: float | None

        @cached_property
        def current_temperature(self) -> float | None:
            """Deprecated, use native_current_temperature instead."""

    else:
        current_temperature = DeprecatedEntityAlias[float | None](
            "native_current_temperature",
            "2027.11",
            core_integration_behavior=ReportBehavior.IGNORE,
        )
        _attr_current_temperature = DeprecatedEntityAlias[float | None](
            "_attr_native_current_temperature",
            "2027.11",
            core_integration_behavior=ReportBehavior.IGNORE,
        )

    @cached_property
    def native_target_temperature(self) -> float | None:
        """Return the temperature we try to reach, in the native unit."""
        return self._attr_native_target_temperature

    if TYPE_CHECKING:
        _attr_target_temperature: float | None

        @cached_property
        def target_temperature(self) -> float | None:
            """Deprecated, use native_target_temperature instead."""

    else:
        target_temperature = DeprecatedEntityAlias[float | None](
            "native_target_temperature",
            "2027.11",
            core_integration_behavior=ReportBehavior.IGNORE,
        )
        _attr_target_temperature = DeprecatedEntityAlias[float | None](
            "_attr_native_target_temperature",
            "2027.11",
            core_integration_behavior=ReportBehavior.IGNORE,
        )

    @cached_property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return self._attr_target_temperature_step

    @cached_property
    def native_target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach.

        In the native unit. Requires ClimateEntityFeature.TARGET_TEMPERATURE_RANGE.
        """
        return self._attr_native_target_temperature_high

    if TYPE_CHECKING:
        _attr_target_temperature_high: float | None

        @cached_property
        def target_temperature_high(self) -> float | None:
            """Deprecated, use native_target_temperature_high instead."""

    else:
        target_temperature_high = DeprecatedEntityAlias[float | None](
            "native_target_temperature_high",
            "2027.11",
            core_integration_behavior=ReportBehavior.IGNORE,
        )
        _attr_target_temperature_high = DeprecatedEntityAlias[float | None](
            "_attr_native_target_temperature_high",
            "2027.11",
            core_integration_behavior=ReportBehavior.IGNORE,
        )

    @cached_property
    def native_target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach.

        In the native unit. Requires ClimateEntityFeature.TARGET_TEMPERATURE_RANGE.
        """
        return self._attr_native_target_temperature_low

    if TYPE_CHECKING:
        _attr_target_temperature_low: float | None

        @cached_property
        def target_temperature_low(self) -> float | None:
            """Deprecated, use native_target_temperature_low instead."""

    else:
        target_temperature_low = DeprecatedEntityAlias[float | None](
            "native_target_temperature_low",
            "2027.11",
            core_integration_behavior=ReportBehavior.IGNORE,
        )
        _attr_target_temperature_low = DeprecatedEntityAlias[float | None](
            "_attr_native_target_temperature_low",
            "2027.11",
            core_integration_behavior=ReportBehavior.IGNORE,
        )

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

    @cached_property
    def swing_horizontal_mode(self) -> str | None:
        """Return the horizontal swing setting.

        Requires ClimateEntityFeature.SWING_HORIZONTAL_MODE.
        """
        return self._attr_swing_horizontal_mode

    @cached_property
    def swing_horizontal_modes(self) -> list[str] | None:
        """Return the list of available horizontal swing modes.

        Requires ClimateEntityFeature.SWING_HORIZONTAL_MODE.
        """
        return self._attr_swing_horizontal_modes

    @final
    @callback
    def _valid_mode_or_raise(
        self,
        mode_type: Literal["preset", "horizontal_swing", "swing", "fan", "hvac"],
        mode: str | HVACMode,
        modes: list[str] | list[HVACMode] | None,
    ) -> None:
        """Raise ServiceValidationError on invalid modes."""
        if modes and mode in modes:
            return
        modes_str: str = ", ".join(modes) if modes else ""
        translation_key = f"not_valid_{mode_type}_mode"
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

    @final
    async def async_handle_set_hvac_mode_service(self, hvac_mode: HVACMode) -> None:
        """Validate and set new preset mode."""
        self._valid_mode_or_raise("hvac", hvac_mode, self.hvac_modes)
        await self.async_set_hvac_mode(hvac_mode)

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
    async def async_handle_set_swing_horizontal_mode_service(
        self, swing_horizontal_mode: str
    ) -> None:
        """Validate and set new horizontal swing mode."""
        self._valid_mode_or_raise(
            "horizontal_swing", swing_horizontal_mode, self.swing_horizontal_modes
        )
        await self.async_set_swing_horizontal_mode(swing_horizontal_mode)

    def set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new target horizontal swing operation."""
        raise NotImplementedError

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new target horizontal swing operation."""
        await self.hass.async_add_executor_job(
            self.set_swing_horizontal_mode, swing_horizontal_mode
        )

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
    @override
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return self._attr_supported_features

    @cached_property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if not hasattr(self, "_attr_min_temp"):
            return TemperatureConverter.convert(
                DEFAULT_MIN_TEMP,
                UnitOfTemperature.CELSIUS,
                self.native_temperature_unit,
            )
        return self._attr_min_temp

    @cached_property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if not hasattr(self, "_attr_max_temp"):
            return TemperatureConverter.convert(
                DEFAULT_MAX_TEMP,
                UnitOfTemperature.CELSIUS,
                self.native_temperature_unit,
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

    @cached_property
    def target_humidity_step(self) -> int | None:
        """Return the supported step of humidity."""
        return self._attr_target_humidity_step
