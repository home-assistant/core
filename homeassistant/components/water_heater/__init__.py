"""Support for water heater devices."""

from datetime import timedelta
import functools as ft
import logging
from operator import attrgetter
from types import MemberDescriptorType
from typing import Any, cast, final, override

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry

# ATTR_TEMPERATURE, SERVICE_TURN_ON and SERVICE_TURN_OFF are re-exported for
# integrations importing them from the water_heater component root.
from homeassistant.const import (  # noqa: F401
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, async_get_hass_or_none
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
    ATTR_AWAY_MODE,
    ATTR_OPERATION_MODE,
    DATA_COMPONENT,
    DOMAIN,
    SERVICE_SET_AWAY_MODE,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    WaterHeaterCapabilityAttribute,
    WaterHeaterEntityFeature,
    WaterHeaterStateAttribute,
)
from .services import async_setup_services

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=60)

DEFAULT_MIN_TEMP = 110
DEFAULT_MAX_TEMP = 140


STATE_ECO = "eco"
STATE_ELECTRIC = "electric"
STATE_PERFORMANCE = "performance"
STATE_HIGH_DEMAND = "high_demand"
STATE_HEAT_PUMP = "heat_pump"
STATE_GAS = "gas"


ATTR_MAX_TEMP = "max_temp"
ATTR_MIN_TEMP = "min_temp"
ATTR_OPERATION_LIST = "operation_list"
ATTR_TARGET_TEMP_HIGH = "target_temp_high"
ATTR_TARGET_TEMP_LOW = "target_temp_low"
ATTR_TARGET_TEMP_STEP = "target_temp_step"
ATTR_CURRENT_TEMPERATURE = "current_temperature"


_LOGGER = logging.getLogger(__name__)


# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up water_heater devices."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[WaterHeaterEntity](
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


class WaterHeaterEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes water heater entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {
    "native_temperature_unit",
    "current_operation",
    "operation_list",
    "native_current_temperature",
    "native_target_temperature",
    "native_target_temperature_high",
    "native_target_temperature_low",
    "target_temperature_step",
    "is_away_mode_on",
}

_DEPRECATED_TEMPERATURE_MEMBERS = (
    "current_temperature",
    "target_temperature",
    "target_temperature_high",
    "target_temperature_low",
    "temperature_unit",
)


def _log_deprecated_temperature_member(cls: type, usage: str, replacement: str) -> None:
    """Log use of a deprecated temperature member."""
    report_issue = async_suggest_report_issue(
        async_get_hass_or_none(), module=cls.__module__
    )
    _LOGGER.warning(
        (
            "%s::%s is %s, this will be unsupported from Home Assistant 2027.11, "
            "use WaterHeaterEntity.%s instead, please %s"
        ),
        cls.__module__,
        cls.__name__,
        usage,
        replacement,
        report_issue,
    )


_REPORTED_DEPRECATED_MEMBERS: set[tuple[type, str]] = set()


def _report_deprecated_temperature_member(
    cls: type, usage: str, replacement: str
) -> None:
    """Report a declaration or a write of a deprecated member, once per class.

    The reported classes are tracked here rather than on the class itself: a
    class attribute is inherited, so a subclass would be silenced by the report
    its parent already made.
    """
    if (key := (cls, usage)) in _REPORTED_DEPRECATED_MEMBERS:
        return
    _REPORTED_DEPRECATED_MEMBERS.add(key)
    _log_deprecated_temperature_member(cls, usage, replacement)


_REPORTED_DEPRECATED_READS: set[tuple[type, str]] = set()


def _report_deprecated_temperature_read(
    cls: type, usage: str, replacement: str
) -> None:
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
            f"is {usage}, use WaterHeaterEntity.{replacement} instead",
            breaks_in_ha_version="2027.11",
            core_behavior=ReportBehavior.LOG,
            exclude_integrations={DOMAIN},
        )
    except RuntimeError:
        # The frame helper is only set up once Home Assistant runs; a read before
        # that can only be attributed to the entity's class.
        _log_deprecated_temperature_member(cls, usage, replacement)


