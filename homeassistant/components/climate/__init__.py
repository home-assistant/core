"""Provides functionality to interact with climate devices."""

from datetime import timedelta
import functools as ft
import logging
from operator import attrgetter
from types import MemberDescriptorType
from typing import Any, Literal, cast, final, override

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
from homeassistant.core import HomeAssistant, async_get_hass_or_none, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.frame import ReportBehavior, report_usage
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_suggest_report_issue
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


_DEPRECATED_TEMPERATURE_MEMBERS = (
    "current_temperature",
    "target_temperature",
    "target_temperature_high",
    "target_temperature_low",
    "temperature_unit",
)


def _log_deprecated_temperature_member(cls: type, member: str, usage: str) -> None:
    """Log use of a deprecated temperature member."""
    report_issue = async_suggest_report_issue(
        async_get_hass_or_none(), module=cls.__module__
    )
    _LOGGER.warning(
        (
            "%s::%s is %s, this will be unsupported from Home Assistant 2027.11, "
            "use ClimateEntity.native_%s instead, please %s"
        ),
        cls.__module__,
        cls.__name__,
        usage,
        member,
        report_issue,
    )


_REPORTED_DEPRECATED_MEMBERS: set[tuple[type, str]] = set()


def _report_deprecated_temperature_member(cls: type, member: str, usage: str) -> None:
    """Report a declaration or a write of a deprecated member, once per class.

    The reported classes are tracked here rather than on the class itself: a
    class attribute is inherited, so a subclass would be silenced by the report
    its parent already made.
    """
    if (key := (cls, usage)) in _REPORTED_DEPRECATED_MEMBERS:
        return
    _REPORTED_DEPRECATED_MEMBERS.add(key)
    _log_deprecated_temperature_member(cls, member, usage)


_REPORTED_DEPRECATED_READS: set[tuple[type, str]] = set()


def _report_deprecated_temperature_read(cls: type, member: str, usage: str) -> None:
    """Report a read of a deprecated temperature member, once per class.

    A read is attributed to the code doing it rather than to the entity's class: a
    proxy or a helper may read the deprecated member of an entity owned by another
    integration, which must not be blamed for it.
    """
    if (key := (cls, usage)) in _REPORTED_DEPRECATED_READS:
        return
    _REPORTED_DEPRECATED_READS.add(key)
    try:
        report_usage(
            f"is {usage}, use ClimateEntity.native_{member} instead",
            breaks_in_ha_version="2027.11",
            core_behavior=ReportBehavior.LOG,
            exclude_integrations={DOMAIN},
        )
    except RuntimeError:
        # The frame helper is only set up once Home Assistant runs; a read before
        # that can only be attributed to the entity's class.
        _log_deprecated_temperature_member(cls, member, usage)


def _read_deprecated_attr(entity: Any, member: str) -> Any:
    """Read the deprecated _attr_<member> a deprecated <member> is served from.

    Reading it off the entity would report the shim's own read, so the native storage
    it aliases is read directly, unless a subclass shadows the alias: that declaration
    is then the value the deprecated member serves.
    """
    attr_member = f"_attr_{member}"
    if getattr(type(entity), attr_member) is getattr(ClimateEntity, attr_member):
        return getattr(entity, f"_attr_native_{member}")
    return getattr(entity, attr_member)


class _DeprecatedFallback(property):
    """Marks a native_<member> installed by the shim instead of by a subclass.

    Reading it reaches back to the deprecated member, so a deprecated member looking
    for the native value must skip it and serve an authored native member instead.
    """


def _read_authored_native(native: Any, entity: Any) -> Any:
    """Read a native member authored by a subclass.

    It is read off the class which authored it rather than off the entity, because a
    fallback installed for a more derived class shadows it and would ask the
    deprecated member for the value it is being read for.
    """
    if (getter := getattr(type(native), "__get__", None)) is not None:
        return getter(native, entity, type(entity))
    return native


def _deprecated_fallback(member: str, declaration: Any) -> _DeprecatedFallback:
    """Build the native member serving a class which declares the deprecated one.

    It is bound to the declaration of that class instead of resolving <member> on the
    entity, so that it cannot bounce off the base class' deprecated member into a
    native member authored further up the MRO.
    """
    if declaration is None:
        # Only _attr_<member> is declared: read it off the entity, an assignment in
        # __init__ has to win over the class attribute.
        return _DeprecatedFallback(attrgetter(f"_attr_{member}"))
    if (getter := getattr(type(declaration), "__get__", None)) is None:
        # A plain class attribute, an instance attribute may shadow it.
        return _DeprecatedFallback(attrgetter(member))
    return _DeprecatedFallback(lambda entity: getter(declaration, entity, type(entity)))


