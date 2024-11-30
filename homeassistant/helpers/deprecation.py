"""Deprecation helpers for Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from enum import Enum, EnumType, _EnumDict
import functools
import inspect
import logging
from typing import Any, NamedTuple


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
                    setattr(func, "_deprecated_substitute_warnings", warnings)

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


def deprecated_class[**_P, _R](
    replacement: str, *, breaks_in_ha_version: str | None = None
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Mark class as deprecated and provide a replacement class to be used instead.

    If the deprecated function was called from a custom integration, ask the user to
    report an issue.
    """

    def deprecated_decorator(cls: Callable[_P, _R]) -> Callable[_P, _R]:
        """Decorate class as deprecated."""

        @functools.wraps(cls)
        def deprecated_cls(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            """Wrap for the original class."""
            _print_deprecation_warning(
                cls, replacement, "class", "instantiated", breaks_in_ha_version
            )
            return cls(*args, **kwargs)

        return deprecated_cls

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
    # pylint: disable=import-outside-toplevel
    from homeassistant.core import async_get_hass_or_none
    from homeassistant.loader import async_suggest_report_issue

    from .frame import MissingIntegrationFrame, get_integration_frame

    logger = logging.getLogger(module_name)
    if breaks_in_ha_version:
        breaks_in = f" which will be removed in HA Core {breaks_in_ha_version}"
    else:
        breaks_in = ""
    try:
        integration_frame = get_integration_frame()
    except MissingIntegrationFrame:
        if log_when_no_integration_is_found:
            logger.warning(
                "%s is a deprecated %s%s. Use %s instead",
                obj_name,
                description,
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
                (
                    "%s was %s from %s, this is a deprecated %s%s. Use %s instead,"
                    " please %s"
                ),
                obj_name,
                verb,
                integration_frame.integration,
                description,
                breaks_in,
                replacement,
                report_issue,
            )
        else:
            logger.warning(
                "%s was %s from %s, this is a deprecated %s%s. Use %s instead",
                obj_name,
                verb,
                integration_frame.integration,
                description,
                breaks_in,
                replacement,
            )


class DeprecatedConstant(NamedTuple):
    """Deprecated constant."""

    value: Any
    replacement: str
    breaks_in_ha_version: str | None


class DeprecatedConstantEnum(NamedTuple):
    """Deprecated constant."""

    enum: Enum
    breaks_in_ha_version: str | None


class DeprecatedAlias(NamedTuple):
    """Deprecated alias."""

    value: Any
    replacement: str
    breaks_in_ha_version: str | None


class DeferredDeprecatedAlias:
    """Deprecated alias with deferred evaluation of the value."""

    def __init__(
        self,
        value_fn: Callable[[], Any],
        replacement: str,
        breaks_in_ha_version: str | None,
    ) -> None:
        """Initialize."""
        self.breaks_in_ha_version = breaks_in_ha_version
        self.replacement = replacement
        self._value_fn = value_fn

    @functools.cached_property
    def value(self) -> Any:
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
        value = deprecated_const.enum.value
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
        mcs,  # noqa: N804  ruff bug, ruff does not understand this is a metaclass
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
