"""Base extension class for Home Assistant template extensions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from jinja2.ext import Extension
from jinja2.nodes import Node
from jinja2.parser import Parser

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


@dataclass
class TemplateFunction:
    """Definition for a template function, filter, or test."""

    name: str
    func: Callable[..., Any]
    as_global: bool = False
    as_filter: bool = False
    as_test: bool = False
    limited_ok: bool = (
        True  # Whether this function is available in limited environments
    )


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
                # Skip functions not allowed in limited environments
                if self.environment.limited and not template_func.limited_ok:
                    continue

                if template_func.as_global:
                    environment.globals[template_func.name] = template_func.func
                if template_func.as_filter:
                    environment.filters[template_func.name] = template_func.func
                if template_func.as_test:
                    environment.tests[template_func.name] = template_func.func

    def parse(self, parser: Parser) -> Node | list[Node]:
        """Required by Jinja2 Extension base class."""
        return []
