"""Base extension class for Home Assistant template extensions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any, Concatenate, NoReturn

from jinja2 import pass_context
from jinja2.ext import Extension
from jinja2.nodes import Node
from jinja2.parser import Parser

from homeassistant.exceptions import TemplateError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.template import TemplateEnvironment


@dataclass
class TemplateFunction:
    """Definition for a template function, filter, or test."""

    name: str
    func: Callable[..., Any] | Any
    as_global: bool = False
    as_filter: bool = False
    as_test: bool = False
    limited_ok: bool = (
        True  # Whether this function is available in limited environments
    )
    requires_hass: bool = False  # Whether this function requires hass to be available


def _pass_context[**_P, _R](
    func: Callable[Concatenate[Any, _P], _R],
    jinja_context: Callable[
        [Callable[Concatenate[Any, _P], _R]],
        Callable[Concatenate[Any, _P], _R],
    ] = pass_context,
) -> Callable[Concatenate[Any, _P], _R]:
    """Wrap function to pass context.

    We mark these as a context functions to ensure they get
    evaluated fresh with every execution, rather than executed
    at compile time and the value stored. The context itself
    can be discarded.
    """

    @wraps(func)
    def wrapper(_: Any, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        return func(*args, **kwargs)

    return jinja_context(wrapper)


class BaseTemplateExtension(Extension):
    """Base class for Home Assistant template extensions."""

    environment: TemplateEnvironment

    def __init__(
        self,
        environment: TemplateEnvironment,
        *,
        functions: list[TemplateFunction] | None = None,
    ) -> None:
        """Initialize the extension with a list of template functions."""
        super().__init__(environment)

        if functions:
            for template_func in functions:
                # Skip functions that require hass when hass is not available
                if template_func.requires_hass and self.environment.hass is None:
                    continue

                # Register unsupported stub for functions not allowed in limited environments
                if self.environment.limited and not template_func.limited_ok:
                    unsupported_func = self._create_unsupported_function(
                        template_func.name
                    )
                    if template_func.as_global:
                        environment.globals[template_func.name] = unsupported_func
                    if template_func.as_filter:
                        environment.filters[template_func.name] = unsupported_func
                    if template_func.as_test:
                        environment.tests[template_func.name] = unsupported_func
                    continue

                func = template_func.func

                if template_func.requires_hass:
                    # We wrap these as a context functions to ensure they get
                    # evaluated fresh with every execution, rather than executed
                    # at compile time and the value stored.
                    func = _pass_context(func)

                if template_func.as_global:
                    environment.globals[template_func.name] = func
                if template_func.as_filter:
                    environment.filters[template_func.name] = func
                if template_func.as_test:
                    environment.tests[template_func.name] = func

    @staticmethod
    def _create_unsupported_function(name: str) -> Callable[[], NoReturn]:
        """Create a function that raises an error for unsupported functions in limited templates."""

        def unsupported(*args: Any, **kwargs: Any) -> NoReturn:
            raise TemplateError(
                f"Use of '{name}' is not supported in limited templates"
            )

        return unsupported

    @property
    def hass(self) -> HomeAssistant:
        """Return the Home Assistant instance.

        This property should only be used in extensions that have functions
        marked with requires_hass=True, as it assumes hass is not None.

        Raises:
            RuntimeError: If hass is not available in the environment.
        """
        if self.environment.hass is None:
            raise RuntimeError(
                "Home Assistant instance is not available. "
                "This property should only be used in extensions with "
                "functions marked requires_hass=True."
            )
        return self.environment.hass

    def parse(self, parser: Parser) -> Node | list[Node]:
        """Required by Jinja2 Extension base class."""
        return []
