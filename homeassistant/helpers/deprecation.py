"""Deprecation helpers for Home Assistant."""

from collections.abc import Callable
from contextlib import suppress
from enum import EnumType, IntEnum, IntFlag, StrEnum, _EnumDict
import functools
import inspect
import logging
from typing import TYPE_CHECKING, Any, NamedTuple, cast, override

from propcache.api import cached_property

if TYPE_CHECKING:
    from .frame import ReportBehavior


def deprecated_substitute[_ObjectT: object](
    substitute_name: str,
) -> Callable[[Callable[[_ObjectT], Any]], Callable[[_ObjectT], Any]]:
    """Help migrate properties to new names.

    When a property is added to replace an older property, this decorator can
    be added to the new property, listing the old property as the substitute.
    If the old property is defined, its value will be used instead, and a log
    warning will be issued alerting the user of the impending change.
    """

    def decorator(func: Callable[[_ObjectT], Any]) -> Callable[[_ObjectT], Any]:
        """Decorate function as deprecated."""

        def func_wrapper(self: _ObjectT) -> Any:
            """Wrap for the original function."""
            if hasattr(self, substitute_name):
                # If this platform is still using the old property, issue
                # a logger warning once with instructions on how to fix it.
                warnings = getattr(func, "_deprecated_substitute_warnings", {})
                module_name = self.__module__
                if not warnings.get(module_name):
                    logger = logging.getLogger(module_name)
                    logger.warning(
                        (
                            "'%s' is deprecated. Please rename '%s' to "
                            "'%s' in '%s' to ensure future support."
                        ),
                        substitute_name,
                        substitute_name,
                        func.__name__,
                        inspect.getfile(self.__class__),
                    )
                    warnings[module_name] = True
                    setattr(func, "_deprecated_substitute_warnings", warnings)  # noqa: B010

                # Return the old property
                return getattr(self, substitute_name)
            return func(self)

        return func_wrapper

    return decorator


def get_deprecated(
    config: dict[str, Any], new_name: str, old_name: str, default: Any | None = None
) -> Any | None:
    """Allow an old config name to be deprecated with a replacement.

    If the new config isn't found, but the old one is, the old value is used
    and a warning is issued to the user.
    """
    if old_name in config:
        module = inspect.getmodule(inspect.stack(context=0)[1].frame)
        if module is not None:
            module_name = module.__name__
        else:
            # If Python is unable to access the sources files, the call stack frame
            # will be missing information, so let's guard.
            # https://github.com/home-assistant/core/issues/24982
            module_name = __name__

        logger = logging.getLogger(module_name)
        logger.warning(
            (
                "'%s' is deprecated. Please rename '%s' to '%s' in your "
                "configuration file."
            ),
            old_name,
            old_name,
            new_name,
        )
        return config.get(old_name)
    return config.get(new_name, default)


def deprecated_class[_T](
    replacement: str, *, breaks_in_ha_version: str | None = None
) -> Callable[[type[_T]], type[_T]]:
    """Mark class as deprecated and provide a replacement class to be used instead.

    If the deprecated function was called from a custom integration, ask the user to
    report an issue.
    """

    def deprecated_decorator(cls: type[_T]) -> type[_T]:
        """Decorate class as deprecated."""
        base_meta = type(cls)

        def __call__(self: type[Any], *args: Any, **kwargs: Any) -> Any:
            _print_deprecation_warning(
                cls, replacement, "class", "instantiated", breaks_in_ha_version
            )
            return base_meta.__call__(self, *args, **kwargs)

        deprecated_meta = type(
            f"Deprecated{base_meta.__name__}",
            (base_meta,),
            {"__call__": __call__},
        )

        deprecated_cls = deprecated_meta(
            cls.__name__,
            (cls,),
            {
                "__module__": cls.__module__,
                "__qualname__": cls.__qualname__,
                "__doc__": cls.__doc__,
                "__slots__": (),
                "__wrapped__": cls,
            },
        )

        return cast(type[_T], deprecated_cls)

    return deprecated_decorator