def _read_deprecated_attr(entity: Any, member: str) -> Any:
    """Read the deprecated _attr_<member> a deprecated <member> is served from.

    Reading it off the entity would report the shim's own read, so the native storage
    it aliases is read directly, unless a subclass shadows the alias: that declaration
    is then the value the deprecated member serves.
    """
    attr_member = f"_attr_{member}"
    if getattr(type(entity), attr_member) is getattr(WaterHeaterEntity, attr_member):
        return getattr(entity, f"_attr_native_{member}")
    return getattr(entity, attr_member)


class _DeprecatedFallback(property):
    """Marks a native_<member> installed by the shim instead of by a subclass.

    Reading it reaches back to the deprecated member, so a deprecated member looking
    for the native value must skip it and serve an authored native member instead.
    """


class _DeprecatedAttrFallback(_DeprecatedFallback):
    """Marks a fallback serving a deprecated _attr_<member> class attribute."""


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
        return _DeprecatedAttrFallback(attrgetter(f"_attr_{member}"))
    if (getter := getattr(type(declaration), "__get__", None)) is None:
        # A plain class attribute, an instance attribute may shadow it.
        return _DeprecatedFallback(attrgetter(member))
    return _DeprecatedFallback(lambda entity: getter(declaration, entity, type(entity)))


def _resolve(cls: type, name: str) -> Any:
    """Return the raw class member name resolves to, without invoking descriptors."""
    return next(vars(klass)[name] for klass in cls.__mro__ if name in vars(klass))


def _link_deprecated_temperature_member(
    cls: type[WaterHeaterEntity], member: str
) -> None:
    """Let native_<member> fall back to a subclass still providing <member>.

    Nothing is moved or removed, the deprecated member keeps working exactly as it
    did. The whole MRO is inspected rather than only cls.__dict__, so that a member
    declared by a mixin which is not itself a WaterHeaterEntity is picked up as well.

    Both links are resolved by MRO position, so that the most derived class wins:

    * The most derived class still declaring the deprecated member gets a fallback
      installed for native_<member>, bound to that class' own declaration. A native
      member authored further up the MRO no longer shadows it.
    * The nearest native member authored by a subclass is recorded for the deprecated
      member to serve, which is what lets a class that has migrated without ever
      assigning _attr_native_<member> keep answering reads of the deprecated name.
    * A class setting _attr_native_<member> below an ancestor's deprecated
      _attr_<member> gets the base native_<member> back, so its own value is served.
    """
    native_member = f"native_{member}"
    attr_member = f"_attr_{member}"
    native_attr_member = f"_attr_{native_member}"
    authored: tuple[Any] | None = None
    deprecated: tuple[type, str, str] | None = None
    declaration: Any = None
    migrated = False
    settled = False

    for klass in cls.__mro__:
        if klass in (WaterHeaterEntity, Entity, object):
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
            migrated = migrated or not settled
            settled = True
        elif member in namespace:
            if not settled:
                declaration = namespace[member]
                deprecated = (
                    (
                        klass,
                        f"declaring the deprecated {member} in __slots__",
                        native_attr_member,
                    )
                    if isinstance(declaration, MemberDescriptorType)
                    else (
                        klass,
                        f"overriding the deprecated {member} property",
                        native_member,
                    )
                )
                settled = True
        elif attr_member in namespace:
            if not settled:
                deprecated = (
                    klass,
                    f"setting the deprecated {attr_member} class attribute",
                    native_attr_member,
                )
                settled = True
            # The deprecated storage shadows a native member authored further up.
            break

    if migrated and isinstance(_resolve(cls, native_member), _DeprecatedAttrFallback):
        # The class has migrated the storage an inherited fallback serves, so its own
        # _attr_native_<member> has to be served instead.
        authored = (native := vars(WaterHeaterEntity)[native_member],)
        setattr(cls, native_member, native)

    setattr(cls, f"_{native_member}_authored", authored)

    if deprecated is None:
        return

    # Deliberately not a cached property: the deprecated member is free to return a
    # new value on every read.
    setattr(cls, native_member, _deprecated_fallback(member, declaration))
    _report_deprecated_temperature_member(*deprecated)


class WaterHeaterEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for water heater entities."""

    _entity_component_unrecorded_attributes = frozenset(
        {
            WaterHeaterCapabilityAttribute.OPERATION_LIST,
            WaterHeaterCapabilityAttribute.MIN_TEMP,
            WaterHeaterCapabilityAttribute.MAX_TEMP,
            WaterHeaterCapabilityAttribute.TARGET_TEMP_STEP,
        }
    )

    entity_description: WaterHeaterEntityDescription
    _attr_current_operation: str | None = None
    _attr_is_away_mode_on: bool | None = None
    _attr_max_temp: float
    _attr_min_temp: float
    _attr_native_current_temperature: float | None = None
    _attr_native_target_temperature_high: float | None = None
    _attr_native_target_temperature_low: float | None = None
    _attr_native_target_temperature: float | None = None
    _attr_native_temperature_unit: str
    _attr_operation_list: list[str] | None = None
    _attr_precision: float
    _attr_state: None = None
    _attr_supported_features: WaterHeaterEntityFeature = WaterHeaterEntityFeature(0)
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
        return self.current_operation

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
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        native_temperature_unit = self.native_temperature_unit
        data: dict[str, Any] = {
            WaterHeaterCapabilityAttribute.MIN_TEMP: show_temp(
                self.hass, self.min_temp, native_temperature_unit, self.precision
            ),
            WaterHeaterCapabilityAttribute.MAX_TEMP: show_temp(
                self.hass, self.max_temp, native_temperature_unit, self.precision
            ),
        }
        if target_temperature_step := self.target_temperature_step:
            data[WaterHeaterCapabilityAttribute.TARGET_TEMP_STEP] = (
                target_temperature_step
            )

        if WaterHeaterEntityFeature.OPERATION_MODE in self.supported_features:
            data[WaterHeaterCapabilityAttribute.OPERATION_LIST] = self.operation_list

        return data

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        native_temperature_unit = self.native_temperature_unit
        data: dict[str, Any] = {
            WaterHeaterStateAttribute.CURRENT_TEMPERATURE: show_temp(
                self.hass,
                self.native_current_temperature,
                native_temperature_unit,
                self.precision,
            ),
            WaterHeaterStateAttribute.TARGET_TEMPERATURE: show_temp(
                self.hass,
                self.native_target_temperature,
                native_temperature_unit,
                self.precision,
            ),
            WaterHeaterStateAttribute.TARGET_TEMP_HIGH: show_temp(
                self.hass,
                self.native_target_temperature_high,
                native_temperature_unit,
                self.precision,
            ),
            WaterHeaterStateAttribute.TARGET_TEMP_LOW: show_temp(
                self.hass,
                self.native_target_temperature_low,
                native_temperature_unit,
                self.precision,
            ),
            WaterHeaterStateAttribute.TEMPERATURE_UNIT: (
                self.hass.config.units.temperature_unit
            ),
        }

        supported_features = self.supported_features

        if WaterHeaterEntityFeature.OPERATION_MODE in supported_features:
            data[WaterHeaterStateAttribute.OPERATION_MODE] = self.current_operation

        if WaterHeaterEntityFeature.AWAY_MODE in supported_features:
            is_away = self.is_away_mode_on
            data[WaterHeaterStateAttribute.AWAY_MODE] = (
                STATE_ON if is_away else STATE_OFF
            )

        return data

    @cached_property
    def native_temperature_unit(self) -> str:
        """Return the unit of measurement the entity reports temperatures in."""
        return self._attr_native_temperature_unit

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement the entity reports temperatures in.

        Deprecated, use native_temperature_unit instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "reading the deprecated temperature_unit property",
            "native_temperature_unit",
        )
        if (authored := self._native_temperature_unit_authored) is not None:
            return cast(str, _read_authored_native(authored[0], self))
        return cast(str, _read_deprecated_attr(self, "temperature_unit"))

    @property
    def _attr_temperature_unit(self) -> str:
        """Return the native unit of measurement.

        Deprecated, use _attr_native_temperature_unit instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "reading the deprecated _attr_temperature_unit attribute",
            "native_temperature_unit",
        )
        return self._attr_native_temperature_unit

    @_attr_temperature_unit.setter
    def _attr_temperature_unit(self, value: str) -> None:
        """Set the native unit of measurement.

        Deprecated, use _attr_native_temperature_unit instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "setting the deprecated _attr_temperature_unit attribute",
            "_attr_native_temperature_unit",
        )
        self._attr_native_temperature_unit = value

    @cached_property
    def current_operation(self) -> str | None:
        """Return current operation ie. eco, electric, performance, ..."""
        return self._attr_current_operation

    @cached_property
    def operation_list(self) -> list[str] | None:
        """Return the list of available operation modes."""
        return self._attr_operation_list

    @cached_property
    def native_current_temperature(self) -> float | None:
        """Return the current temperature in the native unit."""
        return self._attr_native_current_temperature

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature in the native unit.

        Deprecated, use native_current_temperature instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "reading the deprecated current_temperature property",
            "native_current_temperature",
        )
        if (authored := self._native_current_temperature_authored) is not None:
            return cast(float | None, _read_authored_native(authored[0], self))
        return cast(float | None, _read_deprecated_attr(self, "current_temperature"))

    @property
    def _attr_current_temperature(self) -> float | None:
        """Return the current temperature in the native unit.

        Deprecated, use _attr_native_current_temperature instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "reading the deprecated _attr_current_temperature attribute",
            "native_current_temperature",
        )
        return self._attr_native_current_temperature

    @_attr_current_temperature.setter
    def _attr_current_temperature(self, value: float | None) -> None:
        """Set the current temperature in the native unit.

        Deprecated, use _attr_native_current_temperature instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "setting the deprecated _attr_current_temperature attribute",
            "_attr_native_current_temperature",
        )
        self._attr_native_current_temperature = value

    @cached_property
    def native_target_temperature(self) -> float | None:
        """Return the temperature we try to reach, in the native unit."""
        return self._attr_native_target_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach, in the native unit.

        Deprecated, use native_target_temperature instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "reading the deprecated target_temperature property",
            "native_target_temperature",
        )
        if (authored := self._native_target_temperature_authored) is not None:
            return cast(float | None, _read_authored_native(authored[0], self))
        return cast(float | None, _read_deprecated_attr(self, "target_temperature"))

    @property
    def _attr_target_temperature(self) -> float | None:
        """Return the temperature we try to reach, in the native unit.

        Deprecated, use _attr_native_target_temperature instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "reading the deprecated _attr_target_temperature attribute",
            "native_target_temperature",
        )
        return self._attr_native_target_temperature

    @_attr_target_temperature.setter
    def _attr_target_temperature(self, value: float | None) -> None:
        """Set the temperature we try to reach, in the native unit.

        Deprecated, use _attr_native_target_temperature instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "setting the deprecated _attr_target_temperature attribute",
            "_attr_native_target_temperature",
        )
        self._attr_native_target_temperature = value

    @cached_property
    def native_target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach.

        In the native unit.
        """
        return self._attr_native_target_temperature_high

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach.

        Deprecated, use native_target_temperature_high instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "reading the deprecated target_temperature_high property",
            "native_target_temperature_high",
        )
        if (authored := self._native_target_temperature_high_authored) is not None:
            return cast(float | None, _read_authored_native(authored[0], self))
        return cast(
            float | None, _read_deprecated_attr(self, "target_temperature_high")
        )

    @property
    def _attr_target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach.

        Deprecated, use _attr_native_target_temperature_high instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "reading the deprecated _attr_target_temperature_high attribute",
            "native_target_temperature_high",
        )
        return self._attr_native_target_temperature_high

    @_attr_target_temperature_high.setter
    def _attr_target_temperature_high(self, value: float | None) -> None:
        """Set the highbound target temperature we try to reach.

        Deprecated, use _attr_native_target_temperature_high instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "setting the deprecated _attr_target_temperature_high attribute",
            "_attr_native_target_temperature_high",
        )
        self._attr_native_target_temperature_high = value

    @cached_property
    def native_target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach.

        In the native unit.
        """
        return self._attr_native_target_temperature_low

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach.

        Deprecated, use native_target_temperature_low instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "reading the deprecated target_temperature_low property",
            "native_target_temperature_low",
        )
        if (authored := self._native_target_temperature_low_authored) is not None:
            return cast(float | None, _read_authored_native(authored[0], self))
        return cast(float | None, _read_deprecated_attr(self, "target_temperature_low"))

    @property
    def _attr_target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach.

        Deprecated, use _attr_native_target_temperature_low instead.
        """
        _report_deprecated_temperature_read(
            type(self),
            "reading the deprecated _attr_target_temperature_low attribute",
            "native_target_temperature_low",
        )
        return self._attr_native_target_temperature_low

    @_attr_target_temperature_low.setter
    def _attr_target_temperature_low(self, value: float | None) -> None:
        """Set the lowbound target temperature we try to reach.

        Deprecated, use _attr_native_target_temperature_low instead.
        """
        _report_deprecated_temperature_member(
            type(self),
            "setting the deprecated _attr_target_temperature_low attribute",
            "_attr_native_target_temperature_low",
        )
        self._attr_native_target_temperature_low = value

    @cached_property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return self._attr_target_temperature_step

    @cached_property
    def is_away_mode_on(self) -> bool | None:
        """Return true if away mode is on."""
        return self._attr_is_away_mode_on

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        raise NotImplementedError

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self.hass.async_add_executor_job(
            ft.partial(self.set_temperature, **kwargs)
        )

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater on."""
        raise NotImplementedError

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater on."""
        await self.hass.async_add_executor_job(ft.partial(self.turn_on, **kwargs))

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        raise NotImplementedError

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        await self.hass.async_add_executor_job(ft.partial(self.turn_off, **kwargs))

    def set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        raise NotImplementedError

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        await self.hass.async_add_executor_job(self.set_operation_mode, operation_mode)

    @final
    async def async_handle_set_operation_mode(self, operation_mode: str) -> None:
        """Handle a set target operation mode service call."""
        if self.operation_list is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="operation_list_not_defined",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "operation_mode": operation_mode,
                },
            )
        if operation_mode not in self.operation_list:
            operation_list = ", ".join(self.operation_list)
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_valid_operation_mode",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "operation_mode": operation_mode,
                    "operation_list": operation_list,
                },
            )
        await self.async_set_operation_mode(operation_mode)

    def turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        raise NotImplementedError

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        await self.hass.async_add_executor_job(self.turn_away_mode_on)

    def turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        raise NotImplementedError

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        await self.hass.async_add_executor_job(self.turn_away_mode_off)

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if hasattr(self, "_attr_min_temp"):
            return self._attr_min_temp
        return TemperatureConverter.convert(
            DEFAULT_MIN_TEMP,
            UnitOfTemperature.FAHRENHEIT,
            self.native_temperature_unit,
        )

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if hasattr(self, "_attr_max_temp"):
            return self._attr_max_temp
        return TemperatureConverter.convert(
            DEFAULT_MAX_TEMP,
            UnitOfTemperature.FAHRENHEIT,
            self.native_temperature_unit,
        )

    @property
    @override
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Return the list of supported features."""
        return self._attr_supported_features