def _link_deprecated_temperature_member(cls: type[ClimateEntity], member: str) -> None:
    """Let native_<member> fall back to a subclass still providing <member>.

    Nothing is moved or removed, the deprecated member keeps working exactly as it
    did. The whole MRO is inspected rather than only cls.__dict__, so that a member
    declared by a mixin which is not itself a ClimateEntity is picked up as well.

    Both links are resolved by MRO position, so that the most derived class wins:

    * The most derived class still declaring the deprecated member gets a fallback
      installed for native_<member>, bound to that class' own declaration. A native
      member authored further up the MRO no longer shadows it.
    * The nearest native member authored by a subclass is recorded for the deprecated
      member to serve, which is what lets a class that has migrated without ever
      assigning _attr_native_<member> keep answering reads of the deprecated name.
    """
    native_member = f"native_{member}"
    attr_member = f"_attr_{member}"
    native_attr_member = f"_attr_{native_member}"
    authored: tuple[Any] | None = None
    deprecated: tuple[type, str] | None = None
    declaration: Any = None
    settled = False

    for klass in cls.__mro__:
        if klass in (ClimateEntity, Entity, object):
            break
        namespace = klass.__dict__
        if native_member in namespace:
            if not isinstance(native := namespace[native_member], _DeprecatedFallback):
                # Authored by a subclass, it wins over anything further up.
                authored = (native,)
                break
            # A fallback installed for a more derived class already serves the
            # deprecated member, and is not a value it may be served from.
            settled = True
        elif native_attr_member in namespace:
            # The class has migrated, an ancestor's deprecated member is moot.
            settled = True
        elif member in namespace:
            if not settled:
                declaration = namespace[member]
                deprecated = (
                    klass,
                    f"declaring the deprecated {member} in __slots__"
                    if isinstance(declaration, MemberDescriptorType)
                    else f"overriding the deprecated {member} property",
                )
                settled = True
        elif attr_member in namespace:
            if not settled:
                deprecated = (
                    klass,
                    f"setting the deprecated {attr_member} class attribute",
                )
                settled = True
            # The deprecated storage shadows a native member authored further up.
            break

    setattr(cls, f"_{native_member}_authored", authored)

    if deprecated is None:
        return

    # Deliberately not a cached property: the deprecated member is free to return a
    # new value on every read.
    setattr(cls, native_member, _deprecated_fallback(member, declaration))
    _report_deprecated_temperature_member(deprecated[0], member, deprecated[1])


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

    _native_current_temperature_authored: tuple[Any] | None = None
    _native_target_temperature_authored: tuple[Any] | None = None
    _native_target_temperature_high_authored: tuple[Any] | None = None
    _native_target_temperature_low_authored: tuple[Any] | None = None
    _native_temperature_unit_authored: tuple[Any] | None = None

    @override
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Link the deprecated temperature API of a subclass to the native one."""
        super().__init_subclass__(**kwargs)

        for member in _DEPRECATED_TEMPERATURE_MEMBERS:
            _link_deprecated_temperature_member(cls, member)

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

    @final  # type: ignore[misc]  # mypy reads the getter/setter pair as overloads
    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement the entity reports temperatures in.

        Deprecated, use native_temperature_unit instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "temperature_unit",
            "reading the deprecated temperature_unit property",
        )
        if (authored := self._native_temperature_unit_authored) is not None:
            return cast(str, _read_authored_native(authored[0], self))
        return cast(str, _read_deprecated_attr(self, "temperature_unit"))

    @temperature_unit.setter
    def temperature_unit(self, value: str) -> None:
        """Set the native unit of measurement.

        Deprecated, use _attr_native_temperature_unit instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "temperature_unit",
            "setting the deprecated temperature_unit attribute",
        )
        self._attr_native_temperature_unit = value

    @final  # type: ignore[misc]  # mypy reads the getter/setter pair as overloads
    @property
    def _attr_temperature_unit(self) -> str:
        """Return the native unit of measurement.

        Deprecated, use _attr_native_temperature_unit instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "temperature_unit",
            "reading the deprecated _attr_temperature_unit attribute",
        )
        return self._attr_native_temperature_unit

    @_attr_temperature_unit.setter
    def _attr_temperature_unit(self, value: str) -> None:
        """Set the native unit of measurement.

        Deprecated, use _attr_native_temperature_unit instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "temperature_unit",
            "setting the deprecated _attr_temperature_unit attribute",
        )
        self._attr_native_temperature_unit = value

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

    @final  # type: ignore[misc]  # mypy reads the getter/setter pair as overloads
    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature in the native unit.

        Deprecated, use native_current_temperature instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "current_temperature",
            "reading the deprecated current_temperature property",
        )
        if (authored := self._native_current_temperature_authored) is not None:
            return cast(float | None, _read_authored_native(authored[0], self))
        return cast(float | None, _read_deprecated_attr(self, "current_temperature"))

    @current_temperature.setter
    def current_temperature(self, value: float | None) -> None:
        """Set the current temperature in the native unit.

        Deprecated, use _attr_native_current_temperature instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "current_temperature",
            "setting the deprecated current_temperature attribute",
        )
        self._attr_native_current_temperature = value

    @final  # type: ignore[misc]  # mypy reads the getter/setter pair as overloads
    @property
    def _attr_current_temperature(self) -> float | None:
        """Return the current temperature in the native unit.

        Deprecated, use _attr_native_current_temperature instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "current_temperature",
            "reading the deprecated _attr_current_temperature attribute",
        )
        return self._attr_native_current_temperature

    @_attr_current_temperature.setter
    def _attr_current_temperature(self, value: float | None) -> None:
        """Set the current temperature in the native unit.

        Deprecated, use _attr_native_current_temperature instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "current_temperature",
            "setting the deprecated _attr_current_temperature attribute",
        )
        self._attr_native_current_temperature = value

    @cached_property
    def native_target_temperature(self) -> float | None:
        """Return the temperature we try to reach, in the native unit."""
        return self._attr_native_target_temperature

    @final  # type: ignore[misc]  # mypy reads the getter/setter pair as overloads
    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach, in the native unit.

        Deprecated, use native_target_temperature instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "target_temperature",
            "reading the deprecated target_temperature property",
        )
        if (authored := self._native_target_temperature_authored) is not None:
            return cast(float | None, _read_authored_native(authored[0], self))
        return cast(float | None, _read_deprecated_attr(self, "target_temperature"))

    @target_temperature.setter
    def target_temperature(self, value: float | None) -> None:
        """Set the temperature we try to reach, in the native unit.

        Deprecated, use _attr_native_target_temperature instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "target_temperature",
            "setting the deprecated target_temperature attribute",
        )
        self._attr_native_target_temperature = value

    @final  # type: ignore[misc]  # mypy reads the getter/setter pair as overloads
    @property
    def _attr_target_temperature(self) -> float | None:
        """Return the temperature we try to reach, in the native unit.

        Deprecated, use _attr_native_target_temperature instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "target_temperature",
            "reading the deprecated _attr_target_temperature attribute",
        )
        return self._attr_native_target_temperature

    @_attr_target_temperature.setter
    def _attr_target_temperature(self, value: float | None) -> None:
        """Set the temperature we try to reach, in the native unit.

        Deprecated, use _attr_native_target_temperature instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "target_temperature",
            "setting the deprecated _attr_target_temperature attribute",
        )
        self._attr_native_target_temperature = value

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

    @final  # type: ignore[misc]  # mypy reads the getter/setter pair as overloads
    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach.

        Deprecated, use native_target_temperature_high instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "target_temperature_high",
            "reading the deprecated target_temperature_high property",
        )
        if (authored := self._native_target_temperature_high_authored) is not None:
            return cast(float | None, _read_authored_native(authored[0], self))
        return cast(
            float | None, _read_deprecated_attr(self, "target_temperature_high")
        )

    @target_temperature_high.setter
    def target_temperature_high(self, value: float | None) -> None:
        """Set the highbound target temperature we try to reach.

        Deprecated, use _attr_native_target_temperature_high instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "target_temperature_high",
            "setting the deprecated target_temperature_high attribute",
        )
        self._attr_native_target_temperature_high = value

    @final  # type: ignore[misc]  # mypy reads the getter/setter pair as overloads
    @property
    def _attr_target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach.

        Deprecated, use _attr_native_target_temperature_high instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "target_temperature_high",
            "reading the deprecated _attr_target_temperature_high attribute",
        )
        return self._attr_native_target_temperature_high

    @_attr_target_temperature_high.setter
    def _attr_target_temperature_high(self, value: float | None) -> None:
        """Set the highbound target temperature we try to reach.

        Deprecated, use _attr_native_target_temperature_high instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "target_temperature_high",
            "setting the deprecated _attr_target_temperature_high attribute",
        )
        self._attr_native_target_temperature_high = value

    @cached_property
    def native_target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach.

        In the native unit. Requires ClimateEntityFeature.TARGET_TEMPERATURE_RANGE.
        """
        return self._attr_native_target_temperature_low

    @final  # type: ignore[misc]  # mypy reads the getter/setter pair as overloads
    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach.

        Deprecated, use native_target_temperature_low instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "target_temperature_low",
            "reading the deprecated target_temperature_low property",
        )
        if (authored := self._native_target_temperature_low_authored) is not None:
            return cast(float | None, _read_authored_native(authored[0], self))
        return cast(float | None, _read_deprecated_attr(self, "target_temperature_low"))

    @target_temperature_low.setter
    def target_temperature_low(self, value: float | None) -> None:
        """Set the lowbound target temperature we try to reach.

        Deprecated, use _attr_native_target_temperature_low instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "target_temperature_low",
            "setting the deprecated target_temperature_low attribute",
        )
        self._attr_native_target_temperature_low = value

    @final  # type: ignore[misc]  # mypy reads the getter/setter pair as overloads
    @property
    def _attr_target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach.

        Deprecated, use _attr_native_target_temperature_low instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "target_temperature_low",
            "reading the deprecated _attr_target_temperature_low attribute",
        )
        return self._attr_native_target_temperature_low

    @_attr_target_temperature_low.setter
    def _attr_target_temperature_low(self, value: float | None) -> None:
        """Set the lowbound target temperature we try to reach.

        Deprecated, use _attr_native_target_temperature_low instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "target_temperature_low",
            "setting the deprecated _attr_target_temperature_low attribute",
        )
        self._attr_native_target_temperature_low = value

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