def deprecated_function[**_P, _R](
    replacement: str, *, breaks_in_ha_version: str | None = None
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Mark function as deprecated and provide a replacement to be used instead.

    If the deprecated function was called from a custom integration, ask the user to
    report an issue.
    """

    def deprecated_decorator(func: Callable[_P, _R]) -> Callable[_P, _R]:
        """Decorate function as deprecated."""

        @functools.wraps(func)
        def deprecated_func(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            """Wrap for the original function."""
            _print_deprecation_warning(
                func, replacement, "function", "called", breaks_in_ha_version
            )
            return func(*args, **kwargs)

        return deprecated_func

    return deprecated_decorator


def deprecated_hass_argument[**_P, _T](
    breaks_in_ha_version: str | None = None,
) -> Callable[[Callable[_P, _T]], Callable[_P, _T]]:
    """Decorate function to indicate that first argument hass will be ignored."""

    def _decorator(func: Callable[_P, _T]) -> Callable[_P, _T]:
        @functools.wraps(func)
        def _inner(*args: _P.args, **kwargs: _P.kwargs) -> _T:
            from homeassistant.core import HomeAssistant  # noqa: PLC0415

            in_arg = len(args) > 0 and isinstance(args[0], HomeAssistant)
            in_kwarg = "hass" in kwargs and isinstance(kwargs["hass"], HomeAssistant)

            if in_arg or in_kwarg:
                _print_deprecation_warning_internal(
                    "hass",
                    func.__module__,
                    f"{func.__name__} without hass argument",
                    "argument",
                    f"passed to {func.__name__}",
                    breaks_in_ha_version,
                    log_when_no_integration_is_found=True,
                )
                if in_arg:
                    args = args[1:]  # type: ignore[assignment]
                if in_kwarg:
                    kwargs.pop("hass")

            return func(*args, **kwargs)

        return _inner

    return _decorator


def _print_deprecation_warning(
    obj: Any,
    replacement: str,
    description: str,
    verb: str,
    breaks_in_ha_version: str | None,
) -> None:
    _print_deprecation_warning_internal(
        obj.__name__,
        obj.__module__,
        replacement,
        description,
        verb,
        breaks_in_ha_version,
        log_when_no_integration_is_found=True,
    )


def _print_deprecation_warning_internal(
    obj_name: str,
    module_name: str,
    replacement: str,
    description: str,
    verb: str,
    breaks_in_ha_version: str | None,
    *,
    log_when_no_integration_is_found: bool,
) -> None:
    # Suppress ImportError due to use of deprecated enum in core.py
    # Can be removed in HA Core 2025.1
    with suppress(ImportError):
        _print_deprecation_warning_internal_impl(
            obj_name,
            module_name,
            replacement,
            description,
            verb,
            breaks_in_ha_version,
            log_when_no_integration_is_found=log_when_no_integration_is_found,
        )


def _print_deprecation_warning_internal_impl(
    obj_name: str,
    module_name: str,
    replacement: str,
    description: str,
    verb: str,
    breaks_in_ha_version: str | None,
    *,
    log_when_no_integration_is_found: bool,
) -> None:
    from homeassistant.core import async_get_hass_or_none  # noqa: PLC0415
    from homeassistant.loader import async_suggest_report_issue  # noqa: PLC0415

    from .frame import MissingIntegrationFrame, get_integration_frame  # noqa: PLC0415

    logger = logging.getLogger(module_name)
    if breaks_in_ha_version:
        breaks_in = f" It will be removed in HA Core {breaks_in_ha_version}."
    else:
        breaks_in = ""
    try:
        integration_frame = get_integration_frame()
    except MissingIntegrationFrame:
        if log_when_no_integration_is_found:
            logger.warning(
                "The deprecated %s %s was %s.%s Use %s instead",
                description,
                obj_name,
                verb,
                breaks_in,
                replacement,
            )
    else:
        if integration_frame.custom_integration:
            report_issue = async_suggest_report_issue(
                async_get_hass_or_none(),
                integration_domain=integration_frame.integration,
                module=integration_frame.module,
            )
            logger.warning(
                ("The deprecated %s %s was %s from %s.%s Use %s instead, please %s"),
                description,
                obj_name,
                verb,
                integration_frame.integration,
                breaks_in,
                replacement,
                report_issue,
            )
        else:
            logger.warning(
                "The deprecated %s %s was %s from %s.%s Use %s instead",
                description,
                obj_name,
                verb,
                integration_frame.integration,
                breaks_in,
                replacement,
            )


class DeprecatedConstant[T](NamedTuple):
    """Deprecated constant."""

    value: T
    replacement: str
    breaks_in_ha_version: str | None


class DeprecatedConstantEnum[T: (StrEnum | IntEnum | IntFlag)](NamedTuple):
    """Deprecated constant."""

    enum: T
    breaks_in_ha_version: str | None


class DeprecatedAlias[T](NamedTuple):
    """Deprecated alias."""

    value: T
    replacement: str
    breaks_in_ha_version: str | None


class DeferredDeprecatedAlias[T]:
    """Deprecated alias with deferred evaluation of the value."""

    def __init__(
        self,
        value_fn: Callable[[], T],
        replacement: str,
        breaks_in_ha_version: str | None,
    ) -> None:
        """Initialize."""
        self.breaks_in_ha_version = breaks_in_ha_version
        self.replacement = replacement
        self._value_fn = value_fn

    @functools.cached_property
    def value(self) -> T:
        """Return the value."""
        return self._value_fn()


_PREFIX_DEPRECATED = "_DEPRECATED_"


def check_if_deprecated_constant(name: str, module_globals: dict[str, Any]) -> Any:
    """Check if the not found name is a deprecated constant.

    If it is, print a deprecation warning and return the value of the constant.
    Otherwise raise AttributeError.
    """
    module_name = module_globals.get("__name__")
    value = replacement = None
    description = "constant"
    if (deprecated_const := module_globals.get(_PREFIX_DEPRECATED + name)) is None:
        raise AttributeError(f"Module {module_name!r} has no attribute {name!r}")
    if isinstance(deprecated_const, DeprecatedConstant):
        value = deprecated_const.value
        replacement = deprecated_const.replacement
        breaks_in_ha_version = deprecated_const.breaks_in_ha_version
    elif isinstance(deprecated_const, DeprecatedConstantEnum):
        value = deprecated_const.enum
        replacement = (
            f"{deprecated_const.enum.__class__.__name__}.{deprecated_const.enum.name}"
        )
        breaks_in_ha_version = deprecated_const.breaks_in_ha_version
    elif isinstance(deprecated_const, (DeprecatedAlias, DeferredDeprecatedAlias)):
        description = "alias"
        value = deprecated_const.value
        replacement = deprecated_const.replacement
        breaks_in_ha_version = deprecated_const.breaks_in_ha_version

    if value is None or replacement is None:
        msg = (
            f"Value of {_PREFIX_DEPRECATED}{name} is an instance of "
            f"{type(deprecated_const)} but an instance of DeprecatedAlias, "
            "DeferredDeprecatedAlias, DeprecatedConstant or DeprecatedConstantEnum "
            "is required"
        )

        logging.getLogger(module_name).debug(msg)
        # PEP 562 -- Module __getattr__ and __dir__
        # specifies that __getattr__ should raise AttributeError if the attribute is not
        # found.
        # https://peps.python.org/pep-0562/#specification
        raise AttributeError(msg)

    _print_deprecation_warning_internal(
        name,
        module_name or __name__,
        replacement,
        description,
        "used",
        breaks_in_ha_version,
        log_when_no_integration_is_found=False,
    )
    return value


def dir_with_deprecated_constants(module_globals_keys: list[str]) -> list[str]:
    """Return dir() with deprecated constants."""
    return module_globals_keys + [
        name.removeprefix(_PREFIX_DEPRECATED)
        for name in module_globals_keys
        if name.startswith(_PREFIX_DEPRECATED)
    ]


def all_with_deprecated_constants(module_globals: dict[str, Any]) -> list[str]:
    """Generate a list for __all___ with deprecated constants."""
    # Iterate over a copy in case the globals dict is mutated by another thread
    # while we loop over it.
    module_globals_keys = list(module_globals)
    return [itm for itm in module_globals_keys if not itm.startswith("_")] + [
        name.removeprefix(_PREFIX_DEPRECATED)
        for name in module_globals_keys
        if name.startswith(_PREFIX_DEPRECATED)
    ]


class EnumWithDeprecatedMembers(EnumType):
    """Enum with deprecated members."""

    def __new__(
        mcs,
        cls: str,
        bases: tuple[type, ...],
        classdict: _EnumDict,
        *,
        deprecated: dict[str, tuple[str, str]],
        **kwds: Any,
    ) -> Any:
        """Create a new class."""
        classdict["__deprecated__"] = deprecated
        return super().__new__(mcs, cls, bases, classdict, **kwds)

    @override
    def __getattribute__(cls, name: str) -> Any:
        """Warn if accessing a deprecated member."""
        deprecated = super().__getattribute__("__deprecated__")
        if name in deprecated:
            _print_deprecation_warning_internal(
                f"{cls.__name__}.{name}",
                cls.__module__,
                f"{deprecated[name][0]}",
                "enum member",
                "used",
                deprecated[name][1],
                log_when_no_integration_is_found=False,
            )
        return super().__getattribute__(name)


class DeprecatedEntityAlias[_T]:
    """Deprecated name of an entity member, forwarding to its replacement.

    Declare it on the entity base class for both the property and its _attr_
    shorthand, and call migrate_deprecated_entity_members from the base class'
    __init_subclass__ to serve subclasses which still provide the deprecated name.

    core_integration_behavior applies to core integrations providing or using the
    deprecated name, it defaults to ReportBehavior.LOG.
    """

    def __init__(
        self,
        replacement: str,
        breaks_in_ha_version: str,
        *,
        core_integration_behavior: ReportBehavior | None = None,
    ) -> None:
        """Initialize the alias."""
        from .frame import ReportBehavior  # noqa: PLC0415

        self.replacement = replacement
        self.breaks_in_ha_version = breaks_in_ha_version
        self.core_integration_behavior = core_integration_behavior or ReportBehavior.LOG
        self.name = ""
        self.domain = ""

    def __set_name__(self, owner: type, name: str) -> None:
        """Store the deprecated name and the domain of the entity base class."""
        self.name = name
        self.domain = owner.__module__.rpartition(".")[2]

    def __get__(self, instance: object | None, owner: type | None = None) -> Any:
        """Read the replacement."""
        if instance is None:
            return self
        self._report_usage(instance, "reads")
        cls = type(instance)
        if not isinstance(
            inspect.getattr_static(cls, self.replacement), _DeprecatedEntityFallback
        ):
            return getattr(instance, self.replacement)
        # A subclass providing the deprecated name reached it through super(), serve
        # the replacement its fallback shadows instead of bouncing back to it
        for klass in cls.__mro__:
            target = vars(klass).get(self.replacement, _MISSING)
            if target is _MISSING or isinstance(target, _DeprecatedEntityFallback):
                continue
            if isinstance(target, cached_property):
                # Don't cache under the name the fallback serves
                return target.func(instance)
            if (getter := getattr(type(target), "__get__", None)) is not None:
                return getter(target, instance, cls)
            return target
        raise AttributeError(self.replacement)

    def __set__(self, instance: object, value: _T) -> None:
        """Write the storage of the replacement."""
        self._report_usage(instance, "writes")
        if self.replacement.startswith("_attr_"):
            setattr(instance, self.replacement, value)
        else:
            # Writing a cached property would only shadow it, write its storage
            setattr(instance, f"_attr_{self.replacement}", value)

    def _report_usage(self, instance: object, action: str) -> None:
        from . import frame  # noqa: PLC0415

        cls = type(instance)
        what = (
            f"{action} the deprecated {cls.__name__}.{self.name}, "
            f"use {self.replacement} instead"
        )
        try:
            frame.get_integration_frame(exclude_integrations={self.domain})
        except frame.MissingIntegrationFrame:
            pass
        else:
            # report_usage raises before the frame helper is set up; checked here
            # because it also raises RuntimeError for ReportBehavior.ERROR
            if frame._hass.hass is not None:  # noqa: SLF001
                frame.report_usage(
                    what,
                    breaks_in_ha_version=self.breaks_in_ha_version,
                    core_integration_behavior=self.core_integration_behavior,
                    exclude_integrations={self.domain},
                )
                return
        # Outside an integration, or before the frame helper is set up,
        # report_usage can't report once per call site, report once per class
        if (key := (cls, self.name, action)) in _REPORTED_DEPRECATED_ENTITY_USAGE:
            return
        _REPORTED_DEPRECATED_ENTITY_USAGE.add(key)
        logging.getLogger(cls.__module__).warning(
            "Detected code that %s. This will stop working in Home Assistant %s",
            what,
            self.breaks_in_ha_version,
        )


_REPORTED_DEPRECATED_ENTITY_USAGE: set[tuple[type, str, str]] = set()
_MISSING = object()


class _DeprecatedEntityFallback:
    """Replacement serving a subclass which still provides the deprecated name."""

    def __init__(self, name: str) -> None:
        """Initialize the fallback."""
        self.name = name

    def __get__(self, instance: object | None, owner: type | None = None) -> Any:
        """Read the deprecated name the subclass provides."""
        if instance is None:
            return self
        return getattr(instance, self.name)


def migrate_deprecated_entity_members(cls: type, base: type) -> None:
    """Serve the replacements of base's deprecated members from what cls provides.

    Must be called from base.__init_subclass__, which runs before the
    CachedProperties metaclass wraps the _attr_ class attributes of cls.
    """
    from homeassistant.core import async_get_hass_or_none  # noqa: PLC0415
    from homeassistant.loader import async_suggest_report_issue  # noqa: PLC0415

    from .frame import ReportBehavior  # noqa: PLC0415

    for name, alias in vars(base).items():
        if not isinstance(alias, DeprecatedEntityAlias):
            continue
        # The most derived class providing either name wins
        provider = next(
            klass
            for klass in cls.__mro__
            if name in vars(klass) or alias.replacement in vars(klass)
        )
        if provider is base or alias.replacement in vars(provider):
            continue
        if name.startswith("_attr_"):
            # Move the value to the replacement, which the metaclass wraps as
            # storage, and restore the alias so later writes reach it
            setattr(cls, alias.replacement, inspect.getattr_static(cls, name))
            setattr(cls, name, alias)
        else:
            setattr(cls, alias.replacement, _DeprecatedEntityFallback(name))
        behavior = ReportBehavior.LOG
        if cls.__module__.startswith("homeassistant.components."):
            behavior = alias.core_integration_behavior
        if behavior is ReportBehavior.IGNORE:
            continue
        message = (
            f"{cls.__module__}::{cls.__qualname__} provides the deprecated {name}, "
            f"this will stop working in Home Assistant {alias.breaks_in_ha_version}, "
            f"use {alias.replacement} instead"
        )
        if behavior is ReportBehavior.ERROR:
            raise RuntimeError(message)
        logging.getLogger(cls.__module__).warning(
            "%s, please %s",
            message,
            async_suggest_report_issue(async_get_hass_or_none(), module=cls.__module__),
        )
