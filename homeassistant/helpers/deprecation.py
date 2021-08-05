"""Deprecation helpers for Home Assistant."""
from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable

from ..helpers.frame import MissingIntegrationFrame, get_integration_frame


def deprecated_substitute(substitute_name: str) -> Callable[..., Callable]:
    """Help migrate properties to new names.

    When a property is added to replace an older property, this decorator can
    be added to the new property, listing the old property as the substitute.
    If the old property is defined, its value will be used instead, and a log
    warning will be issued alerting the user of the impending change.
    """

    def decorator(func: Callable) -> Callable:
        """Decorate function as deprecated."""

        def func_wrapper(self: Callable) -> Any:
            """Wrap for the original function."""
            if hasattr(self, substitute_name):
                # If this platform is still using the old property, issue
                # a logger warning once with instructions on how to fix it.
                warnings = getattr(func, "_deprecated_substitute_warnings", {})
                module_name = self.__module__
                if not warnings.get(module_name):
                    logger = logging.getLogger(module_name)
                    logger.warning(
                        "'%s' is deprecated. Please rename '%s' to "
                        "'%s' in '%s' to ensure future support.",
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
            "'%s' is deprecated. Please rename '%s' to '%s' in your "
            "configuration file.",
            old_name,
            old_name,
            new_name,
        )
        return config.get(old_name)
    return config.get(new_name, default)


def deprecated_class(replacement: str) -> Any:
    """Mark class as deprecated and provide a replacement class to be used instead."""

    def deprecated_decorator(cls: Any) -> Any:
        """Decorate class as deprecated."""

        @functools.wraps(cls)
        def deprecated_cls(*args: tuple, **kwargs: dict[str, Any]) -> Any:
            """Wrap for the original class."""
            _print_deprecation_warning(cls, replacement, "class")
            return cls(*args, **kwargs)

        return deprecated_cls

    return deprecated_decorator


def deprecated_function(replacement: str) -> Callable[..., Callable]:
    """Mark function as deprecated and provide a replacement function to be used instead."""

    def deprecated_decorator(func: Callable) -> Callable:
        """Decorate function as deprecated."""

        @functools.wraps(func)
        def deprecated_func(*args: tuple, **kwargs: dict[str, Any]) -> Any:
            """Wrap for the original function."""
            _print_deprecation_warning(func, replacement, "function")
            return func(*args, **kwargs)

        return deprecated_func

    return deprecated_decorator


def _print_deprecation_warning(obj: Any, replacement: str, description: str) -> None:
    logger = logging.getLogger(obj.__module__)
    try:
        _, integration, path = get_integration_frame()
        if path == "custom_components/":
            logger.warning(
                "%s was called from %s, this is a deprecated %s. Use %s instead, please report this to the maintainer of %s",
                obj.__name__,
                integration,
                description,
                replacement,
                integration,
            )
        else:
            logger.warning(
                "%s was called from %s, this is a deprecated %s. Use %s instead",
                obj.__name__,
                integration,
                description,
                replacement,
            )
    except MissingIntegrationFrame:
        logger.warning(
            "%s is a deprecated %s. Use %s instead",
            obj.__name__,
            description,
            replacement,
        )
